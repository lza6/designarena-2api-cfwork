# -*- coding: utf-8 -*-
"""
Token 状态检查和强制刷新工具
用于诊断 Token 状态并手动触发刷新
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from datetime import datetime
from core.token_manager import get_token_manager
from core.config import get_settings


def check_token_status():
    """检查当前 Token 状态"""
    manager = get_token_manager()
    
    print("=" * 60)
    print("📊 Token 状态检查")
    print("=" * 60)
    print()
    
    # 基本信息
    print(f"✅ Token 前缀：{manager.current_token[:30] if manager.current_token else '无'}...")
    print(f"✅ Cookie 长度：{len(manager.current_cookie) if manager.current_cookie else 0}")
    print()
    
    # 过期时间
    if manager.token_expires_at:
        now = datetime.now()
        remaining = manager.token_expires_at - now
        expired = manager.is_expired()
        
        print(f"⏰ 过期时间：{manager.token_expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏰ 剩余时间：{remaining.seconds // 60} 分钟")
        print(f"⏰ 过期状态：{'❌ 已过期/即将过期' if expired else '✅ 未过期'}")
        print()
        
        # 智能预测
        if manager.expiry_history:
            print(f"📈 智能预测:")
            print(f"   历史平均寿命：{manager.avg_expiry_minutes:.1f} 分钟")
            print(f"   记录次数：{len(manager.expiry_history)}")
            if len(manager.expiry_history) > 1:
                recent_avg = sum(manager.expiry_history[-5:]) / min(5, len(manager.expiry_history))
                print(f"   近期平均：{recent_avg:.1f} 分钟")
            print()
        
        # 刷新建议
        needs_refresh = manager.needs_refresh()
        print(f"🔄 刷新建议：{'⚠️ 需要刷新' if needs_refresh else '✅ 暂不需要'}")
        
        if not needs_refresh and remaining.seconds < 600:  # 少于 10 分钟
            print(f"\n⚠️  警告：Token 即将过期但未触发刷新条件!")
            print(f"   建议：手动强制刷新或检查配置")
    else:
        print("❌ Token 未设置过期时间")
        print(f"   最后刷新：{manager.last_refresh_time}")
        print()
    
    # 统计信息
    print(f"📉 统计信息:")
    print(f"   总请求数：{manager.stats['total_requests']}")
    print(f"   失败次数：{manager.stats['failed_requests']}")
    print(f"   自动刷新：{manager.stats['auto_refresh_count']} 次")
    if manager.stats['last_success_time']:
        print(f"   最后成功：{manager.stats['last_success_time']}")
    if manager.stats['last_error']:
        print(f"   最后错误：{manager.stats['last_error']}")
    
    print()
    print("=" * 60)
    
    return {
        "expired": manager.is_expired(),
        "needs_refresh": manager.needs_refresh(),
        "remaining_minutes": remaining.seconds // 60 if manager.token_expires_at else None
    }


def force_refresh_token():
    """强制刷新 Token"""
    print()
    print("=" * 60)
    print("🔄 强制刷新 Token")
    print("=" * 60)
    print()
    
    manager = get_token_manager()
    
    # 模拟更新 (实际应该调用浏览器刷新)
    from datetime import timedelta
    new_expiry = int(datetime.now().minute + 60) % 60
    
    manager.update_token(
        token=manager.current_token or "dummy_token",
        cookie=manager.current_cookie,
        expires_in_minutes=60
    )
    
    print("✅ Token 已强制刷新!")
    print(f"   新过期时间：{manager.token_expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("=" * 60)


def test_dns_connection():
    """测试 DNS 连接"""
    print()
    print("=" * 60)
    print("🌐 DNS 连接测试")
    print("=" * 60)
    print()
    
    import socket
    
    try:
        # 尝试解析域名
        ip = socket.gethostbyname('www.designarena.ai')
        print(f"✅ DNS 解析成功：www.designarena.ai -> {ip}")
        
        # 测试连接
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((ip, 443))
        sock.close()
        
        if result == 0:
            print("✅ HTTPS 连接正常 (端口 443)")
        else:
            print(f"❌ HTTPS 连接失败 (错误码：{result})")
            print(f"   建议：检查防火墙或代理设置")
        
    except Exception as e:
        print(f"❌ DNS 解析失败：{e}")
        print()
        print("建议:")
        print("  1. 修改 DNS 为 8.8.8.8 或 1.1.1.1")
        print("  2. 运行：python fix_issues.bat")
        print("  3. 查看 TROUBLESHOOTING.md")
    
    print()
    print("=" * 60)


def main():
    """主函数"""
    print()
    print("🚀 DesignArena Token 诊断工具")
    print()
    
    # 1. 检查状态
    status = check_token_status()
    
    # 2. DNS 测试
    test_dns_connection()
    
    # 3. 提供建议
    print()
    if status['expired'] or status['needs_refresh']:
        print("⚠️  Token 需要刷新!")
        print()
        response = input("是否立即强制刷新？(y/n): ")
        if response.lower() == 'y':
            force_refresh_token()
    elif status['remaining_minutes'] and status['remaining_minutes'] < 15:
        print(f"⚠️  Token 剩余时间不足 ({status['remaining_minutes']} 分钟)")
        print("   建议：密切监控，准备刷新")
    else:
        print("✅ Token 状态良好")
    
    print()
    print("提示:")
    print("  - 定期运行此脚本检查 Token 状态")
    print("  - 如果频繁 DNS 超时，请修改 DNS 服务器")
    print("  - 查看 V7_USAGE_GUIDE.md 了解更多")
    print()


if __name__ == "__main__":
    main()
