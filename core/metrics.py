# -*- coding: utf-8 -*-
"""
Metrics 指标收集系统
- 时间序列数据存储
- Prometheus 格式输出
- 系统性能指标监控
"""

import time
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict
from threading import Lock
from core.config import get_settings


class MetricPoint:
    """单个指标数据点"""
    
    def __init__(self, timestamp: float, value: float, labels: Optional[Dict[str, str]] = None):
        self.timestamp = timestamp
        self.value = value
        self.labels = labels or {}


class TimeSeries:
    """时间序列数据"""
    
    def __init__(self, name: str, help_text: str = "", type_: str = "gauge"):
        self.name = name
        self.help = help_text
        self.type = type_  # gauge, counter, histogram
        self.points: List[MetricPoint] = []
        self.lock = Lock()
    
    def add(self, value: float, labels: Optional[Dict[str, str]] = None):
        """添加数据点"""
        with self.lock:
            point = MetricPoint(time.time(), value, labels)
            self.points.append(point)
            
            # 自动清理旧数据（保留最近 N 小时）
            settings = get_settings()
            cutoff = time.time() - (settings.METRICS_RETENTION_HOURS * 3600)
            self.points = [p for p in self.points if p.timestamp > cutoff]
    
    def latest(self, labels: Optional[Dict[str, str]] = None) -> Optional[float]:
        """获取最新值"""
        if not self.points:
            return None
        
        if not labels:
            return self.points[-1].value
        
        # 根据 labels 过滤
        for point in reversed(self.points):
            if all(point.labels.get(k) == v for k, v in labels.items()):
                return point.value
        
        return None
    
    def get_range(self, start_time: float, end_time: float) -> List[MetricPoint]:
        """获取时间范围内的数据"""
        return [p for p in self.points if start_time <= p.timestamp <= end_time]


class MetricsCollector:
    """指标收集器（单例模式）"""
    
    _instance = None
    _lock = Lock()
    
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
        self.series: Dict[str, TimeSeries] = {}
        self.lock = Lock()
        
        # 初始化内置指标
        self._init_builtin_metrics()
        
        print("[METRICS] 指标收集器初始化完成")
    
    def _init_builtin_metrics(self):
        """初始化内置指标"""
        # API 请求指标
        self.register("api_requests_total", "API 请求总数", "counter")
        self.register("api_request_duration_seconds", "API 请求耗时", "histogram")
        self.register("api_errors_total", "API 错误总数", "counter")
        
        # 任务指标
        self.register("tasks_total", "任务总数", "counter")
        self.register("tasks_active", "活跃任务数", "gauge")
        self.register("tasks_completed", "已完成任务数", "counter")
        self.register("tasks_failed", "失败任务数", "counter")
        self.register("task_duration_seconds", "任务执行耗时", "histogram")
        
        # Token 指标
        self.register("token_refresh_total", "Token 刷新次数", "counter")
        self.register("token_expiry_seconds", "Token 剩余有效期", "gauge")
        
        # 队列指标
        self.register("queue_size", "队列大小", "gauge")
        self.register("queue_capacity", "队列容量", "gauge")
        
        # 浏览器/会话指标
        self.register("browser_sessions_active", "活跃浏览器会话数", "gauge")
        self.register("accounts_total", "总账号数", "gauge")
        self.register("accounts_active", "活跃账号数", "gauge")
        
        # 系统资源指标
        self.register("system_cpu_percent", "CPU 使用率", "gauge")
        self.register("system_memory_percent", "内存使用率", "gauge")
    
    def register(self, name: str, help_text: str = "", type_: str = "gauge") -> TimeSeries:
        """注册新指标"""
        with self.lock:
            if name not in self.series:
                self.series[name] = TimeSeries(name, help_text, type_)
            return self.series[name]
    
    def inc(self, name: str, value: float = 1, labels: Optional[Dict[str, str]] = None):
        """增加计数器"""
        if name not in self.series:
            self.register(name, type_="counter")
        
        current = self.series[name].latest(labels) or 0
        self.series[name].add(current + value, labels)
    
    def set(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """设置仪表值"""
        if name not in self.series:
            self.register(name, type_="gauge")
        self.series[name].add(value, labels)
    
    def observe(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """记录观察值（用于直方图）"""
        if name not in self.series:
            self.register(name, type_="histogram")
        self.series[name].add(value, labels)
    
    def timer(self, name: str, labels: Optional[Dict[str, str]] = None):
        """
        计时器装饰器/上下文管理器
        用法:
            with metrics.timer("api_request"):
                # 执行代码
        """
        return TimerContext(self, name, labels)
    
    def get(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[float]:
        """获取指标最新值"""
        if name not in self.series:
            return None
        return self.series[name].latest(labels)
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有指标数据"""
        result = {}
        for name, series in self.series.items():
            if series.points:
                result[name] = {
                    "type": series.type,
                    "help": series.help,
                    "latest": series.latest(),
                    "points_count": len(series.points)
                }
        return result
    
    def to_prometheus(self) -> str:
        """导出为 Prometheus 格式"""
        lines = []
        
        for name, series in sorted(self.series.items()):
            if not series.points:
                continue
            
            # 添加 HELP 注释
            if series.help:
                lines.append(f"# HELP {name} {series.help}")
            
            # 添加 TYPE 注释
            lines.append(f"# TYPE {name} {series.type}")
            
            # 获取最新值（按 labels 分组）
            latest_by_labels = defaultdict(lambda: None)
            for point in series.points[-100:]:  # 只处理最近 100 个点
                label_key = tuple(sorted(point.labels.items()))
                if point.timestamp > (time.time() - 3600):  # 只取最近 1 小时
                    if latest_by_labels[label_key] is None or point.timestamp > latest_by_labels[label_key][0]:
                        latest_by_labels[label_key] = (point.timestamp, point.value, point.labels)
            
            # 输出每个 label 组合的最新值
            for label_key, (ts, value, labels) in latest_by_labels.items():
                if labels:
                    label_str = ",".join([f'{k}="{v}"' for k, v in sorted(labels.items())])
                    lines.append(f"{name}{{{label_str}}} {value}")
                else:
                    lines.append(f"{name} {value}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def to_json(self) -> str:
        """导出为 JSON 格式"""
        data = {
            "timestamp": datetime.now().isoformat(),
            "metrics": {}
        }
        
        for name, series in self.series.items():
            if series.points:
                data["metrics"][name] = {
                    "type": series.type,
                    "help": series.help,
                    "current": series.latest(),
                    "history": [
                        {
                            "timestamp": datetime.fromtimestamp(p.timestamp).isoformat(),
                            "value": p.value,
                            "labels": p.labels
                        }
                        for p in series.points[-50:]  # 只保留最近 50 个点
                    ]
                }
        
        return json.dumps(data, indent=2)
    
    def clear(self):
        """清空所有指标"""
        with self.lock:
            for series in self.series.values():
                series.points.clear()


class TimerContext:
    """计时器上下文管理器"""
    
    def __init__(self, collector: MetricsCollector, name: str, labels: Optional[Dict[str, str]] = None):
        self.collector = collector
        self.name = name
        self.labels = labels
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        self.collector.observe(self.name, duration, self.labels)
        
        # 同时记录请求总数
        if exc_type is None:
            self.collector.inc(f"{self.name}_success", 1, self.labels)
        else:
            self.collector.inc(f"{self.name}_error", 1, self.labels)


# 创建全局实例
_global_metrics_collector = MetricsCollector()


def get_metrics() -> MetricsCollector:
    """获取全局指标收集器实例"""
    return _global_metrics_collector


# 便捷函数
def inc(name: str, value: float = 1, labels: Optional[Dict[str, str]] = None):
    """增加计数器"""
    _global_metrics_collector.inc(name, value, labels)


def set_metric(name: str, value: float, labels: Optional[Dict[str, str]] = None):
    """设置仪表值"""
    _global_metrics_collector.set(name, value, labels)


def observe(name: str, value: float, labels: Optional[Dict[str, str]] = None):
    """记录观察值"""
    _global_metrics_collector.observe(name, value, labels)


def timer(name: str, labels: Optional[Dict[str, str]] = None):
    """计时器"""
    return _global_metrics_collector.timer(name, labels)
