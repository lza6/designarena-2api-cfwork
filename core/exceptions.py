# -*- coding: utf-8 -*-
"""
统一异常处理模块
定义所有自定义异常基类和具体异常类型
"""

from typing import Optional, Any, Dict


class DesignArenaException(Exception):
    """所有自定义异常的基类"""
    
    def __init__(self, message: str, code: str = "UNKNOWN_ERROR", details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details
        }


class AuthenticationException(DesignArenaException):
    """认证相关异常 (Token 过期、无效等)"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="AUTH_ERROR", details=details)


class TokenExpiredException(AuthenticationException):
    """Token 过期异常"""
    
    def __init__(self, message: str = "Token 已过期", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="TOKEN_EXPIRED", details=details)


class TokenInvalidException(AuthenticationException):
    """Token 无效异常"""
    
    def __init__(self, message: str = "Token 无效", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="TOKEN_INVALID", details=details)


class NetworkException(DesignArenaException):
    """网络相关异常 (连接失败、超时等)"""
    
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        self.status_code = status_code
        if status_code:
            details = details or {}
            details["status_code"] = status_code
        super().__init__(message, code="NETWORK_ERROR", details=details)


class RateLimitException(NetworkException):
    """请求频率限制异常"""
    
    def __init__(self, message: str = "请求过于频繁", retry_after: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(message, status_code=429, details=details)


class TimeoutException(NetworkException):
    """请求超时异常"""
    
    def __init__(self, message: str = "请求超时", timeout: Optional[float] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if timeout:
            details["timeout"] = timeout
        super().__init__(message, status_code=408, details=details)


class BrowserException(DesignArenaException):
    """浏览器相关异常 (启动失败、页面加载错误等)"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="BROWSER_ERROR", details=details)


class TaskException(DesignArenaException):
    """任务执行相关异常"""
    
    def __init__(self, message: str, task_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if task_id:
            details["task_id"] = task_id
        super().__init__(message, code="TASK_ERROR", details=details)


class ConfigException(DesignArenaException):
    """配置相关异常"""
    
    def __init__(self, message: str, config_key: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if config_key:
            details["config_key"] = config_key
        super().__init__(message, code="CONFIG_ERROR", details=details)


class QueueFullException(TaskException):
    """队列已满异常"""
    
    def __init__(self, message: str = "任务队列已满", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="QUEUE_FULL", details=details)


class ResourceNotFoundException(DesignArenaException):
    """资源未找到异常"""
    
    def __init__(self, resource_type: str, resource_id: str, details: Optional[Dict[str, Any]] = None):
        message = f"{resource_type} '{resource_id}' 未找到"
        details = details or {}
        details["resource_type"] = resource_type
        details["resource_id"] = resource_id
        super().__init__(message, code="NOT_FOUND", details=details)
