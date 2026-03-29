# -*- coding: utf-8 -*-
"""
全局健康监控系统
- 系统资源监控 (CPU、内存)
- 任务队列状态监控
- 账号健康状态监控
- 服务可用性检查
"""

import time
import psutil
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any
from loguru import logger
from core.config import get_settings


class HealthStatus:
    """健康状态枚举"""
    HEALTHY = "healthy"      # 健康
    WARNING = "warning"      # 警告
    CRITICAL = "critical"    # 严重
    UNKNOWN = "unknown"      # 未知


class ComponentHealth:
    """组件健康信息"""
    
    def __init__(self, name: str):
        self.name = name
        self.status = HealthStatus.UNKNOWN
        self.message = ""
        self.last_check: float = 0
        self.response_time: float = 0  # 响应时间 (毫秒)
        self.details: Dict[str, Any] = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "last_check": datetime.fromtimestamp(self.last_check).isoformat() if self.last_check else None,
            "response_time_ms": self.response_time,
            "details": self.details
        }


class HealthMonitor:
    """健康监控器（单例模式）"""
    
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
        self.components: Dict[str, ComponentHealth] = {}
        self.check_interval = 10  # 默认 10 秒检查一次
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: List[callable] = []
        
        # 注册默认组件
        self._register_default_components()
        
        logger.info("[HEALTH] 健康监控器初始化完成")
    
    def _register_default_components(self):
        """注册默认监控组件"""
        self.register_component("api_server")
        self.register_component("task_queue")
        self.register_component("browser_engine")
        self.register_component("token_manager")
        self.register_component("database")
        self.register_component("system_resources")
    
    def register_component(self, name: str):
        """注册组件"""
        if name not in self.components:
            self.components[name] = ComponentHealth(name)
    
    def update_component_health(self, name: str, status: HealthStatus, message: str = "", 
                               response_time: float = 0, details: Optional[Dict[str, Any]] = None):
        """更新组件健康状态"""
        if name not in self.components:
            self.register_component(name)
        
        component = self.components[name]
        component.status = status
        component.message = message
        component.last_check = time.time()
        component.response_time = response_time
        component.details = details or {}
        
        # 触发回调
        self._notify_callbacks(name, component)
    
    def check_system_resources(self):
        """检查系统资源"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # CPU 健康检查
            if cpu_percent > 90:
                cpu_status = HealthStatus.CRITICAL
                cpu_msg = f"CPU 使用率过高：{cpu_percent}%"
            elif cpu_percent > 70:
                cpu_status = HealthStatus.WARNING
                cpu_msg = f"CPU 使用率较高：{cpu_percent}%"
            else:
                cpu_status = HealthStatus.HEALTHY
                cpu_msg = f"CPU 使用率正常：{cpu_percent}%"
            
            # 内存健康检查
            if memory.percent > 90:
                mem_status = HealthStatus.CRITICAL
                mem_msg = f"内存使用率过高：{memory.percent}%"
            elif memory.percent > 70:
                mem_status = HealthStatus.WARNING
                mem_msg = f"内存使用率较高：{memory.percent}%"
            else:
                mem_status = HealthStatus.HEALTHY
                mem_msg = f"内存使用率正常：{memory.percent}%"
            
            # 磁盘健康检查
            if disk.percent > 90:
                disk_status = HealthStatus.CRITICAL
                disk_msg = f"磁盘空间不足：{disk.percent}%"
            elif disk.percent > 70:
                disk_status = HealthStatus.WARNING
                disk_msg = f"磁盘空间较少：{disk.percent}%"
            else:
                disk_status = HealthStatus.HEALTHY
                disk_msg = f"磁盘空间充足：{disk.percent}%"
            
            # 更新组件状态
            self.update_component_health(
                "system_resources",
                HealthStatus.HEALTHY if all(s == HealthStatus.HEALTHY for s in [cpu_status, mem_status, disk_status]) else HealthStatus.WARNING,
                f"CPU: {cpu_msg}; 内存：{mem_msg}; 磁盘：{disk_msg}",
                details={
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_available_mb": memory.available / (1024 * 1024),
                    "disk_percent": disk.percent,
                    "disk_free_gb": disk.free / (1024 * 1024 * 1024)
                }
            )
            
            # 同时更新独立的指标
            from core.metrics import set_metric
            set_metric("system_cpu_percent", cpu_percent)
            set_metric("system_memory_percent", memory.percent)
            
        except Exception as e:
            logger.error(f"[HEALTH] 系统资源检查失败：{e}")
            self.update_component_health("system_resources", HealthStatus.CRITICAL, f"检查失败：{e}")
    
    def check_task_queue(self):
        """检查任务队列"""
        try:
            from core.queue import _global_queue
            
            if _global_queue:
                queue_size = len(_global_queue.tasks)
                active_count = sum(1 for t in _global_queue.tasks.values() if t.status == "running")
                pending_count = sum(1 for t in _global_queue.tasks.values() if t.status == "pending")
                
                settings = get_settings()
                max_tasks = settings.MAX_CONCURRENT_TASKS
                
                if queue_size > settings.TASK_QUEUE_SIZE * 0.9:
                    status = HealthStatus.CRITICAL
                    msg = f"队列接近满载：{queue_size}/{settings.TASK_QUEUE_SIZE}"
                elif active_count >= max_tasks:
                    status = HealthStatus.WARNING
                    msg = f"并发任务已达上限：{active_count}/{max_tasks}"
                else:
                    status = HealthStatus.HEALTHY
                    msg = f"队列运行正常：{queue_size} 个任务 ({active_count} 运行中)"
                
                self.update_component_health(
                    "task_queue",
                    status,
                    msg,
                    details={
                        "total_tasks": queue_size,
                        "active_tasks": active_count,
                        "pending_tasks": pending_count,
                        "max_concurrent": max_tasks,
                        "queue_capacity": settings.TASK_QUEUE_SIZE
                    }
                )
                
                # 更新指标
                from core.metrics import set_metric
                set_metric("queue_size", queue_size)
                set_metric("tasks_active", active_count)
                
        except Exception as e:
            logger.error(f"[HEALTH] 任务队列检查失败：{e}")
            self.update_component_health("task_queue", HealthStatus.CRITICAL, f"检查失败：{e}")
    
    def check_accounts(self):
        """检查账号健康状态"""
        try:
            from core.manager import GlobalState
            
            total_accounts = len(GlobalState.accounts)
            active_accounts = sum(1 for acc in GlobalState.accounts if acc.get("is_active", True))
            
            # 检查是否有过期账号
            expired_count = 0
            now = datetime.now()
            for acc in GlobalState.accounts:
                try:
                    expires_at = acc.get("expires_at")
                    if expires_at:
                        exp_time = datetime.fromisoformat(expires_at)
                        if exp_time < now:
                            expired_count += 1
                except:
                    pass
            
            if expired_count > total_accounts * 0.5:
                status = HealthStatus.CRITICAL
                msg = f"超过半数账号已过期：{expired_count}/{total_accounts}"
            elif expired_count > 0:
                status = HealthStatus.WARNING
                msg = f"{expired_count} 个账号已过期"
            else:
                status = HealthStatus.HEALTHY
                msg = f"所有账号状态正常"
            
            self.update_component_health(
                "token_manager",
                status,
                msg,
                details={
                    "total_accounts": total_accounts,
                    "active_accounts": active_accounts,
                    "expired_accounts": expired_count
                }
            )
            
            # 更新指标
            from core.metrics import set_metric
            set_metric("accounts_total", total_accounts)
            set_metric("accounts_active", active_accounts)
            
        except Exception as e:
            logger.error(f"[HEALTH] 账号健康检查失败：{e}")
            self.update_component_health("token_manager", HealthStatus.CRITICAL, f"检查失败：{e}")
    
    def check_api_server(self):
        """检查 API 服务器"""
        try:
            settings = get_settings()
            
            # 简单检查：API 服务是否在运行
            # 这里可以通过尝试连接端口来检查
            import socket
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex((settings.HOST, settings.PORT))
            sock.close()
            
            if result == 0:
                status = HealthStatus.HEALTHY
                msg = f"API 服务运行正常：{settings.HOST}:{settings.PORT}"
            else:
                status = HealthStatus.CRITICAL
                msg = f"API 服务无法访问：{settings.HOST}:{settings.PORT}"
            
            self.update_component_health("api_server", status, msg)
            
        except Exception as e:
            logger.error(f"[HEALTH] API 服务检查失败：{e}")
            self.update_component_health("api_server", HealthStatus.CRITICAL, f"检查失败：{e}")
    
    def run_all_checks(self):
        """执行所有健康检查"""
        self.check_system_resources()
        self.check_task_queue()
        self.check_accounts()
        self.check_api_server()
    
    def get_overall_status(self) -> HealthStatus:
        """获取整体健康状态"""
        if not self.components:
            return HealthStatus.UNKNOWN
        
        statuses = [c.status for c in self.components.values()]
        
        if any(s == HealthStatus.CRITICAL for s in statuses):
            return HealthStatus.CRITICAL
        elif any(s == HealthStatus.WARNING for s in statuses):
            return HealthStatus.WARNING
        elif all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY
        else:
            return HealthStatus.UNKNOWN
    
    def get_health_report(self) -> Dict[str, Any]:
        """获取健康报告"""
        return {
            "overall_status": self.get_overall_status(),
            "timestamp": datetime.now().isoformat(),
            "components": {
                name: comp.to_dict() for name, comp in self.components.items()
            }
        }
    
    def start_background_monitoring(self, interval: int = 10):
        """启动后台监控"""
        self.check_interval = interval
        self.running = True
        
        def monitor_loop():
            logger.info(f"[HEALTH] 启动后台监控，间隔：{interval}秒")
            while self.running:
                try:
                    self.run_all_checks()
                except Exception as e:
                    logger.error(f"[HEALTH] 监控循环出错：{e}")
                time.sleep(self.check_interval)
        
        self._thread = threading.Thread(target=monitor_loop, daemon=True)
        self._thread.start()
    
    def stop_background_monitoring(self):
        """停止后台监控"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
    
    def add_callback(self, callback: callable):
        """添加状态变更回调"""
        self._callbacks.append(callback)
    
    def _notify_callbacks(self, component_name: str, component: ComponentHealth):
        """通知回调"""
        for callback in self._callbacks:
            try:
                callback(component_name, component)
            except Exception as e:
                logger.error(f"[HEALTH] 回调通知失败：{e}")


# 创建全局实例
_global_health_monitor = HealthMonitor()


def get_health_monitor() -> HealthMonitor:
    """获取全局健康监控器实例"""
    return _global_health_monitor
