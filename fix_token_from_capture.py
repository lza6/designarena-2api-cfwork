
# -*- coding: utf-8 -*-
"""
从抓包记录恢复有效 Token 和 Cookie
"""

import os
import sys
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.token_manager import get_token_manager

def main():
    print("="*80)
    print("  从抓包记录恢复 Token 和 Cookie")
    print("="*80)
    
    # 从抓包记录中提取的有效数据
    valid_token = "eyJhbGciOiJSUzI1NiIsImtpZCI6IjM3MzAwNzY5YTA3ZTA1MTE2ZjdlNTEzOGZhOTA5MzY4NWVlYmMyNDAiLCJ0eXAiOiJKV1QifQ.eyJuYW1lIjoi5Yip5LuUIiwicGljdHVyZSI6Imh0dHBzOi8vbGgzLmdvb2dsZXVzZXJjb250ZW50LmNvbS9hL0FDZzhvY0t3TVpKWEtNT3MwUl9Bd0hLVUFvX2xKOXBTWm1yeldMVDdfZ1lBZHpDMUliV1lxQT1zOTYtYyIsImlzcyI6Imh0dHBzOi8vc2VjdXJldG9rZW4uZ29vZ2xlLmNvbS9kZXNpZ25hcmVuYS1hOTBjOSIsImF1ZCI6ImRlc2lnbmFyZW5hLWE5MGM5IiwiYXV0aF90aW1lIjoxNzcwNzQxMzAwLCJ1c2VyX2lkIjoia3NrRVpZd1BYcVRneW9kV29pWG9iR0xpR245MiIsInN1YiI6Imtza0VaWXdQWHFUZ3lvZFdvaVhvYkdMaUduOTIiLCJpYXQiOjE3NzQ3MDEwNzgsImV4cCI6MTc3NDcwNDY3OCwiZW1haWwiOiJxMTM2NDU5NDc0MDdAZ21haWwuY29tIiwiZW1haWxfdmVyaWZpZWQiOnRydWUsImZpcmViYXNlIjp7ImlkZW50aXRpZXMiOnsiZ29vZ2xlLmNvbSI6WyIxMDIyMzM4NzE5MjY3NzIyMjQwODkiXSwiZW1haWwiOlsicTEzNjQ1OTQ3NDA3QGdtYWlsLmNvbSJdfSwic2lnbl9pbl9wcm92aWRlciI6Imdvb2dsZS5jb20ifX0.XTAyTu0HQaUAsOWPrN3J-6XO2PjNOu2iN3hgDa6k6ZM_LADhlNBLwGT0Q-VZOXCIfZAhnGw9bLuh6ySVL9sKNUKAvf0vjvqDz2hKdcgjz_Rtzdvlb2vLrDLgieSZzsZod--qy5ZCHd6Kc4tnKWCdqjYkYRlDT2iFt5O2JTBHK1LauO74g-lm9pLytydBOp0GKOsKazIGtwDUveTsMpHvEOMGCzRWB21yswZ-pNJ5b_cXhfHNNem5Y0NLzXfnEfrDT80E1eIyKs3fCw9pbLek2yNUHaW-2KV7J-UnaRawLlq_ErjtQ8Ge6Ld6YydkqYqug-ZDsRO6m1kF36-gUiIOXw"
    
    valid_cookie = "_ga=GA1.1.498965500.1765977860; NEXT_LOCALE=zh; NEXT_TIMEZONE=Asia/Shanghai; _ga_8YBN2LD1WG=GS2.1.s1774701052$o24$g0$t1774701052$j60$l0$h0; _gcl_au=1.1.506033947.1774701053; _ga_YNTFBNE29J=GS2.1.s1774701053$o27$g0$t1774701053$j60$l0$h0; ph_phc_i6iFf7vuaXs59sLohA9hgYK3mOQWEYDEo3qLsXktpGz_posthog=%7B%22%24device_id%22%3A%22019b2c7b-a884-7e5e-a8e7-5dfaa85480e0%22%2C%22distinct_id%22%3A%22kskEZYwPXqTgyodWoiXobGLiGn92%22%2C%22%24sesid%22%3A%5B1774701104626%2C%22019d346d-012a-75f4-bb86-60537ed2b0f9%22%2C1774701052199%5D%2C%22%24epp%22%3Atrue%2C%22%24initial_person_info%22%3A%7B%22r%22%3A%22https%3A%2F%2Fwww.nodeloc.com%2F%22%2C%22u%22%3A%22https%3A%2F%2Fwww.designarena.ai%2F%22%7D%2C%22%24user_state%22%3A%22identified%22%7D"
    
    print(f"\n[输入] Token 长度: {len(valid_token)}")
    print(f"[输入] Cookie 长度: {len(valid_cookie)}")
    
    # 获取 TokenManager
    tm = get_token_manager()
    
    # 更新 Token（设置为 60 分钟过期）
    tm.update_token(valid_token, valid_cookie, expires_in_minutes=60)
    
    print(f"\n✅ Token 和 Cookie 已成功更新!")
    print(f"\n当前 Token 状态:")
    print(tm.get_status_report())
    
    # 保存到文件
    tm.save_to_files()
    
    print(f"\n✅ 凭证已保存到文件")
    print("="*80)
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

