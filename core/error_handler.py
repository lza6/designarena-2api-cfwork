# -*- coding: utf-8 -*-
"""
全局错误处理器
统一处理所有异常，提供友好的错误信息和日志记录
"""

import traceback
from typing import Optional, Callable, Any, Dict
from functools import wraps
from loguru import logger
from core.exceptions import (
    DesignArenaException,
    AuthenticationException,
    TokenExpiredException,
    NetworkException,
    RateLimitException,
    TimeoutException,
    BrowserException,
    TaskException,
    ConfigException
)


class ErrorHandler:
    """全局错误处理器"""
    
    # 错误统计
    error_stats = {
        "total_errors": 0,
        "error_by_type": {},
        "last_error": None,
        "consecutive_errors": 0
    }
    
    @staticmethod
    def handle_exception(exc: Exception, context: str = "") -> Dict[str, Any]:
        """
        统一处理异常
        :param exc: 异常对象
        :param context: 错误发生的上下文
        :return: 错误信息字典
        """
        ErrorHandler.error_stats["total_errors"] += 1
        ErrorHandler.error_stats["consecutive_errors"] += 1
        ErrorHandler.error_stats["last_error"] = {
            "type": type(exc).__name__,
            "context": context,
            "message": str(exc)
        }
        
        # 统计错误类型
        error_type = type(exc).__name__
        if error_type not in ErrorHandler.error_stats["error_by_type"]:
            ErrorHandler.error_stats["error_by_type"][error_type] = 0
        ErrorHandler.error_stats["error_by_type"][error_type] += 1
        
        # 分类处理
        if isinstance(exc, DesignArenaException):
            return ErrorHandler._handle_custom_exception(exc, context)
        elif isinstance(exc, (AuthenticationException, TokenExpiredException)):
            return ErrorHandler._handle_auth_error(exc, context)
        elif isinstance(exc, (NetworkException, RateLimitException, TimeoutException)):
            return ErrorHandler._handle_network_error(exc, context)
        elif isinstance(exc, (BrowserException, TaskException, ConfigException)):
            return ErrorHandler._handle_business_error(exc, context)
        else:
            return ErrorHandler._handle_unknown_error(exc, context)
    
    @staticmethod
    def _handle_custom_exception(exc: DesignArenaException, context: str) -> Dict[str, Any]:
        """处理自定义异常"""
        logger.error(f"[ERROR] {context}: {exc.code} - {exc.message}")
        if exc.details:
            logger.debug(f"[DETAILS] {exc.details}")
        return exc.to_dict()
    
    @staticmethod
    def _handle_auth_error(exc: AuthenticationException, context: str) -> Dict[str, Any]:
        """处理认证错误"""
        logger.warning(f"[AUTH_ERROR] {context}: {exc.message}")
        logger.warning(f"[ACTION] 建议刷新 Token 或重新登录")
        return {
            "error": exc.code,
            "message": f"认证失败：{exc.message}",
            "suggestion": "请刷新 Token 或重新登录",
            "details": exc.details
        }
    
    @staticmethod
    def _handle_network_error(exc: NetworkException, context: str) -> Dict[str, Any]:
        """处理网络错误"""
        if isinstance(exc, RateLimitException):
            logger.warning(f"[RATE_LIMIT] {context}: {exc.message}")
            retry_after = exc.details.get("retry_after", 60)
            return {
                "error": exc.code,
                "message": f"请求受限：{exc.message}",
                "retry_after": retry_after,
                "suggestion": f"请等待 {retry_after} 秒后重试"
            }
        elif isinstance(exc, TimeoutException):
            logger.warning(f"[TIMEOUT] {context}: {exc.message}")
            return {
                "error": exc.code,
                "message": f"请求超时：{exc.message}",
                "timeout": exc.details.get("timeout"),
                "suggestion": "请检查网络连接后重试"
            }
        else:
            logger.error(f"[NETWORK] {context}: {exc.message} (状态码：{exc.status_code})")
            return {
                "error": exc.code,
                "message": f"网络错误：{exc.message}",
                "status_code": exc.status_code,
                "suggestion": "请检查网络连接"
            }
    
    @staticmethod
    def _handle_business_error(exc: DesignArenaException, context: str) -> Dict[str, Any]:
        """处理业务逻辑错误"""
        logger.error(f"[BUSINESS] {context}: {exc.code} - {exc.message}")
        if exc.details:
            logger.debug(f"[DETAILS] {exc.details}")
        return exc.to_dict()
    
    @staticmethod
    def _handle_unknown_error(exc: Exception, context: str) -> Dict[str, Any]:
        """处理未知错误"""
        logger.error(f"[UNKNOWN] {context}: {type(exc).__name__} - {str(exc)}")
        logger.error(f"[TRACEBACK]\n{traceback.format_exc()}")
        return {
            "error": "INTERNAL_ERROR",
            "message": f"系统内部错误：{str(exc)}",
            "suggestion": "请查看日志获取详细信息",
            "type": type(exc).__name__
        }
    
    @staticmethod
    def reset_consecutive_errors():
        """重置连续错误计数"""
        ErrorHandler.error_stats["consecutive_errors"] = 0
    
    @staticmethod
    def get_error_report() -> str:
        """获取错误报告"""
        report = []
        report.append("=" * 60)
        report.append("📊 全局错误统计报告")
        report.append("=" * 60)
        report.append(f"总错误数：{ErrorHandler.error_stats['total_errors']}")
        report.append(f"连续错误：{ErrorHandler.error_stats['consecutive_errors']}")
        
        if ErrorHandler.error_stats["last_error"]:
            last = ErrorHandler.error_stats["last_error"]
            report.append(f"\n最后错误:")
            report.append(f"  类型：{last['type']}")
            report.append(f"  上下文：{last['context']}")
            report.append(f"  信息：{last['message']}")
        
        if ErrorHandler.error_stats["error_by_type"]:
            report.append(f"\n错误类型分布:")
            for etype, count in sorted(ErrorHandler.error_stats["error_by_type"].items(), 
                                      key=lambda x: x[1], reverse=True):
                report.append(f"  {etype}: {count} 次")
        
        report.append("=" * 60)
        return "\n".join(report)


def handle_errors(context: str = ""):
    """
    错误处理装饰器
    :param context: 错误发生的上下文描述
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_ctx = context or func.__name__
                result = ErrorHandler.handle_exception(e, error_ctx)
                
                # 如果是 API 调用，抛出异常
                if isinstance(e, DesignArenaException):
                    raise
                else:
                    # 普通异常转换为 DesignArenaException
                    raise DesignArenaException(
                        message=str(e),
                        code="INTERNAL_ERROR",
                        details={"context": error_ctx}
                    )
        return wrapper
    return decorator


def async_handle_errors(context: str = ""):
    """
    异步错误处理装饰器
    :param context: 错误发生的上下文描述
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_ctx = context or func.__name__
                result = ErrorHandler.handle_exception(e, error_ctx)
                
                # 如果是 API 调用，抛出异常
                if isinstance(e, DesignArenaException):
                    raise
                else:
                    # 普通异常转换为 DesignArenaException
                    raise DesignArenaException(
                        message=str(e),
                        code="INTERNAL_ERROR",
                        details={"context": error_ctx}
                    )
        return wrapper
    return decorator


# 创建全局实例
global_error_handler = ErrorHandler()
