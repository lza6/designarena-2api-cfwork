# -*- coding: utf-8 -*-
"""
从已保存的 Token 恢复账号到账号矩阵
"""

import os
import sys
from datetime import datetime, timedelta

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.token_manager import get_token_manager
from core.manager import GlobalState

def main():
    print("="*80)
    print("  从 Token 恢复账号")
    print("="*80)
    
    # 加载 TokenManager
    tm = get_token_manager()
    
    print(f"\n[检查] Token 状态:")
    print(f"  Token 存在: {tm.current_token is not None}")
    print(f"  Cookie 存在: {tm.current_cookie is not None}")
    print(f"  Token 过期: {tm.is_expired()}")
    
    if not tm.current_token:
        print("\n❌ 没有找到保存的 Token，无法恢复账号")
        return False
    
    # 加载 GlobalState
    GlobalState.load()
    
    print(f"\n[检查] 当前账号数量: {len(GlobalState.accounts)}")
    
    # 检查是否已有相同 Token 的账号
    existing = any(a["token"] == tm.current_token for a in GlobalState.accounts)
    
    if existing:
        print("\n✅ 账号已存在于账号矩阵中")
        return True
    
    # 创建新账号
    aid = f"auto_{tm.current_token[:8]}"
    now = datetime.now()
    expiry = (now + timedelta(hours=3)).isoformat()
    
    new_acc = {
        "id": aid,
        "name": f"Unit_{aid[5:]}",
        "token": tm.current_token,
        "cookie": tm.current_cookie,
        "expires_at": expiry,
        "last_refresh": now.isoformat(),
        "browser_data_path": f"data/browser_sessions/{aid}",
        "is_active": True,
        "total_calls": 0
    }
    
    GlobalState.accounts.append(new_acc)
    GlobalState.active_account_id = aid
    GlobalState.active_token = tm.current_token
    if tm.current_cookie:
        GlobalState.active_cookie = tm.current_cookie
    
    # 保存
    GlobalState.save()
    
    print(f"\n✅ 账号已成功恢复!")
    print(f"  账号ID: {aid}")
    print(f"  账号名称: {new_acc['name']}")
    print(f"  Token 前缀: {tm.current_token[:30]}...")
    print(f"  过期时间: {expiry}")
    print(f"\n  总账号数: {len(GlobalState.accounts)}")
    
    print("\n" + "="*80)
    print("  完成! 请重启应用以查看账号")
    print("="*80)
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
