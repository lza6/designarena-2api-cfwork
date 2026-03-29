# -*- coding: utf-8 -*-
"""
数据库迁移脚本
升级旧版 audit.db 到新版表结构
"""

import sqlite3
import os
from loguru import logger

DB_FILE = "audit.db"


def migrate_audit_db():
    """迁移审计日志数据库到新版本"""
    
    if not os.path.exists(DB_FILE):
        logger.info("数据库不存在，无需迁移")
        return
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    try:
        # 检查当前表结构
        c.execute("PRAGMA table_info(audit_logs)")
        columns = [row[1] for row in c.fetchall()]
        
        logger.info(f"当前列：{columns}")
        
        # 需要添加的新列
        new_columns = [
            ("action_type", "TEXT"),
            ("metadata", "TEXT"),
            ("session_id", "TEXT"),
        ]
        
        # 添加缺失的列
        for col_name, col_type in new_columns:
            if col_name not in columns:
                logger.info(f"添加列：{col_name}")
                try:
                    c.execute(f"ALTER TABLE audit_logs ADD COLUMN {col_name} {col_type}")
                    logger.success(f"✅ 已添加列：{col_name}")
                except Exception as e:
                    logger.warning(f"列 {col_name} 可能已存在：{e}")
        
        conn.commit()
        logger.success("✅ 数据库迁移完成!")
        
        # 验证新结构
        c.execute("PRAGMA table_info(audit_logs)")
        new_columns_list = [row[1] for row in c.fetchall()]
        logger.info(f"新列：{new_columns_list}")
        
    except Exception as e:
        logger.error(f"❌ 迁移失败：{e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("DesignArena 审计数据库迁移工具")
    print("=" * 60)
    print()
    
    migrate_audit_db()
    
    print()
    print("迁移完成！请重启主程序。")
    print("=" * 60)
