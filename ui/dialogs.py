import os
import time
import logging
from PySide6.QtCore import Signal, QUrl, Qt
from PySide6.QtWidgets import (QVBoxLayout, QDialog, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QPushButton, 
                             QHBoxLayout, QFileDialog, QMessageBox, QFrame, QLabel, QStackedWidget,
                             QMainWindow, QWidget, QLineEdit)
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineUrlRequestInterceptor
from PySide6.QtWebEngineWidgets import QWebEngineView
from core.manager import SessionManager, GlobalState
from core.audit import get_history, export_history

logger = logging.getLogger(__name__)

# =================================================================
# UI 系统 - 拦截器 (UI System - Interceptor)
# =================================================================
class Interceptor(QWebEngineUrlRequestInterceptor):
    detected = Signal(str)
    
    def interceptRequest(self, info):
        url = info.requestUrl().toString()
        method = bytes(info.requestMethod()).decode()
        # Log network flow - increase length for Google/Firebase to ensure visibility
        log_len = 250 if "google" in url or "firebase" in url else 120
        msg = f"F12_FLOW | {method:4} | {url[:log_len]}{'...' if len(url)>log_len else ''}"
        logger.info(msg)
        if GlobalState.log_signal:
            GlobalState.log_signal.emit(msg)
        
        try:
            headers = info.httpHeaders()
            # Capture Authorization
            if b'Authorization' in headers:
                auth = bytes(headers[b'Authorization']).decode('utf-8')
                if "Bearer " in auth and len(auth) > 100:
                    token = auth.replace("Bearer ", "").strip()
                    msg_auth = f"✨ [AUTH_DETECTED] Token captured from: {url[:60]}..."
                    logger.info(msg_auth)
                    if GlobalState.log_signal:
                        GlobalState.log_signal.emit(msg_auth)
                    self.detected.emit(token)
            
            # Capture critical cookies for DesignArena analysis
            if b'Cookie' in headers:
                cookie = bytes(headers[b'Cookie']).decode('utf-8')
                if "NEXT_LOCALE" in cookie or "ph_phc" in cookie:
                    msg_cookie = f"🍪 [COOKIE_FLOW] Session/Locale data detected in request to: {url[:60]}..."
                    logger.info(msg_cookie)
                    if GlobalState.log_signal:
                        GlobalState.log_signal.emit(msg_cookie)
        except Exception as e:
            logger.error(f"Interceptor Error: {e}")

# =================================================================
# UI 系统 - 增强型页面 (UI System - Enhanced Page)
# =================================================================
class WebPage(QWebEnginePage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.featurePermissionRequested.connect(self.on_permission_requested)
        # Handle render process termination (e.g., OOM or crashes)
        self.renderProcessTerminated.connect(self.on_render_process_terminated)
        
        # NOTE: Using a Pure Real-Kernel. Since no automation flags (--remote-debugging-port) are used,
        # the engine identifies naturally as a standard browser. No fake scripts needed.

    def on_render_process_terminated(self, terminationStatus, exitCode):
        # Auto-recovery: If the browser engine crashes, attempt to reload the page
        logger.warning(f"💥 [BROWSER_CRASH] Render process terminated: {terminationStatus} (Code: {exitCode})")
        if terminationStatus != QWebEnginePage.NormalTerminationStatus:
            logger.info("♻️ [RECOVERY] Attempting to auto-reload the page...")
            self.triggerAction(QWebEnginePage.Reload)

    def on_permission_requested(self, url, feature):
        # Automatically grant common permissions to avoid blocking site features
        logger.info(f"🔓 [PERMISSION_AUTO] Granting {feature} to {url.toString()}")
        self.setFeaturePermission(url, feature, QWebEnginePage.PermissionGrantedByUser)

    def createWindow(self, _type):
        # Method 1: Standalone top-level window bypasses 'embedded' detection.
        logger.info(f"🪟 [METHOD_1_POPUP] Spawning independent browser for type: {_type}")
        try:
            # Important: Parenting a popup makes Google think it's 'embedded'.
            # Spawning it with no parent (None) makes it a native top-level window.
            popup = BrowserPopup(self.profile(), parent=None)
            popup.show()
            return popup.view.page()
        except Exception as e:
            logger.error(f"⚠️ [POPUP_ERROR] Failed to spawn Method 1 popup: {e}")
            return None
class BrowserPopup(QMainWindow):
    """A standalone, high-fidelity window for Google/OAuth authentication."""
    def __init__(self, profile, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Design Arena - 安全验证")
        self.resize(1100, 800)
        
        # Central Layer
        cw = QWidget(); self.setCentralWidget(cw)
        ly = QVBoxLayout(cw); ly.setContentsMargins(0, 0, 0, 0); ly.setSpacing(0)
        
        # 1. Address Bar (Read-only for fidelity, not input)
        self.addr_bar = QLineEdit()
        self.addr_bar.setReadOnly(True)
        self.addr_bar.setStyleSheet("""
            QLineEdit { 
                background: #f1f3f4; 
                border: none; 
                padding: 10px 20px; 
                color: #555; 
                font-size: 13px; 
                border-bottom: 1px solid #ddd;
            }
        """)
        ly.addWidget(self.addr_bar)
        
        # 2. Browser View
        self.view = QWebEngineView()
        self.page = WebPage(profile, self)
        self.view.setPage(self.page)
        ly.addWidget(self.view)
        
        # Sync URL
        self.view.urlChanged.connect(lambda u: self.addr_bar.setText(u.toString()))

# The LoginDlg has been removed and integrated directly into the main window for 'Built-in' Browser support.

# =================================================================
# UI 系统 - 历史记录对话框 (UI System - History Dialog)
# =================================================================
class HistoryDlg(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("全局审计与任务历史"); self.resize(900, 600)
        self.setStyleSheet("background:#111; color:#EEE;")
        ly = QVBoxLayout(self)
        
        btns = QHBoxLayout()
        btn_refresh = QPushButton("🔄 刷新数据"); btn_refresh.clicked.connect(self.load_data)
        btn_export = QPushButton("📤 导出审计记录 (CSV/JSON)"); btn_export.clicked.connect(self.export_data)
        btn_refresh.setStyleSheet("height:30px; background:#222;"); btn_export.setStyleSheet("height:30px; background:#222;")
        btns.addWidget(btn_refresh); btns.addWidget(btn_export); ly.addLayout(btns)

        self.tbl = QTableWidget(0, 7)
        self.tbl.setHorizontalHeaderLabels(["ID", "时间", "账号ID", "操作", "状态", "提示词", "错误"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.setStyleSheet("gridline-color: #333; border: none;")
        ly.addWidget(self.tbl)
        self.load_data()

    def load_data(self):
        data = get_history(100)
        self.tbl.setRowCount(len(data))
        for r_idx, row in enumerate(data):
            for c_idx, val in enumerate(row):
                item = QTableWidgetItem(str(val) if val else "")
                self.tbl.setItem(r_idx, c_idx, item)

    def export_data(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出审计记录", f"audit_export_{int(time.time())}.csv", "CSV Files (*.csv);;JSON Files (*.json)")
        if path:
            fmt = "json" if path.endswith(".json") else "csv"
            export_history(path, fmt)
            QMessageBox.information(self, "导出成功", f"记录已成功导出至:\n{path}")
