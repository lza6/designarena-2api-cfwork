# -*- coding: utf-8 -*-
"""
DesignArena-2Api 终极原生版
Unified Entry Point
"""
import sys
import os
import logging
from datetime import datetime, timedelta
from PySide6.QtWidgets import QApplication
from ui.main_window import UltimateWindow
from core.token_manager import get_token_manager
from core.logger import logger

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-blink-features=AutomationControlled --force-color-profile=srgb --disable-features=IsolateOrigins,site-per-process --no-sandbox --disable-autofill-keyboard-accessory-view"

def check_and_startup_cleanup():
    """
    v8.0 Industrial Pro: 启动环境核验与清理
    """
    print("\n\033[36m" + "="*60 + "\033[0m")
    print("\033[36m[v8.0] DESIGN.ARENA // INDUSTRIAL PRO ENGINE INITIALIZING...\033[0m")
    print("\033[36m" + "="*60 + "\033[0m\n")
    
    try:
        # 预加载 Token 管理器
        manager = get_token_manager()
        if manager.token_expires_at:
            print(f"\033[37m[TIME] 预载凭证过期时间：{manager.token_expires_at.strftime('%Y-%m-%d %H:%M:%S')}\033[0m")
    except Exception as e:
        logger.error(f"[STARTUP] 初始化预检失败：{e}")

def main():
    # v8.0: 启动集成环境预检
    check_and_startup_cleanup()
    
    # Initialize the Qt Application
    app = QApplication(sys.argv)
    
    # Create and show the main window
    
    # Note: FastAPI server is started inside UltimateWindow.__init__ in a background thread
    window = UltimateWindow()
    window.show()
    
    print("""
  \033[33m#########################################################\033[0m
  \033[33m#                                                       #\033[0m
  \033[33m#    DESIGN.ARENA // 2API PRO // v8.0 INDUSTRIAL PRO     #\033[0m
  \033[33m#                                                       #\033[0m
  \033[33m#########################################################\033[0m
    """)
    # Execute the application loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
