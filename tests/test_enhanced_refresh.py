
# -*- coding: utf-8 -*-
"""
测试优化后的 v10.0 静默刷新机制
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.browser import PlaywrightManager
from core.token_manager import get_token_manager
from loguru import logger

def success_callback(token, cookie):
    print(f"\n{'='*80}")
    print(f"✅ 成功刷新 Token 和 Cookie!")
    print(f"{'='*80}")
    print(f"\nToken 前缀: {token[:50]}...")
    print(f"Cookie 长度: {len(cookie) if cookie else 0}")
    print(f"\n正在保存到文件...")

if __name__ == "__main__":
    print("="*80)
    print("  测试 v10.0 增强静默刷新机制")
    print("="*80)
    
    # 先显示当前状态
    tm = get_token_manager()
    print("\n[当前状态] 刷新前:")
    print(tm.get_status_report())
    
    print("\n[开始] 启动增强静默刷新...")
    acc_id = "test_refresh_acc"
    pm = PlaywrightManager(acc_id)
    
    pm.launch_refresh(success_callback)
    
    print("\n" + "="*80)
    print("  刷新流程完成!")
    print("="*80)
    
    print("\n[当前状态] 刷新后:")
    print(tm.get_status_report())
    
    print("\n[测试] 验证 Token 有效性...")
    import requests
    
    url = "https://www.designarena.ai/api/chats"
    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "origin": "https://www.designarena.ai",
        "referer": "https://www.designarena.ai/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    if tm.current_token:
        headers["authorization"] = f"Bearer {tm.current_token}"
    
    if tm.current_cookie:
        headers["cookie"] = tm.current_cookie
    
    data = {"prompt": "test"}
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        print(f"\n[测试结果] 状态码: {response.status_code}")
        if response.status_code == 200:
            print("✅ Token 有效！")
            print(f"响应: {response.text}")
        else:
            print(f"❌ Token 可能有问题")
            print(f"响应: {response.text}")
    except Exception as e:
        print(f"❌ 测试请求失败: {e}")

