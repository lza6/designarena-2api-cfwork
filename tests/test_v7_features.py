# -*- coding: utf-8 -*-
"""
DesignArena v7 功能验证测试
运行此脚本验证所有新功能是否正常工作
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import time
from datetime import datetime


def test_imports():
    """测试所有新模块是否可以导入"""
    print("=" * 60)
    print("测试 1: 模块导入")
    print("=" * 60)
    
    tests = [
        ("配置管理", "core.config", ["get_settings", "reload_settings"]),
        ("错误处理", "core.exceptions", ["DesignArenaException", "TokenExpiredException"]),
        ("错误处理器", "core.error_handler", ["ErrorHandler", "handle_errors"]),
        ("指标收集", "core.metrics", ["MetricsCollector", "get_metrics"]),
        ("健康监控", "core.health_monitor", ["HealthMonitor", "get_health_monitor"]),
        ("审计日志", "core.audit", ["log_task", "get_history", "export_history"]),
        ("配置监听", "core.config_watcher", ["start_config_watcher"]),
        ("Token 管理", "core.token_manager", ["TokenManager", "get_token_manager"]),
    ]
    
    passed = 0
    failed = 0
    
    for name, module_name, symbols in tests:
        try:
            module = __import__(module_name, fromlist=symbols)
            for symbol in symbols:
                assert hasattr(module, symbol), f"缺少 {symbol}"
            print(f"✅ {name}: {module_name}")
            passed += 1
        except Exception as e:
            print(f"❌ {name}: {e}")
            failed += 1
    
    print(f"\n结果：{passed} 通过，{failed} 失败\n")
    return failed == 0


def test_config():
    """测试配置管理"""
    print("=" * 60)
    print("测试 2: 配置管理")
    print("=" * 60)
    
    try:
        from core.config import get_settings
        
        settings = get_settings()
        
        # 测试配置项
        assert settings.HOST == "127.0.0.1", "HOST 配置错误"
        assert settings.PORT == 8000, "PORT 配置错误"
        assert settings.MAX_CONCURRENT_TASKS == 10, "MAX_CONCURRENT_TASKS 配置错误"
        assert settings.TOKEN_REFRESH_BEFORE_EXPIRY == 10, "TOKEN_REFRESH_BEFORE_EXPIRY 配置错误"
        assert settings.RATE_LIMIT_PER_ACCOUNT == 40, "RATE_LIMIT_PER_ACCOUNT 配置错误"
        
        print("✅ 所有配置项加载正确")
        print(f"   - HOST: {settings.HOST}")
        print(f"   - PORT: {settings.PORT}")
        print(f"   - MAX_CONCURRENT_TASKS: {settings.MAX_CONCURRENT_TASKS}")
        print(f"   - TOKEN_REFRESH_BEFORE_EXPIRY: {settings.TOKEN_REFRESH_BEFORE_EXPIRY} 分钟")
        print(f"   - RATE_LIMIT_PER_ACCOUNT: {settings.RATE_LIMIT_PER_ACCOUNT} 请求/分钟")
        print()
        return True
        
    except Exception as e:
        print(f"❌ 配置测试失败：{e}\n")
        return False


def test_error_handling():
    """测试错误处理"""
    print("=" * 60)
    print("测试 3: 错误处理系统")
    print("=" * 60)
    
    try:
        from core.exceptions import (
            DesignArenaException, 
            TokenExpiredException,
            RateLimitException
        )
        from core.error_handler import ErrorHandler
        
        # 测试自定义异常
        try:
            raise TokenExpiredException("Token 已过期", {"user": "test"})
        except DesignArenaException as e:
            error_dict = e.to_dict()
            assert error_dict["error"] == "TOKEN_EXPIRED"
            assert error_dict["message"] == "Token 已过期"
            print("✅ 自定义异常工作正常")
        
        # 测试错误处理器
        result = ErrorHandler.handle_exception(
            RateLimitException("请求过多", retry_after=60),
            context="API 测试"
        )
        assert result["error"] == "NETWORK_ERROR"
        assert result.get("retry_after") == 60
        print("✅ 错误处理器工作正常")
        print()
        return True
        
    except Exception as e:
        print(f"❌ 错误处理测试失败：{e}\n")
        return False


def test_metrics():
    """测试指标收集"""
    print("=" * 60)
    print("测试 4: 指标收集系统")
    print("=" * 60)
    
    try:
        from core.metrics import get_metrics
        
        metrics = get_metrics()
        
        # 测试指标记录
        metrics.inc("test_counter", 1, {"label": "value"})
        metrics.set("test_gauge", 42.5)
        metrics.observe("test_histogram", 0.123)
        
        # 获取值
        counter_value = metrics.get("test_counter", {"label": "value"})
        gauge_value = metrics.get("test_gauge")
        
        assert counter_value == 1, f"Counter 值错误：{counter_value}"
        assert gauge_value == 42.5, f"Gauge 值错误：{gauge_value}"
        
        print("✅ 指标记录工作正常")
        print(f"   - Counter: {counter_value}")
        print(f"   - Gauge: {gauge_value}")
        
        # 测试 Prometheus 格式导出
        prometheus_output = metrics.to_prometheus()
        assert "test_counter" in prometheus_output
        assert "test_gauge" in prometheus_output
        print("✅ Prometheus 格式导出正常")
        print()
        return True
        
    except Exception as e:
        print(f"❌ 指标测试失败：{e}\n")
        return False


def test_health_monitor():
    """测试健康监控"""
    print("=" * 60)
    print("测试 5: 健康监控系统")
    print("=" * 60)
    
    try:
        from core.health_monitor import get_health_monitor, HealthStatus
        
        monitor = get_health_monitor()
        
        # 测试组件注册
        monitor.register_component("test_component")
        assert "test_component" in monitor.components
        print("✅ 组件注册工作正常")
        
        # 测试健康状态更新
        monitor.update_component_health(
            "test_component",
            HealthStatus.HEALTHY,
            "测试正常",
            response_time=10.5
        )
        
        component = monitor.components["test_component"]
        assert component.status == HealthStatus.HEALTHY
        assert component.response_time == 10.5
        print("✅ 健康状态更新正常")
        
        # 测试健康报告
        report = monitor.get_health_report()
        assert "overall_status" in report
        assert "components" in report
        assert "timestamp" in report
        print("✅ 健康报告生成正常")
        print()
        return True
        
    except Exception as e:
        print(f"❌ 健康监控测试失败：{e}\n")
        return False


def test_audit_log():
    """测试审计日志"""
    print("=" * 60)
    print("测试 6: 审计日志系统")
    print("=" * 60)
    
    try:
        from core.audit import log_task, get_history, get_audit_statistics
        
        # 记录测试日志
        log_task(
            account_id="test_account",
            action="TEST_ACTION",
            status="success",
            prompt="测试提示词",
            metadata={"test_key": "test_value"}
        )
        print("✅ 日志记录工作正常")
        
        # 查询日志
        history = get_history(limit=1, account_id="test_account")
        assert len(history) > 0, "未找到刚记录的日志"
        print("✅ 日志查询工作正常")
        
        # 获取统计
        stats = get_audit_statistics()
        assert "total_records" in stats
        assert "by_status" in stats
        print("✅ 统计信息生成正常")
        print(f"   - 总记录数：{stats.get('total_records', 0)}")
        print()
        return True
        
    except Exception as e:
        print(f"❌ 审计日志测试失败：{e}\n")
        return False


def test_token_manager():
    """测试 Token 管理器"""
    print("=" * 60)
    print("测试 7: Token 智能管理")
    print("=" * 60)
    
    try:
        from core.token_manager import get_token_manager
        
        manager = get_token_manager()
        
        # 测试智能预测功能
        assert hasattr(manager, 'expiry_history'), "缺少历史记录"
        assert hasattr(manager, 'avg_expiry_minutes'), "缺少平均寿命"
        print("✅ 智能预测功能就绪")
        
        # 测试过期检测 (提前 10 分钟)
        from datetime import datetime, timedelta
        manager.token_expires_at = datetime.now() + timedelta(minutes=15)
        manager.last_refresh_time = datetime.now() - timedelta(minutes=30)
        
        # 应该认为即将过期 (剩余 15 分钟 < 10 分钟阈值)
        is_expired = manager.is_expired()
        needs_refresh = manager.needs_refresh()
        
        print(f"   - Token 过期检测：{'✅' if not is_expired else '❌'}")
        print(f"   - 需要刷新检测：{'✅' if needs_refresh else '⚠️'}")
        print()
        return True
        
    except Exception as e:
        print(f"❌ Token 管理测试失败：{e}\n")
        return False


def main():
    """主测试函数"""
    print("\n")
    print("🚀" * 30)
    print("DesignArena v7 功能验证测试")
    print("🚀" * 30)
    print()
    
    tests = [
        ("模块导入", test_imports),
        ("配置管理", test_config),
        ("错误处理", test_error_handling),
        ("指标收集", test_metrics),
        ("健康监控", test_health_monitor),
        ("审计日志", test_audit_log),
        ("Token 管理", test_token_manager),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ {name} 测试异常：{e}\n")
            failed += 1
    
    # 总结
    print("=" * 60)
    print(f"测试结果：{passed}/{len(tests)} 通过")
    print("=" * 60)
    
    if failed == 0:
        print("\n✅ 所有测试通过！v7 升级成功!")
        print("\n📋 下一步:")
        print("   1. 编辑 .env 文件自定义配置")
        print("   2. 启动主程序测试 API 端点")
        print("   3. 访问 http://localhost:8000/health 检查健康状态")
        print("   4. 访问 http://localhost:8000/metrics 查看指标数据")
        return 0
    else:
        print(f"\n❌ {failed} 个测试失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    sys.exit(main())
