
# -*- coding: utf-8 -*-
"""
测试 Token 是否有效
"""

import os
import sys
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.token_manager import get_token_manager

def main():
    print("="*80)
    print("  测试 Token 有效性")
    print("="*80)
    
    # 获取 TokenManager
    tm = get_token_manager()
    
    print(f"\n当前 Token 状态:")
    print(tm.get_status_report())
    
    if not tm.current_token:
        print("\n❌ 没有找到 Token")
        return False
    
    # 准备测试请求
    url = "https://www.designarena.ai/api/chats"
    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "authorization": f"Bearer {tm.current_token}",
        "content-type": "application/json",
        "origin": "https://www.designarena.ai",
        "priority": "u=1, i",
        "referer": "https://www.designarena.ai/",
        "sec-ch-ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
    }
    
    if tm.current_cookie:
        headers["cookie"] = tm.current_cookie
    
    data = {"prompt": "test"}
    
    print(f"\n[测试] 正在发送请求到 {url}...")
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        print(f"\n[响应] 状态码: {response.status_code}")
        print(f"[响应] 响应头: {dict(response.headers)}")
        
        if response.status_code == 200:
            print(f"\n✅ Token 有效! 请求成功!")
            print(f"[响应] 响应内容: {response.text}")
            return True
        elif response.status_code == 401:
            print(f"\n❌ Token 无效! (401 Unauthorized)")
            print(f"[响应] 响应内容: {response.text}")
            return False
        else:
            print(f"\n⚠️ 请求返回状态码 {response.status_code}")
            print(f"[响应] 响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    print("\n" + "="*80)
    sys.exit(0 if success else 1)

