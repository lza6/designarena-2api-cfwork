# -*- coding: utf-8 -*-
"""
配置管理模块
使用 pydantic-settings 实现配置验证、环境变量支持和热重载
"""

import os
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from pathlib import Path


class Settings(BaseSettings):
    """应用配置"""
    
    model_config = SettingsConfigDict(
        env_prefix="DESIGNARENA_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # ========== 基础配置 ==========
    ROOT: str = Field(
        default_factory=lambda: str(Path(__file__).parent.parent.absolute()),
        description="项目根目录"
    )
    
    # ========== 服务器配置 ==========
    HOST: str = Field(default="127.0.0.1", description="API 服务监听地址")
    PORT: int = Field(default=8000, ge=1, le=65535, description="API 服务端口")
    API_MASTER_KEY: str = Field(default="1", min_length=1, description="主访问凭证")
    
    # ========== 数据库配置 ==========
    DATABASE_URL: str = Field(default="./audit.db", description="审计数据库路径")
    
    # ========== 性能配置 ==========
    MAX_CONCURRENT_TASKS: int = Field(default=10, ge=1, le=50, description="最大并发任务数")
    REQUEST_TIMEOUT: int = Field(default=120, ge=5, le=300, description="请求超时时间 (秒)")
    TASK_QUEUE_SIZE: int = Field(default=100, ge=10, le=1000, description="任务队列大小")
    UI_REFRESH_INTERVAL: int = Field(default=500, ge=100, le=5000, description="UI 刷新间隔 (毫秒)")
    
    # ========== 速率限制 ==========
    RATE_LIMIT_PER_ACCOUNT: int = Field(default=40, ge=1, le=100, description="每账号每分钟最大请求数")
    RATE_LIMIT_WINDOW: int = Field(default=60, ge=10, le=300, description="速率限制时间窗口 (秒)")
    
    # ========== Token 管理 ==========
    TOKEN_REFRESH_BEFORE_EXPIRY: int = Field(default=10, ge=1, le=60, description="Token 过期前提前刷新时间 (分钟)")
    TOKEN_AUTO_REFRESH_INTERVAL: int = Field(default=30, ge=5, le=120, description="Token 自动刷新间隔 (分钟)")
    TOKEN_DEFAULT_EXPIRY: int = Field(default=60, ge=10, le=480, description="Token 默认有效期 (分钟)")
    
    # ========== 浏览器配置 ==========
    BASE_URL: str = Field(default="https://www.designarena.ai", description="目标网站地址")
    BROWSER_HEADLESS: bool = Field(default=True, description="浏览器是否无头模式")
    BROWSER_TIMEOUT: int = Field(default=60000, ge=10000, le=300000, description="浏览器操作超时 (毫秒)")
    
    # ========== 日志配置 ==========
    DEBUG_MODE: bool = Field(default=False, description="调试模式 (输出详细网络包信息)")
    LOG_LEVEL: str = Field(default="INFO", description="日志级别")
    LOG_RETENTION_DAYS: int = Field(default=30, ge=1, le=365, description="日志保留天数")
    
    # ========== 历史数据 ==========
    MAX_HISTORY: int = Field(default=1000, ge=100, le=10000, description="最大历史记录数")
    METRICS_RETENTION_HOURS: int = Field(default=24, ge=1, le=168, description="指标数据保留小时数")
    
    # ========== 主题配置 ==========
    DEFAULT_THEME: str = Field(default="DARK", description="默认主题")
    
    @field_validator('BASE_URL')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """验证 URL 格式"""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('BASE_URL 必须以 http:// 或 https:// 开头')
        return v
    
    @field_validator('LOG_LEVEL')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """验证日志级别"""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'LOG_LEVEL 必须是 {valid_levels} 之一')
        return v.upper()
    
    @field_validator('DEFAULT_THEME')
    @classmethod
    def validate_theme(cls, v: str) -> str:
        """验证主题名称"""
        valid_themes = ['DARK', 'LIGHT', 'HIGH_CONTRAST']
        if v.upper() not in valid_themes:
            raise ValueError(f'DEFAULT_THEME 必须是 {valid_themes} 之一')
        return v.upper()
    
    def get_root(self) -> str:
        """获取项目根目录"""
        return self.ROOT
    
    def get_data_dir(self) -> str:
        """获取数据目录"""
        data_dir = os.path.join(self.ROOT, "data")
        os.makedirs(data_dir, exist_ok=True)
        return data_dir
    
    def get_sessions_dir(self) -> str:
        """获取会话目录"""
        sessions_dir = os.path.join(self.ROOT, "sessions")
        os.makedirs(sessions_dir, exist_ok=True)
        return sessions_dir
    
    def get_images_dir(self) -> str:
        """获取图片目录"""
        images_dir = os.path.join(self.ROOT, "generated_images")
        os.makedirs(images_dir, exist_ok=True)
        return images_dir


# 创建全局配置实例
_global_settings: Optional[Settings] = None


def get_settings(force_reload: bool = False) -> Settings:
    """获取全局配置实例（支持强制重新加载）"""
    global _global_settings
    if _global_settings is None or force_reload:
        _global_settings = Settings()
        init_config() # 同步更新旧的 CONFIG 接口
    return _global_settings


def reload_settings() -> Settings:
    """重新加载配置并同步到 CONFIG"""
    return get_settings(force_reload=True)


def reload_config():
    """便捷的热更新接口"""
    logger.info(" [CONFIG] 正在执行热更新...")
    reload_settings()
    logger.info(" [CONFIG] 配置热更新完成")


# 向后兼容：提供旧的 CONFIG 字典接口
CONFIG = {}


def init_config():
    """初始化/更新全局配置（兼容旧代码）"""
    settings = get_settings()
    CONFIG.clear() # 确保是全新的更新
    CONFIG.update({
        "ROOT": settings.ROOT,
        "BASE_URL": settings.BASE_URL,
        "TIMEOUT_SECONDS": settings.REQUEST_TIMEOUT,
        "API_MASTER_KEY": settings.API_MASTER_KEY,
        "PORT": settings.PORT,
        "HOST": settings.HOST,
        "MAX_HISTORY": settings.MAX_HISTORY,
        "DEBUG_MODE": settings.DEBUG_MODE,
        "MAX_CONCURRENT_TASKS": settings.MAX_CONCURRENT_TASKS,
        "RATE_LIMIT_PER_ACCOUNT": settings.RATE_LIMIT_PER_ACCOUNT,
        "TOKEN_REFRESH_BEFORE_EXPIRY": settings.TOKEN_REFRESH_BEFORE_EXPIRY,
        "UI_REFRESH_INTERVAL": settings.UI_REFRESH_INTERVAL,
        "BROWSER_HEADLESS": settings.BROWSER_HEADLESS,
        "BROWSER_TIMEOUT": settings.BROWSER_TIMEOUT
    })
    
    # 注入全局变量供其他模块直接使用
    os.environ["DESIGNARENA_ROOT"] = settings.ROOT


# 自动初始化配置
init_config()
