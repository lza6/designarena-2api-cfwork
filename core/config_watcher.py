# -*- coding: utf-8 -*-
"""
配置热重载模块
- 监听配置文件变化
- 自动重新加载配置
- 通知配置变更事件
"""

import os
import time
import threading
from pathlib import Path
from typing import Callable, List
from loguru import logger
from core.config import reload_settings, get_settings


class ConfigWatcher:
    """配置文件监听器"""
    
    def __init__(self, env_file: str = ".env"):
        self.env_file = Path(env_file)
        self.last_modified = 0
        self.running = False
        self._thread: threading.Thread = None
        self._callbacks: List[Callable] = []
        self.check_interval = 5  # 每 5 秒检查一次
    
    def start(self):
        """启动监听"""
        if self.running:
            return
        
        self.running = True
        
        # 记录初始修改时间
        if self.env_file.exists():
            self.last_modified = self.env_file.stat().st_mtime
        
        def watch_loop():
            logger.info(f"[CONFIG] 开始监听配置文件：{self.env_file}")
            while self.running:
                try:
                    self._check_changes()
                except Exception as e:
                    logger.error(f"[CONFIG] 检查失败：{e}")
                time.sleep(self.check_interval)
        
        self._thread = threading.Thread(target=watch_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        """停止监听"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=10)
    
    def _check_changes(self):
        """检查文件变化"""
        if not self.env_file.exists():
            return
        
        current_mtime = self.env_file.stat().st_mtime
        
        if current_mtime != self.last_modified:
            logger.info("[CONFIG] 检测到配置文件变化，重新加载...")
            self.last_modified = current_mtime
            
            try:
                # 重新加载配置
                new_settings = reload_settings()
                
                # 通知回调
                self._notify_callbacks(new_settings)
                
                logger.info("[CONFIG] 配置重新加载成功")
            except Exception as e:
                logger.error(f"[CONFIG] 重新加载失败：{e}")
    
    def add_callback(self, callback: Callable):
        """添加配置变更回调"""
        self._callbacks.append(callback)
    
    def _notify_callbacks(self, new_settings):
        """通知所有回调"""
        for callback in self._callbacks:
            try:
                callback(new_settings)
            except Exception as e:
                logger.error(f"[CONFIG] 回调通知失败：{e}")


# 全局配置监听器
_config_watcher: ConfigWatcher = None


def start_config_watcher(env_file: str = ".env"):
    """启动配置监听器"""
    global _config_watcher
    if _config_watcher is None:
        _config_watcher = ConfigWatcher(env_file)
        _config_watcher.start()
        logger.info("[CONFIG] 配置监听器已启动")
    return _config_watcher


def stop_config_watcher():
    """停止配置监听器"""
    global _config_watcher
    if _config_watcher:
        _config_watcher.stop()
        logger.info("[CONFIG] 配置监听器已停止")


def on_config_change(callback: Callable):
    """注册配置变更回调"""
    if _config_watcher:
        _config_watcher.add_callback(callback)
