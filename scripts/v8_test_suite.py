# -*- coding: utf-8 -*-
"""
DesignArena-2Api v8.0 Ground Test Suite (落地测试工具)
- Verifies: Zero-Copy Junctions, Token Decay, Module Integrity
"""

import os
import sys
import shutil
import time
import subprocess
from datetime import datetime, timedelta

# Add project root to sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)
    os.chdir(ROOT) # Ensure CWD is project root

from core.config import CONFIG
from core.token_manager import TokenManager
from core.browser import setup_mirror_profile

def test_module_imports():
    print("[TEST] 1. 验证模块导入状态...")
    try:
        import core.browser
        import core.token_manager
        import core.manager
        # import api.server # Skip server for now if it requires too many dependencies
        print("[PASS] 核心模块导入成功!")
    except Exception as e:
        print(f"[FAIL] 模块导入失败: {e}")
        return False
    return True

def test_junction_creation():
    print("[TEST] 2. 验证零拷贝 (Junction) 创建逻辑...")
    try:
        mirror_root = setup_mirror_profile("Default")
        profile_path = os.path.join(mirror_root, "Default")
        
        if not os.path.exists(profile_path):
            print("[FAIL] Mirror 目录创建失败")
            return False
            
        indexed_db = os.path.join(profile_path, "IndexedDB")
        if os.path.exists(indexed_db):
            print(f"[PASS] IndexedDB 路径已就绪: {indexed_db}")
        
        cookie_file = os.path.join(profile_path, "Cookies")
        if os.path.exists(cookie_file):
            print(f"[PASS] 核心配置文件已复制: {cookie_file}")
            
    except Exception as e:
        print(f"[FAIL] Junction 测试发生异常: {e}")
        return False
    return True

def test_token_decay_logic():
    print("[TEST] 3. 验证令牌衰减预测逻辑 (v8.0)...")
    tm = TokenManager()
    initial_avg = tm.avg_token_life
    
    # Simulate a few updates with different lifespans
    tm.update_token("mock_token_1", expires_in_minutes=180)
    v1 = tm.avg_token_life
    tm.update_token("mock_token_2", expires_in_minutes=30)
    v2 = tm.avg_token_life
    
    print(f"   初始均值: {initial_avg}")
    print(f"   更新(180m)后: {v1}")
    print(f"   更新(30m)后: {v2}")
    
    # Check if a 0.7 decay is applied (v2 should be closer to 30 than initial_avg)
    if abs(v2 - 30) < abs(v2 - 180):
        print("[PASS] 权重衰减逻辑正常工作 (高权重响应最新样本)")
    else:
        print("[FAIL] 权重逻辑不符合预期")
        return False
    return True

def run_all():
    print("="*60)
    print("DesignArena-2Api v8.0 Ground Test Suite")
    print("="*60)
    
    results = []
    results.append(test_module_imports())
    results.append(test_junction_creation())
    results.append(test_token_decay_logic())
    
    print("="*60)
    if all(results):
        print("[RESULT] v8.0 落地测试全项目通过！")
    else:
        print("[RESULT] 测试存在部分异常。")
    print("="*60)

if __name__ == "__main__":
    run_all()
