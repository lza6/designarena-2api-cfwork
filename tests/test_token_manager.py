# -*- coding: utf-8 -*-
"""
TokenManager 单元测试
测试自动刷新/自动续杯机制的核心逻辑
"""

import os
import sys
import json
import pytest
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.token_manager import TokenManager, get_token_manager


class TestTokenManagerSingleton:
    """测试TokenManager单例模式"""
    
    def test_singleton_instance(self):
        """UT-001: 验证TokenManager是单例"""
        manager1 = TokenManager()
        manager2 = TokenManager()
        assert manager1 is manager2, "TokenManager应该是单例模式"
    
    def test_get_token_manager(self):
        """验证get_token_manager返回单例"""
        manager1 = get_token_manager()
        manager2 = get_token_manager()
        assert manager1 is manager2, "get_token_manager应该返回同一个实例"


class TestTokenManagerBasic:
    """测试TokenManager基础功能"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后清理"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        self.original_root = None
        
        # Mock CONFIG
        with patch('core.token_manager.CONFIG') as mock_config:
            mock_config.__getitem__ = lambda self, key: self.temp_dir if key == "ROOT" else None
            
            # 创建新的TokenManager实例
            self.manager = TokenManager()
            yield
        
        # 清理临时目录
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_update_token(self):
        """UT-002: 验证Token更新功能"""
        test_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
        self.manager.update_token(test_token, expires_in_minutes=60)
        
        assert self.manager.current_token == test_token, "Token应该已更新"
        assert self.manager.token_type == "Bearer", "Token类型应该是Bearer"
    
    def test_update_token_with_cookie(self):
        """UT-003: 验证Token和Cookie同时更新"""
        test_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
        test_cookie = "session_id=abc123; user_token=xyz789"
        
        self.manager.update_token(test_token, cookie=test_cookie, expires_in_minutes=60)
        
        assert self.manager.current_token == test_token, "Token应该已更新"
        assert self.manager.current_cookie == test_cookie, "Cookie应该已更新"
    
    def test_get_auth_header_with_token(self):
        """UT-004: 验证生成认证头(包含Token)"""
        test_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
        self.manager.update_token(test_token, expires_in_minutes=60)
        
        headers = self.manager.get_auth_header()
        
        assert "Authorization" in headers, "应该包含Authorization头"
        assert headers["Authorization"] == f"Bearer {test_token}", "Authorization头格式应该正确"
    
    def test_get_auth_header_with_cookie(self):
        """验证生成认证头(包含Cookie)"""
        test_cookie = "session_id=abc123; user_token=xyz789"
        self.manager.update_token("test_token", cookie=test_cookie, expires_in_minutes=60)
        
        headers = self.manager.get_auth_header()
        
        assert "Cookie" in headers, "应该包含Cookie头"
        assert headers["Cookie"] == test_cookie, "Cookie头应该正确"
    
    def test_get_auth_header_with_both(self):
        """验证生成认证头(同时包含Token和Cookie)"""
        test_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
        test_cookie = "session_id=abc123"
        
        self.manager.update_token(test_token, cookie=test_cookie, expires_in_minutes=60)
        headers = self.manager.get_auth_header()
        
        assert "Authorization" in headers, "应该包含Authorization头"
        assert "Cookie" in headers, "应该包含Cookie头"


class TestTokenExpiryDetection:
    """测试Token过期检测逻辑"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后清理"""
        self.temp_dir = tempfile.mkdtemp()
        
        with patch('core.token_manager.CONFIG') as mock_config:
            mock_config.__getitem__ = lambda self, key: self.temp_dir if key == "ROOT" else None
            self.manager = TokenManager()
            yield
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_token_not_expired(self):
        """UT-010: Token还有30分钟过期(安全)"""
        self.manager.token_expires_at = datetime.now() + timedelta(minutes=30)
        self.manager.last_refresh_time = datetime.now() - timedelta(minutes=10)
        
        assert not self.manager.is_expired(), "Token不应该被判定为过期"
    
    def test_token_expiring_soon(self):
        """UT-011: Token还有5分钟过期(需要刷新)"""
        self.manager.token_expires_at = datetime.now() + timedelta(minutes=5)
        self.manager.last_refresh_time = datetime.now() - timedelta(minutes=50)
        
        # 提前10分钟认为过期
        assert self.manager.is_expired(), "Token应该被判定为即将过期"
    
    def test_token_already_expired(self):
        """UT-012: Token已过期"""
        self.manager.token_expires_at = datetime.now() - timedelta(minutes=5)
        self.manager.last_refresh_time = datetime.now() - timedelta(minutes=60)
        
        assert self.manager.is_expired(), "Token应该被判定为已过期"
    
    def test_token_no_expiry_time(self):
        """UT-013: 没有设置过期时间"""
        self.manager.token_expires_at = None
        
        assert not self.manager.is_expired(), "没有过期时间时不应该判定为过期"


class TestSmartRefreshLogic:
    """测试智能刷新判断逻辑"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后清理"""
        self.temp_dir = tempfile.mkdtemp()
        
        with patch('core.token_manager.CONFIG') as mock_config:
            mock_config.__getitem__ = lambda self, key: self.temp_dir if key == "ROOT" else None
            self.manager = TokenManager()
            yield
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_never_refreshed(self):
        """UT-020: 从未刷新过"""
        self.manager.last_refresh_time = None
        
        assert self.manager.needs_refresh(), "从未刷新过时应该需要刷新"
    
    def test_safe_refresh_point(self):
        """UT-021: 基于平均寿命计算安全刷新点"""
        # 设置平均寿命为60分钟
        self.manager.avg_token_life = 60.0
        # 上次刷新是36分钟前 (60 * 0.6 = 36)
        self.manager.last_refresh_time = datetime.now() - timedelta(minutes=36)
        
        assert self.manager.needs_refresh(), "到达安全刷新点时应该需要刷新"
    
    def test_no_need_refresh(self):
        """UT-022: 刚刷新不久"""
        self.manager.avg_token_life = 60.0
        # 上次刷新是10分钟前
        self.manager.last_refresh_time = datetime.now() - timedelta(minutes=10)
        
        assert not self.manager.needs_refresh(), "刚刷新不久时不应该需要刷新"
    
    def test_weighted_average_calculation(self):
        """UT-023: 验证加权衰减算法"""
        # 初始平均寿命
        initial_avg = 60.0
        self.manager.avg_token_life = initial_avg
        
        # 更新Token，设置新的过期时间
        new_expiry_minutes = 45
        self.manager.update_token("test_token", expires_in_minutes=new_expiry_minutes)
        
        # 计算预期的加权平均值
        # decay = 0.7
        # new_avg = (old_avg * (1 - decay)) + (new_value * decay)
        expected_avg = (initial_avg * 0.3) + (new_expiry_minutes * 0.7)
        
        assert abs(self.manager.avg_token_life - expected_avg) < 0.01, \
            f"平均寿命应该使用加权衰减算法计算，预期{expected_avg}，实际{self.manager.avg_token_life}"


class TestFilePersistence:
    """测试文件持久化功能"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后清理"""
        self.temp_dir = tempfile.mkdtemp()
        
        with patch('core.token_manager.CONFIG') as mock_config:
            mock_config.__getitem__ = lambda self, key: self.temp_dir if key == "ROOT" else None
            self.manager = TokenManager()
            yield
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_save_token_to_file(self):
        """UT-030: 验证Token保存到文件"""
        test_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
        self.manager.update_token(test_token, expires_in_minutes=60)
        
        # 检查文件是否存在
        assert os.path.exists(self.manager.token_file), "Token文件应该存在"
        
        # 检查文件内容
        with open(self.manager.token_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert test_token in content, "文件应该包含Token"
    
    def test_save_cookie_to_file(self):
        """验证Cookie保存到文件"""
        test_cookie = "session_id=abc123; user_token=xyz789"
        self.manager.update_token("test_token", cookie=test_cookie, expires_in_minutes=60)
        
        assert os.path.exists(self.manager.cookie_file), "Cookie文件应该存在"
        
        with open(self.manager.cookie_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert test_cookie in content, "文件应该包含Cookie"
    
    def test_save_cache_to_file(self):
        """UT-032: 验证统计信息保存到缓存文件"""
        # 设置一些统计信息
        self.manager.stats['total_requests'] = 100
        self.manager.stats['failed_requests'] = 5
        self.manager.stats['auto_refresh_count'] = 3
        
        self.manager.update_token("test_token", expires_in_minutes=60)
        
        # 检查缓存文件
        assert os.path.exists(self.manager.cache_file), "缓存文件应该存在"
        
        with open(self.manager.cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
            assert 'stats' in cache_data, "缓存应该包含统计信息"
            assert cache_data['stats']['total_requests'] == 100, "统计信息应该正确"
    
    def test_load_token_from_file(self):
        """UT-031: 验证从文件加载Token"""
        test_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.load_test"
        
        # 手动写入Token文件
        with open(self.manager.token_file, 'w', encoding='utf-8') as f:
            f.write(f"Bearer {test_token}\n")
        
        # 重新加载
        self.manager.load_from_files()
        
        assert self.manager.current_token == test_token, "Token应该从文件加载"
    
    def test_load_history_from_file(self):
        """UT-033: 验证历史记录加载"""
        # 手动写入缓存文件
        cache_data = {
            'expiry_history': [45.0, 50.0, 55.0],
            'avg_token_life': 50.0
        }
        with open(self.manager.cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f)
        
        # 重新加载
        self.manager.load_from_files()
        
        assert len(self.manager.expiry_history) == 3, "历史记录应该加载"
        assert self.manager.avg_token_life == 50.0, "平均寿命应该加载"


class TestStatistics:
    """测试统计功能"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后清理"""
        self.temp_dir = tempfile.mkdtemp()
        
        with patch('core.token_manager.CONFIG') as mock_config:
            mock_config.__getitem__ = lambda self, key: self.temp_dir if key == "ROOT" else None
            self.manager = TokenManager()
            yield
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_record_error(self):
        """验证错误记录功能"""
        initial_failed = self.manager.stats['failed_requests']
        
        self.manager.record_error("Test error")
        
        assert self.manager.stats['failed_requests'] == initial_failed + 1, "失败次数应该增加"
        assert self.manager.stats['last_error'] == "Test error", "最后错误应该记录"
    
    def test_auto_refresh_count(self):
        """验证自动刷新计数"""
        initial_count = self.manager.stats['auto_refresh_count']
        
        self.manager.update_token("test_token", expires_in_minutes=60)
        
        assert self.manager.stats['auto_refresh_count'] == initial_count + 1, "自动刷新次数应该增加"
    
    def test_status_report(self):
        """验证状态报告生成"""
        self.manager.update_token("test_token", expires_in_minutes=60)
        
        report = self.manager.get_status_report()
        
        assert "Token 管理器状态报告" in report, "报告应该包含标题"
        assert "Token 状态" in report, "报告应该包含Token状态"
        assert "统计信息" in report, "报告应该包含统计信息"


class TestEdgeCases:
    """测试边界情况"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后清理"""
        self.temp_dir = tempfile.mkdtemp()
        
        with patch('core.token_manager.CONFIG') as mock_config:
            mock_config.__getitem__ = lambda self, key: self.temp_dir if key == "ROOT" else None
            self.manager = TokenManager()
            yield
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_minimum_refresh_interval(self):
        """测试最小刷新间隔"""
        # 设置平均寿命为10分钟
        self.manager.avg_token_life = 10.0
        # 安全刷新点应该是 max(5, 10*0.6) = 6分钟
        self.manager.last_refresh_time = datetime.now() - timedelta(minutes=6)
        
        assert self.manager.needs_refresh(), "到达最小刷新间隔时应该需要刷新"
    
    def test_very_short_token_life(self):
        """测试非常短的Token寿命"""
        self.manager.avg_token_life = 3.0
        # 安全刷新点应该是 max(5, 3*0.6) = 5分钟
        self.manager.last_refresh_time = datetime.now() - timedelta(minutes=5)
        
        assert self.manager.needs_refresh(), "非常短的Token寿命时应该需要刷新"
    
    def test_concurrent_updates(self):
        """测试并发更新(通过锁机制)"""
        import threading
        
        results = []
        
        def update_token(token_value):
            self.manager.update_token(token_value, expires_in_minutes=60)
            results.append(self.manager.current_token)
        
        # 创建多个线程同时更新
        threads = []
        for i in range(5):
            t = threading.Thread(target=update_token, args=(f"token_{i}",))
            threads.append(t)
            t.start()
        
        # 等待所有线程完成
        for t in threads:
            t.join()
        
        # 验证最终状态一致
        assert self.manager.current_token in [f"token_{i}" for i in range(5)], \
            "最终Token应该是其中一个更新的值"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
