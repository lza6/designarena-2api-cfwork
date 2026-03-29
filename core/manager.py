# -*- coding: utf-8 -*-
import json
import os
import base64
from typing import List, Dict, Optional, Any
from PySide6.QtCore import Signal
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings, QWebEngineScript
from core.config import CONFIG
from core.security import encrypt_token, decrypt_token
from core.logger import logger

class ThemeManager:
    DARK: str = """
        /* v8.0 F1 Cockpit - Ultra Premium Dark */
        QMainWindow, QWidget#MainContent { 
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #050510, stop:1 #0A0A25); 
            color: #E0E0E0; 
            font-family: 'Segoe UI', 'Inter', 'Microsoft YaHei'; 
            font-size: 14px; 
        }
        
        QFrame#Sidebar { 
            background: rgba(10, 10, 25, 0.9); 
            border-right: 1px solid #1A1A3A; 
        }
        
        QLabel#Title { 
            color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00D2FF, stop:1 #3A00FF); 
            font-size: 26px; 
            font-weight: 900; 
            padding: 25px;
            letter-spacing: 2px;
        }
        
        QPushButton#NavBtn { 
            background: transparent; 
            border: none; 
            text-align: left; 
            padding-left: 30px; 
            border-radius: 8px; 
            margin: 2px 15px;
            color: #707085;
            font-size: 13px;
        }
        QPushButton#NavBtn:hover { 
            background: rgba(0, 210, 255, 0.05); 
            color: #00D2FF; 
        }
        QPushButton#NavBtn:checked { 
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0, 210, 255, 0.1), stop:1 rgba(58, 0, 255, 0.1));
            color: #00D2FF; 
            font-weight: bold; 
            border-left: 4px solid #00D2FF;
        }
        
        QFrame#Card { 
            background: #0A0A1F; 
            border: 1px solid #1A1A3A; 
            border-radius: 15px; 
        }
        
        QPushButton#PrimaryBtn { 
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00D2FF, stop:1 #3A00FF); 
            color: #FFF; 
            border: none; 
            border-radius: 12px; 
            font-weight: 900; 
            font-size: 14px;
        }
        
        QLineEdit, QTextEdit {
            background: #020208;
            border: 1px solid #1A1A3A;
            border-radius: 6px;
            padding: 8px;
            color: #F0F0F0;
        }
        
        QProgressBar { 
            border: none; 
            border-radius: 2px; 
            background: #050510; 
            height: 4px; 
        }
        QProgressBar::chunk { 
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00D2FF, stop:1 #3A00FF); 
            border-radius: 2px; 
        }
        
        QLabel#StatusValue { color: #00D2FF; font-weight: bold; }
        
        QHeaderView::section { background-color: #0A0A1F; color: #888; padding: 8px; border: none; border-bottom: 1px solid #1A1A3A; }
    """
    LIGHT: str = """
        QMainWindow { background-color: #F8F9FA; }
        QWidget { color: #333; font-family: 'Inter', 'Segoe UI', 'Microsoft YaHei'; font-size: 14px; }
        
        QFrame#Sidebar { 
            background: #FFFFFF; 
            border-right: 1px solid #E5E5E5; 
        }
        
        QLabel#Title { 
            color: #0078D4; 
            font-size: 22px; 
            font-weight: 900; 
            padding: 20px;
        }
        
        QPushButton#NavBtn { 
            background: transparent; 
            border: none; 
            text-align: left; 
            padding-left: 30px; 
            border-radius: 0px; 
            color: #666;
            font-size: 13px;
            border-left: 3px solid transparent;
        }
        QPushButton#NavBtn:hover { 
            background: #F0F0F0; 
            color: #0078D4; 
        }
        QPushButton#NavBtn:checked { 
            background: rgba(0, 120, 212, 10); 
            color: #0078D4; 
            font-weight: bold; 
            border-left: 3px solid #0078D4;
        }
        
        QFrame#Card { 
            background: #FFFFFF; 
            border: 1px solid #E5E5E5; 
            border-radius: 12px; 
        }
        
        QPushButton#PrimaryBtn { 
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0078D4, stop:1 #2B88D8); 
            color: #FFF; 
            border: none; 
            border-radius: 12px; 
            font-weight: 900; 
            font-size: 14px;
        }
        QPushButton#PrimaryBtn:hover { 
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2B88D8, stop:1 #0078D4);
        }

        /* v6.1: Status Badges */
        QLabel#BadgeSuccess { background: #d4edda; color: #155724; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: bold; }
        QLabel#BadgeWarning { background: #fff3cd; color: #856404; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: bold; }
        QLabel#BadgeRunning { background: #d1ecf1; color: #0c5460; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: bold; }
        
        QPushButton#SecondaryBtn { 
            background: #F8F9FA; 
            color: #333; 
            border: 1px solid #E5E5E5; 
            border-radius: 8px; 
            font-weight: bold; 
        }
        QPushButton#SecondaryBtn:hover { background: #F0F0F0; }
        
        QLineEdit, QTextEdit {
            background: #FFFFFF;
            border: 1px solid #D5D5D5;
            border-radius: 6px;
            padding: 8px;
            color: #111;
        }
        
        QProgressBar { border: 1px solid #E5E5E5; border-radius: 8px; text-align: center; background: #F0F0F0; height: 12px; }
        QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0078D4, stop:1 #2B88D8); border-radius: 6px; }
        
        QHeaderView::section { background-color: #F8F9FA; color: #666; padding: 8px; border: none; border-bottom: 1px solid #E5E5E5; }
        QTableWidget { background-color: transparent; gridline-color: #EEE; border: none; color: #111; }
        QListWidget { background-color: #FFF; border: 1px solid #E5E5E5; border-radius: 12px; color: #333; }
        
        QScrollBar:vertical { border: none; background: transparent; width: 8px; }
        QScrollBar::handle:vertical { background: #CCC; border-radius: 4px; min-height: 20px; }
    """
    HIGH_CONTRAST: str = """
        QMainWindow { background-color: #000000; }
        QWidget { color: #FFFFFF; font-family: 'Segoe UI', 'Microsoft YaHei'; font-size: 15px; }
        
        QFrame#Sidebar { 
            background: #0A0A0A; 
            border-right: 2px solid #FFFFFF; 
        }
        
        QLabel#Title { 
            color: #FFFF00; 
            font-size: 28px; 
            font-weight: 900; 
            padding: 25px;
        }
        
        QPushButton#NavBtn { 
            background: transparent; 
            border: 2px solid #555; 
            text-align: left; 
            padding-left: 30px; 
            border-radius: 8px; 
            margin: 2px 15px;
            color: #FFF;
            font-size: 14px;
        }
        QPushButton#NavBtn:hover { 
            border-color: #FFFF00; 
            background: #222; 
        }
        QPushButton#NavBtn:checked { 
            background: #FFFF00; 
            color: #000; 
            font-weight: bold; 
            border: 2px solid #FFFF00;
        }
        
        QFrame#Card { 
            background: #111111; 
            border: 2px solid #FFFFFF; 
            border-radius: 15px; 
        }
        
        QPushButton#PrimaryBtn { 
            background: #FFFF00; 
            color: #000; 
            border: 2px solid #FFFF00; 
            border-radius: 12px; 
            font-weight: 900; 
            font-size: 15px;
        }
        QPushButton#PrimaryBtn:hover { 
            background: #FFEA00; 
        }
        QPushButton#PrimaryBtn:pressed { background: #FFD700; }

        QLabel#BadgeSuccess { background: #00FF00; color: #000; padding: 5px 12px; border-radius: 10px; font-size: 12px; font-weight: 900; border: 2px solid #00FF00; }
        QLabel#BadgeWarning { background: #FF0000; color: #FFF; padding: 5px 12px; border-radius: 10px; font-size: 12px; font-weight: 900; border: 2px solid #FF0000; }
        QLabel#BadgeRunning { background: #FFFF00; color: #000; padding: 5px 12px; border-radius: 10px; font-size: 12px; font-weight: 900; border: 2px solid #FFFF00; }
        
        QPushButton#SecondaryBtn { 
            background: #222; 
            color: #FFF; 
            border: 2px solid #888; 
            border-radius: 8px; 
            font-weight: bold; 
        }
        QPushButton#SecondaryBtn:hover { background: #333; border-color: #FFF; }
        
        QLineEdit, QTextEdit {
            background: #111111;
            border: 2px solid #888;
            border-radius: 6px;
            padding: 10px;
            color: #FFF;
        }
        
        QProgressBar { border: 2px solid #FFF; border-radius: 8px; text-align: center; background: #111; height: 14px; }
        QProgressBar::chunk { background: #FFFF00; border-radius: 6px; }
        
        QHeaderView::section { background-color: #222; color: #FFF; padding: 10px; border: 1px solid #FFF; }
        QTableWidget { background-color: transparent; gridline-color: #FFF; border: 1px solid #FFF; color: #FFF; }
        QListWidget { background-color: #111; border: 2px solid #FFF; border-radius: 12px; color: #FFF; }
        
        QScrollBar:vertical { border: 2px solid #FFF; background: #000; width: 12px; }
        QScrollBar::handle:vertical { background: #FFF; border-radius: 6px; min-height: 20px; }
    """

class GlobalState:
    accounts: List[Dict[str, Any]] = []  # Schema: id, token, cookie, expires_at, last_refresh...
    active_account_id: Optional[str] = None
    active_token: Optional[str] = None
    active_cookie: Optional[str] = None
    log_signal: Optional[Signal] = None
    theme: str = "DARK"
    total_calls: int = 0
    error_count: int = 0
    last_error: str = ""

    @staticmethod
    def _get_accounts_path() -> str:
        auth_dir = os.path.join(CONFIG["ROOT"], "data", "auth")
        os.makedirs(auth_dir, exist_ok=True)
        new_path = os.path.join(auth_dir, "accounts.json")
        old_path = os.path.join(CONFIG["ROOT"], "accounts.json")
        # v7.8: Migration
        if os.path.exists(old_path) and not os.path.exists(new_path):
            try:
                import shutil
                shutil.move(old_path, new_path)
                logger.info("[GLOBAL_STATE] 已将 accounts.json 迁移至 data/auth/")
            except: pass
        return new_path

    @staticmethod
    def load() -> None:
        try:
            p = GlobalState._get_accounts_path()
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    GlobalState.accounts = data.get("accounts", [])
                    GlobalState.active_account_id = data.get("active_account_id")
                    GlobalState.active_token = data.get("active_token")
                    GlobalState.active_cookie = data.get("active_cookie")
                    GlobalState.theme = data.get("theme", "DARK")
                    
                    # Industrial migration: ensure all accounts have the v6.0 schema
                    for acc in GlobalState.accounts:
                        if "is_active" not in acc: acc["is_active"] = True
                        if "expires_at" not in acc: acc["expires_at"] = ""
                        if "last_refresh" not in acc: acc["last_refresh"] = ""
                        if "name" not in acc: acc["name"] = f"Unit_{acc['id'][:4]}"
                        if "total_calls" not in acc: acc["total_calls"] = 0
                        # Decrypt tokens
                        acc["token"] = decrypt_token(acc["token"])
                    
                    if GlobalState.active_account_id:
                        for a in GlobalState.accounts:
                            if a["id"] == GlobalState.active_account_id:
                                GlobalState.active_token = a["token"]
                                GlobalState.active_cookie = a.get("cookie", "")
                                break
                    GlobalState.theme = data.get("theme", "DARK")
        except Exception as e:
            logger.error(f"Load State Error: {e}")

    @staticmethod
    def save():
        path = GlobalState._get_accounts_path()
        try:
            # Industrial save: preserve all v6.0 metadata
            save_accounts = []
            for a in GlobalState.accounts:
                acc_copy = a.copy()
                acc_copy["token"] = encrypt_token(a["token"]) # Encrypt for storage
                save_accounts.append(acc_copy)
            
            with open(path, 'w', encoding="utf-8") as f:
                json.dump({
                    "accounts": save_accounts,
                    "active_account_id": GlobalState.active_account_id,
                    "active_token": GlobalState.active_token,
                    "active_cookie": GlobalState.active_cookie,
                    "theme": GlobalState.theme
                }, f, indent=4)
        except Exception as e:
            logger.error(f"Save State Error: {e}")

    @staticmethod
    def parse_email(token: str) -> str:
        try:
            if not token or "." not in token: return "Unknown"
            payload = token.split(".")[1]
            padded = payload + "=" * (4 - len(payload) % 4)
            data = json.loads(base64.b64decode(padded).decode())
            return data.get("email", "Unknown")
        except: return "Unknown"

class SessionManager:
    profiles = {}

    @staticmethod
    def get_profile(account_id: str):
        if account_id not in SessionManager.profiles:
            profile = QWebEngineProfile(account_id, None)
            
            # Use unified settings block for maximum stability and Chrome-like behavior
            s = profile.settings()
            s.setAttribute(QWebEngineSettings.PluginsEnabled, True)
            s.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
            s.setAttribute(QWebEngineSettings.JavascriptCanAccessClipboard, True)
            s.setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True) # Revert to True (Chrome default)
            s.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
            s.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, True)
            s.setAttribute(QWebEngineSettings.AutoLoadImages, True)
            s.setAttribute(QWebEngineSettings.FullScreenSupportEnabled, True)
            s.setAttribute(QWebEngineSettings.WebRTCPublicInterfacesOnly, True)
            s.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
            s.setAttribute(QWebEngineSettings.DnsPrefetchEnabled, True)
            
            # All masking scripts removed as per user request for "Real" kernel.
            # Relying solely on native Chromium flags set in main.py.
            
            storage_path = os.path.join(CONFIG["ROOT"], "data", f"storage_{account_id}")
            cache_path = os.path.join(CONFIG["ROOT"], "data", f"cache_{account_id}")
            
            profile.setPersistentStoragePath(storage_path)
            profile.setCachePath(cache_path) # Critical for Real-Kernel depth
            profile.setPersistentCookiesPolicy(QWebEngineProfile.AllowPersistentCookies)
            profile.setHttpCacheType(QWebEngineProfile.DiskHttpCache)
            
            # Match latest production Chrome version for maximum compatibility
            profile.setHttpUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36")
            
            SessionManager.profiles[account_id] = profile
        return SessionManager.profiles[account_id]

    @staticmethod
    def delete_session(account_id: str):
        import shutil
        path = os.path.join(CONFIG["ROOT"], "data", f"storage_{account_id}")
        if os.path.exists(path):
            try: shutil.rmtree(path)
            except: pass
        if account_id in SessionManager.profiles:
            del SessionManager.profiles[account_id]
