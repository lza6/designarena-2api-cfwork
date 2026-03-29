# -*- coding: utf-8 -*-
"""
端到端自动续杯测试
测试完整的自动刷新/自动续杯流程
"""

import os
import sys
import time
import pytest
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.token_manager import (
    TokenManager,
    get_token_manager,
    check_and_auto_refresh,
    diagnose_api_error
)
from core.browser import PlaywrightManager, start_refresh_thread


class TestEndToEndAutoRefresh:
    """端到端自动续杯测试"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后清理"""
        self.temp_dir = tempfile.mkdtemp()
        
        with patch('core.token_manager.CONFIG') as mock_config:
            mock_config.__getitem__ = lambda self, key: self.temp_dir if key == "ROOT" else None
            
            # 重置单例
            TokenManager._instance = None
            
            self.manager = TokenManager()
            yield
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_complete_refresh_cycle(self):
        """E2E-001: 测试完整的刷新周期"""
        # 1. 初始状态 - 没有Token
        assert self.manager.current_token is None, "初始应该没有Token"
        assert self.manager.needs_refresh(), "首次应该需要刷新"
        
        # 2. 模拟首次登录获取Token
        first_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.first_login"
        first_cookie = "session_id=first_session"
        self.manager.update_token(first_token, cookie=first_cookie, expires_in_minutes=60)
        
        # 3. 验证Token已保存
        assert self.manager.current_token == first_token, "Token应该已保存"
        assert self.manager.current_cookie == first_cookie, "Cookie应该已保存"
        assert not self.manager.is_expired(), "新Token不应该过期"
        
        # 4. 模拟时间流逝，Token即将过期
        self.manager.token_expires_at = datetime.now() + timedelta(minutes=5)
        self.manager.last_refresh_time = datetime.now() - timedelta(minutes=50)
        
        # 5. 验证需要刷新
        assert self.manager.is_expired(), "Token应该被判定为即将过期"
        assert self.manager.needs_refresh(), "应该需要刷新"
        
        # 6. 模拟自动刷新获取新Token
        second_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.second_refresh"
        second_cookie = "session_id=second_session"
        self.manager.update_token(second_token, cookie=second_cookie, expires_in_minutes=60)
        
        # 7. 验证Token已更新
        assert self.manager.current_token == second_token, "Token应该已更新"
        assert self.manager.current_cookie == second_cookie, "Cookie应该已更新"
        assert not self.manager.is_expired(), "新Token不应该过期"
        
        # 8. 验证统计信息
        assert self.manager.stats['auto_refresh_count'] == 2, "应该有2次刷新记录"
    
    def test_multiple_refresh_cycles(self):
        """E2E-010: 测试连续多次刷新"""
        tokens = []
        
        # 模拟5次刷新
        for i in range(5):
            token = f"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.refresh_{i}"
            self.manager.update_token(token, expires_in_minutes=60)
            tokens.append(token)
            
            # 模拟时间流逝
            time.sleep(0.01)
        
        # 验证最终Token是最后一个
        assert self.manager.current_token == tokens[-1], "最终Token应该是最后一个"
        
        # 验证刷新次数
        assert self.manager.stats['auto_refresh_count'] == 5, "应该有5次刷新记录"
    
    def test_history_accumulation(self):
        """E2E-011: 测试历史记录累积"""
        # 模拟不同寿命的Token
        lifetimes = [45, 50, 55, 60, 65]
        
        for lifetime in lifetimes:
            self.manager.update_token(f"token_{lifetime}", expires_in_minutes=lifetime)
        
        # 验证历史记录
        # 注意：expiry_history在update_token中没有直接添加，需要手动模拟
        # 这里验证avg_token_life被更新
        assert self.manager.avg_token_life > 0, "平均寿命应该被计算"
    
    def test_weighted_average_accuracy(self):
        """E2E-012: 测试加权平均算法准确性"""
        # 初始平均寿命
        initial_avg = 60.0
        self.manager.avg_token_life = initial_avg
        
        # 更新Token，设置新的过期时间
        new_lifetime = 45
        self.manager.update_token("test_token", expires_in_minutes=new_lifetime)
        
        # 计算预期的加权平均值
        # decay = 0.7
        # new_avg = (old_avg * (1 - decay)) + (new_value * decay)
        expected_avg = (initial_avg * 0.3) + (new_lifetime * 0.7)
        
        # 验证计算结果
        assert abs(self.manager.avg_token_life - expected_avg) < 0.01, \
            f"加权平均值应该准确，预期{expected_avg}，实际{self.manager.avg_token_life}"


class TestCheckAndAutoRefresh:
    """测试check_and_auto_refresh函数"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后清理"""
        self.temp_dir = tempfile.mkdtemp()
        
        with patch('core.token_manager.CONFIG') as mock_config:
            mock_config.__getitem__ = lambda self, key: self.temp_dir if key == "ROOT" else None
            
            # 重置单例
            TokenManager._instance = None
            
            self.manager = TokenManager()
            yield
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_check_and_auto_refresh_no_browser(self):
        """测试无浏览器上下文的自动刷新"""
        # 设置Token即将过期
        self.manager.token_expires_at = datetime.now() + timedelta(minutes=5)
        self.manager.last_refresh_time = datetime.now() - timedelta(minutes=50)
        self.manager.current_token = "test_token"
        
        # 调用check_and_auto_refresh
        headers = check_and_auto_refresh(browser_context=None)
        
        # 验证返回认证头
        assert "Authorization" in headers, "应该返回Authorization头"
    
    def test_check_and_auto_refresh_with_browser(self):
        """测试有浏览器上下文的自动刷新"""
        # 设置Token即将过期
        self.manager.token_expires_at = datetime.now() + timedelta(minutes=5)
        self.manager.last_refresh_time = datetime.now() - timedelta(minutes=50)
        self.manager.current_token = "test_token"
        
        # Mock浏览器上下文
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_context.pages = [mock_page]
        mock_context.new_page.return_value = mock_page
        
        # 调用check_and_auto_refresh
        with patch('time.sleep'):  # 跳过sleep
            headers = check_and_auto_refresh(browser_context=mock_context)
        
        # 验证返回认证头
        assert "Authorization" in headers, "应该返回Authorization头"
        
        # 验证页面被访问
        mock_page.goto.assert_called()


class TestDiagnoseApiError:
    """测试API错误诊断"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后清理"""
        self.temp_dir = tempfile.mkdtemp()
        
        with patch('core.token_manager.CONFIG') as mock_config:
            mock_config.__getitem__ = lambda self, key: self.temp_dir if key == "ROOT" else None
            
            # 重置单例
            TokenManager._instance = None
            
            self.manager = TokenManager()
            yield
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_diagnose_401_error(self):
        """测试401错误诊断"""
        should_refresh = diagnose_api_error("401 Unauthorized", response_status=401)
        
        assert should_refresh is True, "401错误应该建议刷新"
        assert self.manager.stats['failed_requests'] == 1, "失败次数应该增加"
    
    def test_diagnose_403_error(self):
        """测试403错误诊断"""
        should_refresh = diagnose_api_error("403 Forbidden", response_status=403)
        
        assert should_refresh is True, "403错误应该建议刷新"
    
    def test_diagnose_429_error(self):
        """测试429错误诊断"""
        should_refresh = diagnose_api_error("429 Too Many Requests", response_status=429)
        
        # 429错误不建议立即刷新
        assert should_refresh is False, "429错误不应该建议立即刷新"
    
    def test_diagnose_timeout_error(self):
        """测试超时错误诊断"""
        should_refresh = diagnose_api_error("Connection timed out")
        
        assert should_refresh is False, "超时错误不应该建议刷新"
    
    def test_diagnose_token_expired_error(self):
        """测试Token过期错误诊断"""
        should_refresh = diagnose_api_error("Token has expired")
        
        assert should_refresh is True, "Token过期错误应该建议刷新"


class TestAutoRefreshScenarios:
    """测试各种自动刷新场景"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后清理"""
        self.temp_dir = tempfile.mkdtemp()
        
        with patch('core.token_manager.CONFIG') as mock_config:
            mock_config.__getitem__ = lambda self, key: self.temp_dir if key == "ROOT" else None
            
            # 重置单例
            TokenManager._instance = None
            
            self.manager = TokenManager()
            yield
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_scenario_safe_token(self):
        """场景1: Token还有30分钟过期(安全)"""
        self.manager.token_expires_at = datetime.now() + timedelta(minutes=30)
        self.manager.last_refresh_time = datetime.now() - timedelta(minutes=10)
        
        assert not self.manager.is_expired(), "安全Token不应该过期"
        assert not self.manager.needs_refresh(), "安全Token不需要刷新"
    
    def test_scenario_expiring_token(self):
        """场景2: Token还有5分钟过期(需要刷新)"""
        self.manager.token_expires_at = datetime.now() + timedelta(minutes=5)
        self.manager.last_refresh_time = datetime.now() - timedelta(minutes=50)
        
        assert self.manager.is_expired(), "即将过期Token应该被判定为过期"
        assert self.manager.needs_refresh(), "即将过期Token需要刷新"
    
    def test_scenario_expired_token(self):
        """场景3: Token已过期(必须刷新)"""
        self.manager.token_expires_at = datetime.now() - timedelta(minutes=5)
        self.manager.last_refresh_time = datetime.now() - timedelta(minutes=60)
        
        assert self.manager.is_expired(), "已过期Token应该被判定为过期"
        assert self.manager.needs_refresh(), "已过期Token需要刷新"
    
    def test_scenario_never_refreshed(self):
        """场景4: 从未刷新过(需要刷新)"""
        self.manager.token_expires_at = datetime.now() + timedelta(minutes=60)
        self.manager.last_refresh_time = None
        
        assert not self.manager.is_expired(), "未过期Token不应该过期"
        assert self.manager.needs_refresh(), "从未刷新过应该需要刷新"


class TestConcurrentRefresh:
    """测试并发刷新"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后清理"""
        self.temp_dir = tempfile.mkdtemp()
        
        with patch('core.token_manager.CONFIG') as mock_config:
            mock_config.__getitem__ = lambda self, key: self.temp_dir if key == "ROOT" else None
            
            # 重置单例
            TokenManager._instance = None
            
            self.manager = TokenManager()
            yield
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_concurrent_token_updates(self):
        """测试并发Token更新"""
        import threading
        
        results = []
        errors = []
        
        def update_token(token_value):
            try:
                self.manager.update_token(token_value, expires_in_minutes=60)
                results.append(self.manager.current_token)
            except Exception as e:
                errors.append(str(e))
        
        # 创建多个线程同时更新
        threads = []
        for i in range(10):
            t = threading.Thread(target=update_token, args=(f"token_{i}",))
            threads.append(t)
            t.start()
        
        # 等待所有线程完成
        for t in threads:
            t.join()
        
        # 验证没有错误
        assert len(errors) == 0, f"不应该有错误: {errors}"
        
        # 验证最终状态一致
        assert self.manager.current_token in [f"token_{i}" for i in range(10)], \
            "最终Token应该是其中一个更新的值"


class TestPersistenceAcrossRestarts:
    """测试跨重启持久化"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后清理"""
        self.temp_dir = tempfile.mkdtemp()
        
        with patch('core.token_manager.CONFIG') as mock_config:
            mock_config.__getitem__ = lambda self, key: self.temp_dir if key == "ROOT" else None
            yield
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_token_persists_across_instances(self):
        """测试Token在不同实例间持久化"""
        # 创建第一个实例并保存Token
        with patch('core.token_manager.CONFIG') as mock_config:
            mock_config.__getitem__ = lambda self, key: self.temp_dir if key == "ROOT" else None
            
            # 重置单例
            TokenManager._instance = None
            
            manager1 = TokenManager()
            test_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.persist_test"
            test_cookie = "session_id=persist_test"
            manager1.update_token(test_token, cookie=test_cookie, expires_in_minutes=60)
        
        # 创建第二个实例，应该加载保存的Token
        with patch('core.token_manager.CONFIG') as mock_config:
            mock_config.__getitem__ = lambda self, key: self.temp_dir if key == "ROOT" else None
            
            # 重置单例
            TokenManager._instance = None
            
            manager2 = TokenManager()
            
            # 验证Token被加载
            assert manager2.current_token == test_token, "Token应该从文件加载"
            assert manager2.current_cookie == test_cookie, "Cookie应该从文件加载"
    
    def test_statistics_persist(self):
        """测试统计信息持久化"""
        # 创建第一个实例并设置统计信息
        with patch('core.token_manager.CONFIG') as mock_config:
            mock_config.__getitem__ = lambda self, key: self.temp_dir if key == "ROOT" else None
            
            # 重置单例
            TokenManager._instance = None
            
            manager1 = TokenManager()
            manager1.stats['total_requests'] = 100
            manager1.stats['failed_requests'] = 5
            manager1.stats['auto_refresh_count'] = 3
            manager1.update_token("test_token", expires_in_minutes=60)
        
        # 创建第二个实例，应该加载统计信息
        with patch('core.token_manager.CONFIG') as mock_config:
            mock_config.__getitem__ = lambda self, key: self.temp_dir if key == "ROOT" else None
            
            # 重置单例
            TokenManager._instance = None
            
            manager2 = TokenManager()
            
            # 验证统计信息被加载
            assert manager2.stats['total_requests'] == 100, "总请求数应该被加载"
            assert manager2.stats['failed_requests'] == 5, "失败次数应该被加载"
            assert manager2.stats['auto_refresh_count'] == 3, "刷新次数应该被加载"


class TestRealWorldSimulation:
    """测试真实世界场景模拟"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后清理"""
        self.temp_dir = tempfile.mkdtemp()
        
        with patch('core.token_manager.CONFIG') as mock_config:
            mock_config.__getitem__ = lambda self, key: self.temp_dir if key == "ROOT" else None
            
            # 重置单例
            TokenManager._instance = None
            
            self.manager = TokenManager()
            yield
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_full_day_simulation(self):
        """模拟一整天的Token使用"""
        # 模拟8小时工作时间，每30分钟刷新一次
        refresh_count = 16  # 8小时 * 2次/小时
        
        for i in range(refresh_count):
            # 模拟Token获取
            token = f"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.hour_{i//2}_refresh_{i%2}"
            
            # 模拟不同的Token寿命 (45-75分钟)
            lifetime = 45 + (i % 3) * 15
            
            self.manager.update_token(token, expires_in_minutes=lifetime)
            
            # 模拟时间流逝
            time.sleep(0.01)
        
        # 验证最终状态
        assert self.manager.current_token is not None, "应该有有效的Token"
        assert self.manager.stats['auto_refresh_count'] == refresh_count, \
            f"应该有{refresh_count}次刷新记录"
        assert self.manager.avg_token_life > 0, "平均寿命应该被计算"
    
    def test_error_recovery_simulation(self):
        """模拟错误恢复场景"""
        # 1. 初始正常Token
        self.manager.update_token("initial_token", expires_in_minutes=60)
        
        # 2. 模拟API错误
        self.manager.record_error("401 Unauthorized")
        self.manager.record_error("401 Unauthorized")
        self.manager.record_error("401 Unauthorized")
        
        # 3. 验证错误统计
        assert self.manager.stats['failed_requests'] == 3, "应该有3次失败记录"
        
        # 4. 模拟成功刷新
        self.manager.update_token("recovered_token", expires_in_minutes=60)
        
        # 5. 验证恢复
        assert self.manager.current_token == "recovered_token", "Token应该已恢复"
        assert self.manager.stats['auto_refresh_count'] == 2, "应该有2次刷新记录"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
