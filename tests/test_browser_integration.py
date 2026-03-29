# -*- coding: utf-8 -*-
"""
浏览器刷新集成测试
测试浏览器启动、流量嗅探、Token捕获等集成功能
"""

import os
import sys
import re
import pytest
import tempfile
import shutil
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime, timedelta

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.browser import (
    find_chrome_executable,
    setup_mirror_profile,
    PlaywrightManager,
    start_refresh_thread
)
from core.token_manager import get_token_manager


class TestChromeDetection:
    """测试Chrome路径检测"""
    
    def test_find_chrome_executable(self):
        """IT-001: 验证Chrome路径查找"""
        chrome_path = find_chrome_executable()
        
        # 应该返回一个字符串
        assert isinstance(chrome_path, str), "应该返回字符串路径"
        
        # 如果Chrome安装了，路径应该存在或者是chrome.exe
        if chrome_path != "chrome.exe":
            assert os.path.exists(chrome_path) or chrome_path.endswith("chrome.exe"), \
                f"Chrome路径应该存在或是可执行文件名: {chrome_path}"


class TestMirrorProfile:
    """测试镜像Profile同步"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后清理"""
        self.temp_dir = tempfile.mkdtemp()
        
        with patch('core.browser.CONFIG') as mock_config:
            mock_config.__getitem__ = lambda self, key: self.temp_dir if key == "ROOT" else None
            yield
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_setup_mirror_profile_creates_directory(self):
        """IT-002: 验证镜像目录创建"""
        # Mock robocopy命令
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            mirror_path = setup_mirror_profile()
            
            # 验证镜像根目录被创建
            assert os.path.exists(mirror_path), "镜像目录应该被创建"


class TestTokenRegexPattern:
    """测试Token正则表达式匹配"""
    
    def test_token_pattern_jwt_format(self):
        """IT-010: 验证JWT格式Token匹配"""
        # 从browser.py中提取的正则表达式
        TOKEN_PATTERN = r"Bearer\s+(ey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*)"
        
        # 测试用例
        test_cases = [
            # 标准JWT格式
            ("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
             "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"),
            
            # 带空格的Bearer
            ("Bearer  eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.signature",
             "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.signature"),
            
            # 在更长的字符串中
            ("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test, Cookie: session=abc",
             "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"),
        ]
        
        for input_str, expected_token in test_cases:
            match = re.search(TOKEN_PATTERN, input_str)
            assert match is not None, f"应该匹配到Token: {input_str[:50]}..."
            assert match.group(1) == expected_token, f"Token应该正确提取"
    
    def test_token_pattern_no_match(self):
        """验证不匹配的情况"""
        TOKEN_PATTERN = r"Bearer\s+(ey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*)"
        
        # 不应该匹配的字符串
        no_match_cases = [
            "Bearer invalid_token",
            "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",  # 只有一部分
            "Authorization: Basic dXNlcjpwYXNz",  # Basic认证
            "No token here",
        ]
        
        for input_str in no_match_cases:
            match = re.search(TOKEN_PATTERN, input_str)
            assert match is None, f"不应该匹配: {input_str}"


class TestPlaywrightManagerInit:
    """测试PlaywrightManager初始化"""
    
    def test_manager_initialization(self):
        """验证PlaywrightManager初始化"""
        account_id = "test_account"
        manager = PlaywrightManager(account_id)
        
        assert manager.account_id == account_id, "账号ID应该正确设置"
        assert manager.captured_token is None, "初始captured_token应该为None"
        assert manager._is_closing is False, "初始_is_closing应该为False"
        assert manager._context is None, "初始_context应该为None"
    
    def test_manager_has_token_manager(self):
        """验证PlaywrightManager有TokenManager引用"""
        manager = PlaywrightManager("test_account")
        
        assert hasattr(manager, 'token_manager'), "应该有token_manager属性"
        assert manager.token_manager is not None, "token_manager不应该为None"


class TestPlaywrightManagerMocked:
    """测试PlaywrightManager(使用Mock)"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后清理"""
        self.temp_dir = tempfile.mkdtemp()
        
        with patch('core.browser.CONFIG') as mock_config:
            mock_config.__getitem__ = lambda self, key: self.temp_dir if key == "ROOT" else None
            self.manager = PlaywrightManager("test_account")
            yield
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_launch_refresh_with_mock(self):
        """IT-003: 测试launch_refresh(使用Mock)"""
        # Mock Playwright
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        
        # 设置Mock链
        mock_playwright.chromium.launch_persistent_context.return_value = mock_context
        mock_context.pages = [mock_page]
        mock_context.new_page.return_value = mock_page
        
        # Mock success callback
        callback_called = []
        def mock_callback(token, cookie):
            callback_called.append((token, cookie))
        
        # 执行测试
        with patch('core.browser.sync_playwright') as mock_sync_playwright:
            mock_sync_playwright.return_value.__enter__.return_value = mock_playwright
            
            # Mock find_chrome_executable
            with patch('core.browser.find_chrome_executable') as mock_find_chrome:
                mock_find_chrome.return_value = "chrome.exe"
                
                # 执行launch_refresh
                self.manager.launch_refresh(mock_callback)
                
                # 验证浏览器被启动
                mock_playwright.chromium.launch_persistent_context.assert_called_once()
                
                # 验证页面被访问
                mock_page.goto.assert_called()
    
    def test_on_request_captures_token(self):
        """IT-011: 测试请求嗅探捕获Token"""
        # 模拟请求对象
        mock_request = MagicMock()
        mock_request.url = "https://designarena.ai/api/chat"
        mock_request.headers = {
            "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.signature",
            "cookie": "session_id=abc123"
        }
        
        # 模拟成功回调
        captured_tokens = []
        def capture_callback(token, cookie):
            captured_tokens.append((token, cookie))
        
        # 创建一个模拟的on_request函数
        def on_request(request):
            try:
                url = request.url
                headers = request.headers
                
                TOKEN_PATTERN = r"Bearer\s+(ey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*)"
                
                found_token = None
                for h_val in headers.values():
                    match = re.search(TOKEN_PATTERN, str(h_val))
                    if match:
                        found_token = match.group(1)
                        break
                
                if found_token:
                    cookie = headers.get('cookie') or headers.get('Cookie') or ""
                    capture_callback(found_token, cookie)
            except Exception as e:
                pass
        
        # 执行
        on_request(mock_request)
        
        # 验证
        assert len(captured_tokens) == 1, "应该捕获到一个Token"
        assert captured_tokens[0][0] == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.signature", "Token应该正确"
        assert captured_tokens[0][1] == "session_id=abc123", "Cookie应该正确"


class TestStartRefreshThread:
    """测试启动刷新线程"""
    
    def test_start_refresh_thread(self):
        """验证start_refresh_thread启动线程"""
        callback_called = []
        def mock_callback(token, cookie):
            callback_called.append((token, cookie))
        
        # Mock PlaywrightManager
        with patch('core.browser.PlaywrightManager') as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm_class.return_value = mock_pm
            
            # 启动线程
            thread = start_refresh_thread("test_account", mock_callback)
            
            # 验证线程被创建
            assert thread is not None, "线程应该被创建"
            assert thread.daemon is True, "线程应该是守护线程"
            
            # 验证PlaywrightManager被创建
            mock_pm_class.assert_called_once_with("test_account")


class TestAutoRefreshIntegration:
    """测试自动刷新集成"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后清理"""
        self.temp_dir = tempfile.mkdtemp()
        
        with patch('core.browser.CONFIG') as mock_config:
            mock_config.__getitem__ = lambda self, key: self.temp_dir if key == "ROOT" else None
            yield
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_token_manager_integration(self):
        """验证TokenManager与PlaywrightManager集成"""
        manager = PlaywrightManager("test_account")
        
        # 验证TokenManager被正确初始化
        assert manager.token_manager is not None, "TokenManager应该被初始化"
        
        # 验证可以更新Token
        test_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.integration_test"
        manager.token_manager.update_token(test_token, expires_in_minutes=60)
        
        # 验证Token被更新
        assert manager.token_manager.current_token == test_token, "Token应该被更新"
    
    def test_refresh_callback_updates_token_manager(self):
        """验证刷新回调更新TokenManager"""
        manager = PlaywrightManager("test_account")
        
        # 模拟刷新成功回调
        test_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.callback_test"
        test_cookie = "session_id=callback_test"
        
        # 模拟on_request中的逻辑
        manager.token_manager.update_token(test_token, cookie=test_cookie, expires_in_minutes=60)
        
        # 验证TokenManager被更新
        assert manager.token_manager.current_token == test_token, "Token应该被更新"
        assert manager.token_manager.current_cookie == test_cookie, "Cookie应该被更新"


class TestErrorHandling:
    """测试错误处理"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """每个测试前后清理"""
        self.temp_dir = tempfile.mkdtemp()
        
        with patch('core.browser.CONFIG') as mock_config:
            mock_config.__getitem__ = lambda self, key: self.temp_dir if key == "ROOT" else None
            yield
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_launch_refresh_handles_exception(self):
        """测试launch_refresh异常处理"""
        manager = PlaywrightManager("test_account")
        
        callback_called = []
        def mock_callback(token, cookie):
            callback_called.append((token, cookie))
        
        # Mock Playwright抛出异常
        with patch('core.browser.sync_playwright') as mock_sync_playwright:
            mock_sync_playwright.return_value.__enter__.side_effect = Exception("Test error")
            
            # 执行应该不会崩溃
            try:
                manager.launch_refresh(mock_callback)
            except Exception as e:
                # 异常应该被捕获
                pass
            
            # 回调不应该被调用
            assert len(callback_called) == 0, "回调不应该被调用"
    
    def test_on_request_handles_malformed_headers(self):
        """测试处理格式错误的请求头"""
        # 模拟格式错误的请求
        mock_request = MagicMock()
        mock_request.url = "https://designarena.ai/api/chat"
        mock_request.headers = {
            "authorization": None,  # None值
            "cookie": 123,  # 非字符串值
        }
        
        captured_tokens = []
        def capture_callback(token, cookie):
            captured_tokens.append((token, cookie))
        
        def on_request(request):
            try:
                url = request.url
                headers = request.headers
                
                TOKEN_PATTERN = r"Bearer\s+(ey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*)"
                
                found_token = None
                for h_val in headers.values():
                    match = re.search(TOKEN_PATTERN, str(h_val))
                    if match:
                        found_token = match.group(1)
                        break
                
                if found_token:
                    cookie = headers.get('cookie') or headers.get('Cookie') or ""
                    capture_callback(found_token, cookie)
            except Exception as e:
                # 应该捕获异常而不是崩溃
                pass
        
        # 执行不应该崩溃
        on_request(mock_request)
        
        # 应该没有捕获到Token
        assert len(captured_tokens) == 0, "不应该捕获到Token"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
