
# -*- coding: utf-8 -*-
"""
手动启动登录流程 - 打开浏览器让用户登录，自动捕获 Token
"""

import os
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.browser import PlaywrightManager
from core.token_manager import get_token_manager
from core.config import CONFIG
from loguru import logger

def success_callback(token, cookie):
    print(f"\n{'='*80}")
    print(f"✅ 成功捕获 Token 和 Cookie!")
    print(f"{'='*80}")
    print(f"\nToken 前缀: {token[:50]}...")
    print(f"Cookie 长度: {len(cookie) if cookie else 0}")
    print(f"\n正在保存到文件...")

if __name__ == "__main__":
    print("="*80)
    print("  DesignArena 手动登录工具")
    print("="*80)
    print("\n说明:")
    print("1. 浏览器窗口将自动打开")
    print("2. 请在浏览器中登录您的 DesignArena 账号")
    print("3. 登录成功后，系统会自动捕获 Token 和 Cookie")
    print("4. 捕获完成后浏览器会自动关闭")
    print("\n" + "="*80)
    
    # 先清除旧的 Token，强制重新登录
    print("\n⚠️  正在清除旧的 Token...")
    tm = get_token_manager()
    tm.current_token = None
    tm.current_cookie = None
    tm.token_expires_at = None
    
    # 清除保存的文件
    auth_dir = os.path.join(CONFIG["ROOT"], "data", "auth")
    if os.path.exists(auth_dir):
        for f in ["captured_token.txt", "captured_cookie.txt", "token_cache.json"]:
            fp = os.path.join(auth_dir, f)
            if os.path.exists(fp):
                try:
                    os.remove(fp)
                    print(f"   已删除: {f}")
                except:
                    pass
    
    print("\n自动继续...")
    
    acc_id = "manual_login_acc"
    pm = PlaywrightManager(acc_id)
    
    print("\n🚀 正在启动浏览器...")
    pm.launch_login(success_callback)
    
    print("\n" + "="*80)
    print("  登录流程完成!")
    print("="*80)
    
    tm = get_token_manager()
    print("\n当前 Token 状态:")
    print(tm.get_status_report())

