# -*- coding: utf-8 -*-
"""
审计日志模块
- 记录所有敏感操作
- 支持日志查询和导出
- 日志轮转机制
- 操作追溯
"""

import sqlite3
import time
import os
import csv
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from loguru import logger
from core.config import get_settings

DB_FILE = "audit.db"

# 审计日志动作类型
ACTION_TYPES = {
    # Token 相关
    "TOKEN_REFRESH": "Token 刷新",
    "TOKEN_UPDATE": "Token 更新",
    "TOKEN_EXPIRED": "Token 过期",
    
    # 账号相关
    "ACCOUNT_ADD": "添加账号",
    "ACCOUNT_REMOVE": "删除账号",
    "ACCOUNT_SWITCH": "切换账号",
    "ACCOUNT_RENAME": "重命名账号",
    
    # 任务相关
    "TASK_CREATE": "创建任务",
    "TASK_COMPLETE": "任务完成",
    "TASK_FAILED": "任务失败",
    "TASK_CANCEL": "取消任务",
    
    # 系统相关
    "CONFIG_CHANGE": "配置变更",
    "SYSTEM_START": "系统启动",
    "SYSTEM_STOP": "系统停止",
    
    # 安全相关
    "LOGIN_SUCCESS": "登录成功",
    "LOGIN_FAILED": "登录失败",
    "AUTH_ERROR": "认证错误",
    "RATE_LIMIT": "频率限制",
}


def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 创建审计日志表（增强版）
    c.execute('''CREATE TABLE IF NOT EXISTS audit_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  account_id TEXT,
                  action TEXT,
                  action_type TEXT,
                  status TEXT,
                  prompt TEXT,
                  error TEXT,
                  ip_address TEXT,
                  user_agent TEXT,
                  metadata TEXT,
                  session_id TEXT)''')
    
    # 添加索引以加速查询
    try:
        c.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_logs(timestamp DESC)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_account_id ON audit_logs(account_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_action ON audit_logs(action)')
    except Exception as e:
        logger.debug(f"创建索引：{e}")
    
    conn.commit()
    conn.close()
    logger.info("[AUDIT] 审计数据库初始化完成")


def log_task(account_id: str, action: str, status: str, 
             prompt: Optional[str] = None, 
             error: Optional[str] = None, 
             ip: Optional[str] = None, 
             ua: Optional[str] = None,
             metadata: Optional[Dict[str, Any]] = None,
             session_id: Optional[str] = None) -> None:
    """
    记录审计日志
    :param account_id: 账号 ID
    :param action: 动作名称
    :param status: 状态 (success/failed/pending)
    :param prompt: 提示词/请求内容
    :param error: 错误信息
    :param ip: IP 地址
    :param ua: User-Agent
    :param metadata: 额外元数据（JSON 格式）
    :param session_id: 会话 ID
    """
    try:
        settings = get_settings()
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # 获取动作类型描述
        action_type = ACTION_TYPES.get(action, action)
        
        # 序列化 metadata
        metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else None
        
        c.execute("""INSERT INTO audit_logs 
                     (account_id, action, action_type, status, prompt, error, ip_address, user_agent, metadata, session_id) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (account_id, action, action_type, status, prompt, error, ip, ua, metadata_json, session_id))
        
        conn.commit()
        conn.close()
        
        # 同步输出到日志
        log_msg = f"[AUDIT] {action_type} | 账号：{account_id} | 状态：{status}"
        if error:
            log_msg += f" | 错误：{error}"
        logger.info(log_msg)
        
        # 检查是否需要日志轮转
        _check_log_rotation()
        
    except Exception as e:
        logger.error(f"[AUDIT] 记录日志失败：{e}")


def _check_log_rotation():
    """检查是否需要日志轮转"""
    try:
        settings = get_settings()
        
        if not os.path.exists(DB_FILE):
            return
        
        # 检查日志保留期限
        retention_days = settings.LOG_RETENTION_DAYS
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # 删除过期的日志
        c.execute("DELETE FROM audit_logs WHERE timestamp < ?", (cutoff_date.isoformat(),))
        deleted_count = c.rowcount
        
        conn.commit()
        conn.close()
        
        if deleted_count > 0:
            logger.info(f"[AUDIT] 已清理 {deleted_count} 条过期日志（>{retention_days}天）")
    
    except Exception as e:
        logger.debug(f"[AUDIT] 日志轮转检查失败：{e}")


def get_history(limit: int = 50, 
                account_id: Optional[str] = None,
                action: Optional[str] = None,
                start_time: Optional[str] = None,
                end_time: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    获取审计历史
    :param limit: 返回数量限制
    :param account_id: 按账号过滤
    :param action: 按动作过滤
    :param start_time: 开始时间 (ISO 格式)
    :param end_time: 结束时间 (ISO 格式)
    :return: 审计日志列表
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row  # 返回字典格式
        c = conn.cursor()
        
        # 构建动态查询
        query = "SELECT * FROM audit_logs WHERE 1=1"
        params = []
        
        if account_id:
            query += " AND account_id = ?"
            params.append(account_id)
        
        if action:
            query += " AND action = ?"
            params.append(action)
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        c.execute(query, params)
        rows = c.fetchall()
        
        # 转换为字典列表
        result = []
        for row in rows:
            row_dict = dict(row)
            # 解析 metadata
            if row_dict.get('metadata'):
                try:
                    row_dict['metadata'] = json.loads(row_dict['metadata'])
                except:
                    pass
            result.append(row_dict)
        
        conn.close()
        return result
    
    except Exception as e:
        logger.error(f"[AUDIT] 查询历史失败：{e}")
        return []


def export_history(filename: str, fmt: str = "csv", 
                   account_id: Optional[str] = None,
                   start_time: Optional[str] = None,
                   end_time: Optional[str] = None) -> str:
    """导出审计历史"""
    try:
        # 获取数据
        history = get_history(limit=10000, account_id=account_id, 
                             start_time=start_time, end_time=end_time)
        
        if fmt.lower() == "csv":
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                
                # 写入表头
                headers = ["ID", "时间戳", "账号 ID", "动作", "状态", "提示词", "错误信息", "IP 地址"]
                writer.writerow(headers)
                
                # 写入数据
                for row in history:
                    writer.writerow([
                        row.get('id'),
                        row.get('timestamp'),
                        row.get('account_id'),
                        row.get('action_type', row.get('action')),
                        row.get('status'),
                        row.get('prompt', ''),
                        row.get('error', ''),
                        row.get('ip_address', '')
                    ])
            
            logger.info(f"[AUDIT] 已导出 CSV 到 {filename}, 共 {len(history)} 条记录")
        
        elif fmt.lower() == "json":
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            
            logger.info(f"[AUDIT] 已导出 JSON 到 {filename}, 共 {len(history)} 条记录")
        
        return filename
    
    except Exception as e:
        logger.error(f"[AUDIT] 导出历史失败：{e}")
        return ""


def get_audit_statistics() -> Dict[str, Any]:
    """获取审计统计信息"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        stats = {}
        
        # 总记录数
        c.execute("SELECT COUNT(*) FROM audit_logs")
        stats['total_records'] = c.fetchone()[0]
        
        # 按状态统计
        c.execute("SELECT status, COUNT(*) FROM audit_logs GROUP BY status")
        stats['by_status'] = dict(c.fetchall())
        
        # 按动作统计 (Top 10)
        c.execute("SELECT action_type, COUNT(*) FROM audit_logs GROUP BY action_type ORDER BY COUNT(*) DESC LIMIT 10")
        stats['top_actions'] = dict(c.fetchall())
        
        # 最近 24 小时活动
        now = datetime.now()
        yesterday = (now - timedelta(days=1)).isoformat()
        c.execute("SELECT COUNT(*) FROM audit_logs WHERE timestamp >= ?", (yesterday,))
        stats['last_24h'] = c.fetchone()[0]
        
        # 最近 7 天活动
        last_week = (now - timedelta(days=7)).isoformat()
        c.execute("SELECT COUNT(*) FROM audit_logs WHERE timestamp >= ?", (last_week,))
        stats['last_7d'] = c.fetchone()[0]
        
        conn.close()
        
        return stats
    
    except Exception as e:
        logger.error(f"[AUDIT] 统计失败：{e}")
        return {}


def search_logs(keyword: str, limit: int = 100) -> List[Dict[str, Any]]:
    """搜索日志（模糊匹配）"""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        search_pattern = f"%{keyword}%"
        c.execute("""
            SELECT * FROM audit_logs 
            WHERE prompt LIKE ? OR error LIKE ? OR action LIKE ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (search_pattern, search_pattern, search_pattern, limit))
        
        rows = c.fetchall()
        result = []
        for row in rows:
            row_dict = dict(row)
            if row_dict.get('metadata'):
                try:
                    row_dict['metadata'] = json.loads(row_dict['metadata'])
                except:
                    pass
            result.append(row_dict)
        
        conn.close()
        return result
    
    except Exception as e:
        logger.error(f"[AUDIT] 搜索失败：{e}")
        return []


# 便捷函数
def log_sensitive_operation(account_id: str, operation: str, success: bool, 
                           details: Optional[Dict[str, Any]] = None):
    """记录敏感操作"""
    status = "success" if success else "failed"
    log_task(
        account_id=account_id,
        action=operation,
        status=status,
        metadata=details
    )




# 初始化数据库
init_db()
