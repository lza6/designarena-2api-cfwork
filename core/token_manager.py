# -*- coding: utf-8 -*-
"""
Token 和 Cookie 自动管理模块
- 自动检测 Token/Cookie 过期
- 后台静默刷新
- 智能错误诊断
- 性能优化和内存管理
"""

import os
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from loguru import logger
from core.config import CONFIG


class TokenManager:
    """单例模式的 Token 管理器"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        auth_dir = os.path.join(CONFIG["ROOT"], "data", "auth")
        os.makedirs(auth_dir, exist_ok=True)
        
        self.token_file = os.path.join(auth_dir, "captured_token.txt")
        self.cookie_file = os.path.join(auth_dir, "captured_cookie.txt")
        self.cache_file = os.path.join(auth_dir, "token_cache.json")
        
        # v7.8: Migrate legacy files from root if they exist
        self._migrate_legacy_files()
        
        # Token 和 Cookie 存储
        self.current_token: Optional[str] = None
        self.current_cookie: Optional[str] = None
        self.token_type: str = "Bearer"  # Bearer or Cookie
        
        # 缓存和过期时间
        self.token_expires_at: Optional[datetime] = None
        self.last_refresh_time: Optional[datetime] = None
        self.refresh_interval = timedelta(minutes=30)  # 30 分钟刷新一次
        
        # 历史过期时间统计（用于智能预测）
        self.expiry_history: List[float] = []  # 记录每次 Token 的实际存活时长（分钟）
        self.avg_token_life: float = 60.0  # 平均过期时间，默认 60 分钟
        
        # 统计信息（用于性能监控）
        self.stats = {
            "total_requests": 0,
            "failed_requests": 0,
            "auto_refresh_count": 0,
            "last_error": None,
            "last_success_time": None,
        }
        
        # 加载已保存的凭证
        self.load_from_files()
        
        logger.info("[TOKEN_MANAGER] Token 管理器初始化完成 (存储路径: data/auth/)")

    def _migrate_legacy_files(self):
        """v7.8: 将旧的凭据文件从根目录迁移到 data/auth/"""
        import shutil
        legacy_files = {
            "captured_token.txt": self.token_file,
            "captured_cookie.txt": self.cookie_file,
            "token_cache.json": self.cache_file
        }
        for old_name, new_path in legacy_files.items():
            old_path = os.path.join(CONFIG["ROOT"], old_name)
            if os.path.exists(old_path) and not os.path.exists(new_path):
                try:
                    shutil.move(old_path, new_path)
                    logger.info(f"[TOKEN_MANAGER] 已迁移旧文件: {old_name} -> data/auth/")
                except Exception as e:
                    logger.warning(f"[TOKEN_MANAGER] 迁移 {old_name} 失败: {e}")
    
    def load_from_files(self):
        """从文件加载 Token 和 Cookie"""
        try:
            # 加载 Token
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    for line in content.split('\n'):
                        if line.startswith('Bearer '):
                            self.current_token = line.replace('Bearer ', '').strip()
                            self.token_type = "Bearer"
                            logger.info(f"[TOKEN_MANAGER] 从文件加载 Token 成功，前缀：{self.current_token[:20]}...")
                            break
            
            # 加载 Cookie
            if os.path.exists(self.cookie_file):
                with open(self.cookie_file, 'r', encoding='utf-8') as f:
                    self.current_cookie = f.read().strip()
                    if not self.current_token:  # 如果没有 Token，使用 Cookie
                        self.token_type = "Cookie"
                    logger.info(f"[TOKEN_MANAGER] 从文件加载 Cookie 成功，长度：{len(self.current_cookie)}")
            
            # 加载缓存（包含过期时间）
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    if 'expires_at' in cache_data:
                        self.token_expires_at = datetime.fromisoformat(cache_data['expires_at'])
                    if 'last_refresh' in cache_data:
                        self.last_refresh_time = datetime.fromisoformat(cache_data['last_refresh'])
                    if 'stats' in cache_data:
                        self.stats.update(cache_data['stats'])
                    if 'expiry_history' in cache_data:
                        self.expiry_history = cache_data['expiry_history']
                    if 'avg_token_life' in cache_data:
                        self.avg_token_life = cache_data['avg_token_life']
                    
        except Exception as e:
            logger.debug(f"[TOKEN_MANAGER] 加载文件失败：{e}")
    
    def save_to_files(self):
        """保存 Token 和 Cookie 到文件"""
        try:
            # 保存 Token
            if self.current_token:
                with open(self.token_file, 'w', encoding='utf-8') as f:
                    f.write(f"{self.token_type} {self.current_token}\n")
                    f.write(f"\n# Captured at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    if self.token_expires_at:
                        f.write(f"# Expires at: {self.token_expires_at.isoformat()}\n")
                
                logger.debug(f"[TOKEN_MANAGER] Token 已保存到文件")
            
            # 保存 Cookie
            if self.current_cookie:
                with open(self.cookie_file, 'w', encoding='utf-8') as f:
                    f.write(self.current_cookie)
                logger.debug(f"[TOKEN_MANAGER] Cookie 已保存到文件")
            
            # 保存缓存（包含过期时间和统计）
            cache_data = {
                'expires_at': self.token_expires_at.isoformat() if self.token_expires_at else None,
                'last_refresh': self.last_refresh_time.isoformat() if self.last_refresh_time else None,
                'stats': self.stats,
                'expiry_history': self.expiry_history[-50:],  # 只保留最近 50 次记录
                'avg_token_life': self.avg_token_life,
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"[TOKEN_MANAGER] Save failed: {e}")
    
    def update_token(self, token: str, cookie: Optional[str] = None, expires_in_minutes: int = 180):
        """
        v8.0: High-Fidelity Token Sync with Lifespan Decay weighted average.
        """
        with self._lock:
            self.current_token = token
            if cookie: self.current_cookie = cookie
            
            # v8.0: Decay Weighted Average for better predictive refresh
            # Prioritize recent session history (70% weight on new sample)
            decay = 0.7
            self.avg_token_life = (self.avg_token_life * (1 - decay)) + (expires_in_minutes * decay)
            
            self.token_expires_at = datetime.now() + timedelta(minutes=expires_in_minutes)
            self.last_refresh_time = datetime.now()
            
            self.stats['auto_refresh_count'] += 1
            self.stats['last_success_time'] = datetime.now().isoformat()
            
            self._save_to_disk_internal()
            logger.info(f"TOKEN | v8.0 Sync Success | Expected Life: {self.avg_token_life:.1f}m")

    def _save_to_disk_internal(self):
        """Internal helper for persistence."""
        self.save_to_files()
    
    def is_expired(self) -> bool:
        """检查 Token 是否过期（提前 10 分钟认为过期）"""
        if not self.token_expires_at:
            return False  # 没有过期时间，认为未过期
        
        # 从配置获取提前刷新时间，默认 10 分钟
        from core.config import get_settings
        try:
            refresh_before = get_settings().TOKEN_REFRESH_BEFORE_EXPIRY
        except:
            refresh_before = 10
        
        # 提前 N 分钟认为过期
        return datetime.now() >= (self.token_expires_at - timedelta(minutes=refresh_before))
    
    def needs_refresh(self) -> bool:
        """检查是否需要刷新（即使未过期）"""
        if not self.last_refresh_time:
            return True  # 从未刷新过
        
        # 基于历史统计数据动态调整刷新间隔
        # 如果平均寿命是 45 分钟，那么在 30 分钟时就应该刷新
        safe_refresh_point = max(5, self.avg_token_life * 0.6)  # 60% 时间点作为安全刷新点
        
        minutes_since_refresh = (datetime.now() - self.last_refresh_time).total_seconds() / 60
        return minutes_since_refresh >= safe_refresh_point
    
    def get_auth_header(self) -> Dict[str, str]:
        """获取认证头（同时包含 Token 和 Cookie，确保兼容性）"""
        self.stats['total_requests'] += 1
        
        headers = {}
        
        # 如果有 Token，添加 Authorization 头
        if self.current_token:
            headers["Authorization"] = f"Bearer {self.current_token}"
        
        # 如果有 Cookie，也添加 Cookie 头（双重保障）
        if self.current_cookie:
            headers["Cookie"] = self.current_cookie
        
        # 返回组合认证头
        return headers
    
    def record_error(self, error_msg: str):
        """记录错误"""
        self.stats['failed_requests'] += 1
        self.stats['last_error'] = error_msg
        logger.warning(f"[TOKEN_MANAGER] ❌ 请求失败：{error_msg}")
        
        # 如果连续失败超过 5 次，建议刷新
        if self.stats['failed_requests'] >= 5:
            logger.warning(f"[TOKEN_MANAGER] ⚠️ 连续失败 5 次，建议刷新 Token")
    
    def get_status_report(self) -> str:
        """获取状态报告"""
        status = []
        status.append("="*60)
        status.append("📊 Token 管理器状态报告")
        status.append("="*60)
        
        if self.current_token:
            status.append(f"✅ Token 状态：活跃")
            status.append(f"   类型：{self.token_type}")
            status.append(f"   前缀：{self.current_token[:30]}...")
            if self.token_expires_at:
                remaining = self.token_expires_at - datetime.now()
                status.append(f"   剩余时间：{remaining.seconds // 60} 分钟")
                status.append(f"   过期时间：{self.token_expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 显示智能预测信息
            if self.expiry_history:
                status.append(f"\n[METRICS] Predictive Analytics:")
                status.append(f"   Weighted Avg Life: {self.avg_token_life:.1f} min")
                status.append(f"   Capture Samples: {len(self.expiry_history)}")
                if len(self.expiry_history) > 1:
                    recent_avg = sum(self.expiry_history[-5:]) / min(5, len(self.expiry_history))
                    status.append(f"   Recent Context: {recent_avg:.1f} min")
        else:
            status.append(f"❌ Token 状态：未登录")
        
        if self.current_cookie:
            status.append(f"✅ Cookie 状态：活跃 (长度：{len(self.current_cookie)})")
        else:
            status.append(f"❌ Cookie 状态：未设置")
        
        status.append(f"\n📉 统计信息:")
        status.append(f"   总请求数：{self.stats['total_requests']}")
        status.append(f"   失败次数：{self.stats['failed_requests']}")
        status.append(f"   自动刷新次数：{self.stats['auto_refresh_count']}")
        
        if self.stats['last_success_time']:
            status.append(f"   最后成功：{self.stats['last_success_time']}")
        
        if self.stats['last_error']:
            status.append(f"   最后错误：{self.stats['last_error']}")
        
        status.append("="*60)
        return "\n".join(status)


# 创建全局单例
_global_token_manager = TokenManager()


def get_token_manager() -> TokenManager:
    """获取全局 Token 管理器实例"""
    return _global_token_manager


def check_and_auto_refresh(browser_context=None):
    """
    检查并自动刷新 Token
    如果浏览器上下文可用，会自动触发刷新流程
    """
    manager = get_token_manager()
    
    if manager.is_expired() or manager.needs_refresh():
        logger.info("[AUTO_REFRESH] 🔄 检测到 Token 需要刷新，启动后台刷新流程...")
        
        if browser_context:
            # 如果有浏览器上下文，尝试静默刷新
            try:
                # 导航到主页触发刷新
                page = browser_context.pages[0] if browser_context.pages else browser_context.new_page()
                page.goto("https://designarena.ai/", wait_until="domcontentloaded", timeout=30000)
                time.sleep(3)  # 等待背景请求
                
                logger.info("[AUTO_REFRESH] ✅ 后台刷新完成")
                manager.stats['auto_refresh_count'] += 1
                
            except Exception as e:
                logger.error(f"[AUTO_REFRESH] ❌ 刷新失败：{e}")
                manager.record_error(str(e))
        else:
            logger.warning("[AUTO_REFRESH] ⚠️ 无可用浏览器上下文，需要手动刷新")
    
    return manager.get_auth_header()


def diagnose_api_error(error_msg: str, response_status: int = None):
    """
    诊断 API 错误原因
    返回是否需要刷新 Token 的建议
    """
    manager = get_token_manager()
    manager.record_error(error_msg)
    
    diagnosis = []
    should_refresh = False
    
    diagnosis.append("\n" + "="*60)
    diagnosis.append("🔍 API 错误诊断报告")
    diagnosis.append("="*60)
    diagnosis.append(f"错误信息：{error_msg}")
    
    if response_status:
        diagnosis.append(f"HTTP 状态码：{response_status}")
    
    # 分析错误类型
    error_lower = error_msg.lower()
    
    if '401' in error_lower or 'unauthorized' in error_lower:
        diagnosis.append("\n❌ 问题：认证失败 (401 Unauthorized)")
        diagnosis.append("💡 原因：Token 已失效或无效")
        diagnosis.append("✅ 解决方案：自动刷新 Token")
        should_refresh = True
        
    elif '403' in error_lower or 'forbidden' in error_lower:
        diagnosis.append("\n❌ 问题：禁止访问 (403 Forbidden)")
        diagnosis.append("💡 原因：Token 权限不足或 IP 受限")
        diagnosis.append("✅ 解决方案：刷新 Token 或检查网络")
        should_refresh = True
        
    elif '429' in error_lower or 'too many requests' in error_lower:
        diagnosis.append("\n⚠️ 问题：请求过于频繁 (429 Too Many Requests)")
        diagnosis.append("💡 原因：触发速率限制")
        diagnosis.append("✅ 解决方案：等待 1 分钟后重试")
        
    elif 'timeout' in error_lower or 'timed out' in error_lower:
        diagnosis.append("\n⚠️ 问题：请求超时")
        diagnosis.append("💡 原因：网络连接不稳定")
        diagnosis.append("✅ 解决方案：检查网络后重试")
        
    elif 'token' in error_lower and ('expir' in error_lower or 'invalid' in error_lower):
        diagnosis.append("\n❌ 问题：Token 过期或无效")
        diagnosis.append("💡 原因：Token 已超过有效期")
        diagnosis.append("✅ 解决方案：立即刷新 Token")
        should_refresh = True
    
    # 显示当前 Token 状态
    diagnosis.append("\n" + manager.get_status_report())
    
    if should_refresh:
        diagnosis.append("\n🔄 正在自动刷新 Token...")
        # 这里可以调用刷新逻辑
    
    diagnosis.append("="*60)
    
    logger.warning("\n".join(diagnosis))
    
    return should_refresh
