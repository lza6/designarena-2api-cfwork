import os
import sys

# Add project root to sys.path
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from core.browser import PlaywrightManager
from core.token_manager import get_token_manager
from loguru import logger

logger.add("sys.stdout", level="DEBUG")

def success_callback(token, cookie):
    print(f"\n[SUCCESS CALLBACK] Token captured!\nToken: {token[:20]}...\nCookie: {cookie[:20] if cookie else None}...\n")

if __name__ == "__main__":
    print("Testing PlaywrightManager launch_refresh")
    acc_id = "test_refresh_acc"
    pm = PlaywrightManager(acc_id)
    pm.launch_refresh(success_callback)
    
    print("\n[INFO] Refresh flow completed. Checking TokenManager status:")
    tm = get_token_manager()
    print(tm.get_status_report())
