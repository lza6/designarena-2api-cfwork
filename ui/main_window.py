# -*- coding: utf-8 -*-
import uuid
import threading
import uvicorn
import time
import json
import webbrowser
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QRect, QSize
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QFrame, QLabel, QPushButton, QStackedWidget, 
                             QTextEdit, QLineEdit, QListWidget, QListWidgetItem,
                             QProgressBar, QSystemTrayIcon, QMenu, QButtonGroup,
                             QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea, QStyle, QGraphicsDropShadowEffect, QInputDialog)
from PySide6.QtGui import QIcon, QAction, QFont, QColor
from core.config import CONFIG
from core.manager import GlobalState, SessionManager, ThemeManager
from core.queue import _global_queue, Task
from core.browser import start_login_thread, start_refresh_thread
from ui.dialogs import HistoryDlg, Interceptor
from ui.widgets import ImageDropWidget
from api.server import app
from loguru import logger
import os

class UltimateWindow(QMainWindow):
    log_sig = Signal(str)
    task_sig = Signal(object)
    refresh_done_sig = Signal(str, str)  # v8.1: Dual-signal for Token + Cookie

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DesignArena 2API Pro - 工业级旗舰版")
        self.resize(1200, 850)
        
        GlobalState.load()
        
        # Unified Interceptor MUST be initialized before setup_ui as the UI loads the browser
        self.interceptor = Interceptor(self)
        self.interceptor.detected.connect(self.finalize_acc_silent)
        
        self.setup_ui()
        self.setup_tray()
        
        # v7.3: Auto-sync from captured files if no accounts exist
        self.sync_from_captured_files()
        
        self.log_sig.connect(self.add_log)
        self.task_sig.connect(self.update_task_ui)
        self.refresh_done_sig.connect(self.finalize_acc_silent) # v7.7 Fix Threading
        GlobalState.log_signal = self.log_sig
        _global_queue.on_task_update = lambda t: self.task_sig.emit(t)
        
        # API Thread
        self.api_thread = threading.Thread(
            target=lambda: uvicorn.run(app, host=CONFIG["HOST"], port=CONFIG["PORT"], log_config=None), 
            daemon=True
        )
        self.api_thread.start()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_ui)
        self.timer.start(2000)
        
        # v6.0: Industrial Auto-Refresh Guard
        self.refresh_guard_timer = QTimer()
        self.refresh_guard_timer.timeout.connect(self.check_auto_refresh)
        self.refresh_guard_timer.start(600000) # Check every 10 minutes (v8.0 Standard)

    def apply_theme(self) -> None:
        qss = ThemeManager.DARK if GlobalState.theme == "DARK" else ThemeManager.LIGHT
        self.setStyleSheet(qss)

    def setup_ui(self) -> None:
        cw = QWidget(); self.setCentralWidget(cw)
        main_layout = QHBoxLayout(cw); main_layout.setContentsMargins(0, 0, 0, 0); main_layout.setSpacing(0)
        
        # 1. Sidebar (Dynamic Styling via ThemeManager)
        self.sidebar = QFrame(); self.sidebar.setObjectName("Sidebar"); self.sidebar.setFixedWidth(260)
        side_layout = QVBoxLayout(self.sidebar); side_layout.setContentsMargins(0, 30, 0, 20); side_layout.setSpacing(5)
        
        logo_area = QVBoxLayout()
        logo = QLabel("DA 2API PRO"); logo.setObjectName("Title"); logo.setAlignment(Qt.AlignCenter)
        logo_sub = QLabel("ENTERPRISE EDITION"); logo_sub.setStyleSheet("font-size: 10px; color: #00d2ff; opacity: 0.8; letter-spacing: 3px; font-weight: bold;")
        logo_sub.setAlignment(Qt.AlignCenter)
        logo_area.addWidget(logo); logo_area.addWidget(logo_sub); side_layout.addLayout(logo_area)
        side_layout.addSpacing(30)
        
        self.nav_group = QButtonGroup(self)
        btns = [("控制面板", "🏠"), ("账号矩阵", "💎"), ("任务队列", "⚡"), ("数据透视", "📈"), ("操作审计", "🛡️"), ("系统设置", "⚙️")]
        for i, (text, icon) in enumerate(btns):
            btn = QPushButton(f"    {icon}   {text}"); btn.setObjectName("NavBtn"); btn.setCheckable(True)
            btn.setFixedHeight(55)
            if i == 0: btn.setChecked(True)
            self.nav_group.addButton(btn, i); side_layout.addWidget(btn)
        
        side_layout.addStretch()
        
        # Theme Toggle
        theme_btn = QPushButton("🌓 切换主题模式")
        theme_btn.setStyleSheet("background: transparent; border: 1px solid rgba(128,128,128,50); border-radius: 15px; margin: 20px; height: 35px; color: #888; font-size: 12px;")
        theme_btn.clicked.connect(self.rotate_theme)
        side_layout.addWidget(theme_btn)
        
        self.acc_info = QLabel("  ● 系统内核: 就绪 (Cyber-Active)"); self.acc_info.setStyleSheet("font-size: 11px; color: #00FFC2; padding: 20px; border-top: 1px solid #1A1A2E;"); side_layout.addWidget(self.acc_info)
        main_layout.addWidget(self.sidebar)
        
        # 2. Stacked Content
        self.stack = QStackedWidget()
        self.dashboard = self.create_dashboard()
        self.accounts_page = self.create_accounts_page()
        self.tasks_page = self.create_tasks_page()
        self.analytics_page = self.create_analytics_page()
        self.history_page = self.create_history_page()
        self.settings_page = self.create_settings_page()
        
        for p in [self.dashboard, self.accounts_page, self.tasks_page, self.analytics_page, self.history_page, self.settings_page]:
            self.stack.addWidget(p)
        main_layout.addWidget(self.stack)
        
        self.nav_group.idClicked.connect(self.stack.setCurrentIndex)
        self.apply_theme()

    def resizeEvent(self, event):
        super().resizeEvent(event)

    def rotate_theme(self):
        GlobalState.theme = "LIGHT" if GlobalState.theme == "DARK" else "DARK"
        GlobalState.save()
        self.apply_theme()
        self.add_log(f"🌗 已切换至 {GlobalState.theme} 主题模式")

    def _create_card(self, title: str, value: str, sub: str = "") -> QFrame:
        card = QFrame(); card.setObjectName("Card")
        l = QVBoxLayout(card); l.setContentsMargins(25, 25, 25, 25)
        t = QLabel(title); t.setStyleSheet("font-size: 11px; color: #888; font-weight: 800; text-transform: uppercase; letter-spacing: 1px;")
        v = QLabel(value); v.setStyleSheet("font-size: 42px; font-weight: 900; color: #FFF; margin: 5px 0;")
        s = QLabel(sub); s.setStyleSheet("font-size: 10px; color: #764ba2; font-weight: bold; background: rgba(118, 75, 162, 20); padding: 2px 8px; border-radius: 4px;")
        card.value_label = v; l.addWidget(t); l.addWidget(v); l.addWidget(s)
        return card

    def create_dashboard(self) -> QWidget:
        page = QWidget(); ly = QVBoxLayout(page); ly.setContentsMargins(50, 50, 50, 50); ly.setSpacing(30)
        ly.addWidget(QLabel("系统状态纵览 / Dashboard", objectName="Title"))
        
        stats_ly = QHBoxLayout(); stats_ly.setSpacing(25)
        self.card_total = self._create_card("累计分发请求", "0", "TOTAL TRAFFIC")
        self.card_error = self._create_card("拦截/重试异常", "0", "BLOCKED FAULTS")
        self.card_worker = self._create_card("动态计算单元", "3", "ACTIVE WORKERS")
        for c in [self.card_total, self.card_error, self.card_worker]: stats_ly.addWidget(c)
        ly.addLayout(stats_ly)
        
        gen_card = QFrame(); gen_card.setObjectName("Card"); gen_ly = QVBoxLayout(gen_card); gen_ly.setContentsMargins(30, 30, 30, 30)
        title_ly = QHBoxLayout(); title_ly.addWidget(QLabel("🚀 快捷测试通道 (Quick I2I Channel)", styleSheet="font-weight: 900; font-size: 15px;"))
        title_ly.addStretch(); gen_ly.addLayout(title_ly); gen_ly.addSpacing(10)
        
        h_box = QHBoxLayout(); h_box.setSpacing(12)
        self.prompt_input = QLineEdit(); self.prompt_input.setPlaceholderText("请输入创作指令或提示词..."); self.prompt_input.setFixedHeight(50)
        h_box.addWidget(self.prompt_input)
        self.gen_btn = QPushButton("发送指令"); self.gen_btn.setFixedHeight(50); self.gen_btn.setFixedWidth(140)
        self.gen_btn.setStyleSheet("background: hsv(45, 100%, 100%); color: #000; font-weight: 900; border-radius: 8px; font-size: 15px;")
        self.gen_btn.clicked.connect(self.on_quick_gen); h_box.addWidget(self.gen_btn); gen_ly.addLayout(h_box)
        
        ly.addWidget(gen_card)
        
        # Status Bar Area (v8.0 F1 - High Precision)
        status_layout = QHBoxLayout()
        self.status_label = QLabel("● 系统内核: 运行中 (CYBER-ACTIVE)")
        self.status_label.setStyleSheet("color: #00FFC2; font-weight: 800; font-size: 11px;")
        self.capture_status = QLabel("流量侦听: 等待脉冲")
        self.capture_status.setObjectName("StatusValue")
        
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.capture_status)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(4)
        
        ly.addLayout(status_layout)
        ly.addWidget(self.progress_bar)
        
        c_title = QLabel("📟 实时系统调度终端 (Industrial Console)")
        c_title.setStyleSheet("font-weight: 900; color: #555; font-size: 12px; margin-top: 10px;")
        ly.addWidget(c_title)
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background: rgba(5,5,15,0.8); color: #00FFC2; font-family:'Consolas'; border: 1px solid #1A1A3A; padding: 15px; border-radius: 10px;")
        ly.addWidget(self.console)
        return page

    def create_accounts_page(self) -> QWidget:
        page = QWidget(); ly = QVBoxLayout(page); ly.setContentsMargins(30, 40, 30, 30); ly.setSpacing(20)
        ly.addWidget(QLabel("账号矩阵 / Account Matrix", objectName="Title"))
        
        # 2. Account Matrix (v6.0 Industrial Layout)
        self.acc_list = QTableWidget(0, 6)
        self.acc_list.setHorizontalHeaderLabels(["状态", "名称", "剩余有效期", "最后同步", "会话路径", "累计用量"])
        self.acc_list.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.acc_list.setSelectionBehavior(QTableWidget.SelectRows)
        self.acc_list.verticalHeader().setVisible(False)
        self.acc_list.setObjectName("AccTable")
        self.acc_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.acc_list.customContextMenuRequested.connect(self.show_acc_menu)
        self.acc_list.cellClicked.connect(self.select_acc_table)
        ly.addWidget(self.acc_list)
        
        btn_ly = QHBoxLayout(); btn_ly.setSpacing(10)
        btn_add = QPushButton(" 💎 接入新账号单元 (Add Unit) "); btn_add.setFixedHeight(45); btn_add.clicked.connect(self.add_acc)
        btn_add.setObjectName("PrimaryBtn")
        btn_del = QPushButton(" 🗑️ 彻底移除 (Remove) "); btn_del.setFixedHeight(45); btn_del.clicked.connect(self.del_acc); 
        btn_del.setObjectName("SecondaryBtn")
        btn_ly.addWidget(btn_add); btn_ly.addWidget(btn_del); ly.addLayout(btn_ly)
        
        self.sync_acc_list(); return page

    def create_tasks_page(self) -> QWidget:
        page = QWidget(); ly = QVBoxLayout(page); ly.setContentsMargins(50, 50, 50, 50)
        ly.addWidget(QLabel("任务实时观测镜像 / Task Mirror", objectName="Title"))
        self.task_list_widget = QListWidget(); self.task_list_widget.setStyleSheet("background: transparent; border: 1px solid #222; border-radius: 12px; QListWidget::item { padding: 15px; border-bottom: 1px solid #1a1a1a; }"); ly.addWidget(self.task_list_widget); return page

    def create_analytics_page(self) -> QWidget:
        page = QWidget(); ly = QVBoxLayout(page); ly.setContentsMargins(50, 50, 50, 50); ly.setSpacing(30)
        ly.addWidget(QLabel("系统运行深度透视 / Analytics Hub", objectName="Title"))
        stats_ly = QHBoxLayout(); stats_ly.setSpacing(25)
        self.ana_calls = self._create_card("历史吞吐量", "0", "LIFETIME REQS")
        self.ana_errors = self._create_card("安全熔断拦截", "0", "FAULT PREVENTION")
        self.ana_latency = self._create_card("平均响应延迟", "0s", "NETWORK LATENCY")
        stats_ly.addWidget(self.ana_calls); stats_ly.addWidget(self.ana_errors); stats_ly.addWidget(self.ana_latency); ly.addLayout(stats_ly)
        
        ly.addWidget(QLabel("⚡ 账号池实时健康矩阵 / Pool Health Status", styleSheet="font-weight: 900; margin-top: 10px; color: #FFBF00;"))
        self.health_table = QTableWidget(0, 5); self.health_table.setHorizontalHeaderLabels(["节点 ID", "活跃任务", "连续失败", "存活状态", "重联冷却"])
        self.health_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); ly.addWidget(self.health_table); ly.addStretch()
        return page

    def create_history_page(self) -> QWidget:
        page = QWidget(); ly = QVBoxLayout(page); ly.setContentsMargins(50, 50, 50, 50)
        ly.addWidget(QLabel("全量审计历史镜像 / Global Audit", objectName="Title"))
        btn = QPushButton("📑 调取全量审计报表 (CSV/JSON)"); btn.setFixedHeight(60); btn.clicked.connect(self.show_history)
        btn.setStyleSheet("background: hsv(0, 0, 15%); border: 2px dashed #444; border-radius: 15px; font-weight: 900; font-size: 16px;")
        ly.addWidget(btn); ly.addStretch(); return page

    def create_settings_page(self) -> QWidget:
        page = QWidget(); scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget(); ly = QVBoxLayout(content); ly.setContentsMargins(50, 50, 50, 50); ly.setSpacing(25)
        ly.addWidget(QLabel("系统高级配置中心 / Advanced Settings", objectName="Title"))
        
        # Theme Toggle
        theme_card = QFrame(); theme_card.setObjectName("Card"); tl = QHBoxLayout(theme_card); tl.setContentsMargins(20,20,20,20)
        tl.addWidget(QLabel("🌗 界面主题模式切换 (System Theme Mode)"))
        self.theme_btn = QPushButton("切换模式"); self.theme_btn.setFixedWidth(120); self.theme_btn.clicked.connect(self.toggle_theme)
        tl.addWidget(self.theme_btn); ly.addWidget(theme_card)
        
        # API Connection Info
        api_card = QFrame(); api_card.setObjectName("Card"); al = QVBoxLayout(api_card); al.setContentsMargins(20,20,20,20)
        al.addWidget(QLabel("🔌 API 服务终结点 (Service Endpoints)", styleSheet="font-weight: bold; color: #FFBF00;"))
        self.api_url_label = QLabel(f"http://{CONFIG['HOST']}:{CONFIG['PORT']}/v1/chat/completions")
        self.api_url_label.setStyleSheet("font-family: 'Consolas'; font-size: 13px; color: #888; margin: 10px 0;")
        al.addWidget(self.api_url_label)
        btn_copy = QPushButton("📦 复制 OpenAI 格式接口地址"); btn_copy.clicked.connect(lambda: self.copy_text(self.api_url_label.text())); al.addWidget(btn_copy)
        ly.addWidget(api_card)
        
        # Master Key Card
        key_card = QFrame(); key_card.setObjectName("Card"); kl = QVBoxLayout(key_card); kl.setContentsMargins(20,20,20,20)
        kl.addWidget(QLabel("🔑 主访问凭证 (Master Authentication Key)", styleSheet="font-weight: bold; color: #FFBF00;"))
        self.key_display = QLabel(CONFIG["API_MASTER_KEY"][:4] + "*" * 12)
        self.key_display.setStyleSheet("font-family: 'Consolas'; font-size: 20px; color: #AAA; margin: 10px 0;")
        kl.addWidget(self.key_display)
        
        kb_ly = QHBoxLayout()
        self.show_key_btn = QPushButton("👁️ 显示明文"); self.show_key_btn.setCheckable(True); 
        self.show_key_btn.clicked.connect(self.toggle_key_visibility); kb_ly.addWidget(self.show_key_btn)
        btn_copy_key = QPushButton("📄 复制凭证"); btn_copy_key.clicked.connect(lambda: self.copy_text(CONFIG["API_MASTER_KEY"])); kb_ly.addWidget(btn_copy_key)
        kl.addLayout(kb_ly); ly.addWidget(key_card)
        
        # Model List Card
        model_card = QFrame(); model_card.setObjectName("Card"); ml = QVBoxLayout(model_card); ml.setContentsMargins(20,20,20,20)
        ml.addWidget(QLabel("🤖 受支持模型矩阵 (Supported Model Matrix)", styleSheet="font-weight: bold; color: #FFBF00;"))
        m_list = QLabel("● designarena-image (默认推荐)\n● designarena-turbo (极速模式)\n● dall-e-3 (兼容映射)")
        m_list.setStyleSheet("color: #777; line-height: 1.8; margin-top: 10px;")
        ml.addWidget(m_list); 
        btn_doc = QPushButton("📘 查看 API 集成最佳实践文档"); btn_doc.clicked.connect(lambda: webbrowser.open("https://github.com/")); ml.addWidget(btn_doc)
        ly.addWidget(model_card)
        
        ly.addStretch()
        scroll.setWidget(content); return scroll

    def setup_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
        # Use a standard system icon as fallback (Qt6 style enumeration)
        self.tray.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        menu = QMenu(); show = QAction("显示主窗口", self); show.triggered.connect(self.show)
        exit_ac = QAction("退出程序", self); exit_ac.triggered.connect(self.close)
        menu.addAction(show); menu.addSeparator(); menu.addAction(exit_ac)
        self.tray.setContextMenu(menu); self.tray.show()

    def sync_acc_list(self) -> None:
        self.acc_list.setRowCount(len(GlobalState.accounts))
        for i, a in enumerate(GlobalState.accounts):
            is_active = (a["id"] == GlobalState.active_account_id)
            status = "✨ 活跃 (当前)" if is_active else "⚪ 备用"
            if not a.get("is_active", True): status = "🔴 停用"
            
            status_item = QTableWidgetItem()
            self.acc_list.setItem(i, 0, status_item)
            
            # v6.1: Rich Status Badges
            badge = QLabel(status)
            if "活跃" in status: badge.setObjectName("BadgeSuccess")
            elif "停用" in status: badge.setObjectName("BadgeWarning")
            else: badge.setObjectName("BadgeRunning")
            badge.setAlignment(Qt.AlignCenter)
            self.acc_list.setCellWidget(i, 0, badge)
            
            name_item = QTableWidgetItem(a.get("name", "Unknown"))
            if is_active: name_item.setFont(QFont("Segoe UI", -1, QFont.Bold))
            self.acc_list.setItem(i, 1, name_item)
            
            # Calculate remaining time
            try:
                exp = datetime.fromisoformat(a.get("expires_at", ""))
                rem = (exp - datetime.now()).total_seconds() / 60
                
                # v7.1 FIX: 考虑提前刷新时间，显示实际有效时间
                refresh_before = 10  # 默认提前 10 分钟
                try:
                    from core.config import get_settings
                    refresh_before = get_settings().TOKEN_REFRESH_BEFORE_EXPIRY
                except:
                    pass
                
                effective_rem = rem - refresh_before
                
                if rem > 0:
                    if effective_rem <= 0:
                        rem_str = f"⚠️ 即将过期 (有效{int(effective_rem)} 分钟)"
                    else:
                        rem_str = f"{int(rem)} 分钟 (有效{int(effective_rem)} 分钟)"
                else:
                    rem_str = "已过期"
            except: rem_str = "未知"
            
            self.acc_list.setItem(i, 2, QTableWidgetItem(rem_str))
            
            last = a.get("last_refresh", "").split("T")[1][:5] if "T" in a.get("last_refresh", "") else "-"
            self.acc_list.setItem(i, 3, QTableWidgetItem(last))
            
            path = a.get("browser_data_path", "-")
            self.acc_list.setItem(i, 4, QTableWidgetItem(path))
            
            calls = f"{a.get('total_calls', 0)} 次"
            self.acc_list.setItem(i, 5, QTableWidgetItem(calls))

    def check_auto_refresh(self):
        """No-Touch background task to refresh sessions near expiration."""
        from core.token_manager import get_token_manager
        
        now = datetime.now()
        
        # v7.0: Check BOTH account expiry AND token manager expiry
        token_manager = get_token_manager()
        
        # Check if token manager needs refresh (independent of account expiry)
        if token_manager.is_expired() or token_manager.needs_refresh():
            self.add_log(f"🔄 [v7] Token 管理器检测到需要刷新，启动后台续期...")
            # Trigger refresh for active account
            if GlobalState.active_account_id:
                start_refresh_thread(GlobalState.active_account_id, self.refresh_done_sig.emit)
        
        # Check individual accounts
        for a in GlobalState.accounts:
            try:
                # v6.0: Robust expiration check
                if not a.get("expires_at"): continue
                exp = datetime.fromisoformat(a.get("expires_at", ""))
                diff = (exp - now).total_seconds()
                
                # If expires in < 30 minutes, trigger headless refresh
                if 0 < diff < 1800:
                    self.add_log(f"🔄 检测到账号 [{a['name']}] 会话即将过期 ({int(diff/60)}m)，启动静默续期...")
                    start_refresh_thread(a["id"], self.refresh_done_sig.emit)
                elif diff <= 0:
                    self.add_log(f"⚠️ 账号 [{a['name']}] 会话已过期，请手动重新登录。")
            except Exception as e: 
                logger.error(f"Refresh Check Error for {a.get('id')}: {e}")
                continue

    def refresh_ui(self) -> None:
        try:
            from core.scheduler import _global_balancer
            self.card_total.value_label.setText(str(GlobalState.total_calls))
            self.card_error.value_label.setText(str(GlobalState.error_count))
            self.acc_info.setText(f"  ● 活跃单元: {GlobalState.parse_email(GlobalState.active_token)}")
            
            self.ana_calls.value_label.setText(str(GlobalState.total_calls))
            self.ana_errors.value_label.setText(str(GlobalState.error_count))
            
            h_map = _global_balancer.health_map
            self.health_table.setRowCount(len(h_map))
            for i, (aid, h) in enumerate(h_map.items()):
                self.health_table.setItem(i, 0, QTableWidgetItem(aid))
                self.health_table.setItem(i, 1, QTableWidgetItem(str(h.active_tasks)))
                self.health_table.setItem(i, 2, QTableWidgetItem(str(h.failures)))
                status = "🟢 工作正常" if h.failures < 3 else "🔴 链路抖动"
                if time.time() < h.cool_off_until: status = "⏳ 风控挂起"
                self.health_table.setItem(i, 3, QTableWidgetItem(status))
                co = max(0, int(h.cool_off_until - time.time()))
                self.health_table.setItem(i, 4, QTableWidgetItem(f"{co}s" if co > 0 else "-"))
        except: pass

    def update_task_ui(self, task: Task) -> None:
        msg = f"[{datetime.now().strftime('%H:%M:%S')}] 任务 {task.id[:8]} | {task.status} | 精度: {task.progress}% - {task.message}"
        item = QListWidgetItem(msg); self.task_list_widget.insertItem(0, item)
        if self.task_list_widget.count() > 50: self.task_list_widget.takeItem(50)

    def on_quick_gen(self) -> None:
        p = self.prompt_input.text()
        if not p: return
        aid = GlobalState.active_account_id
        if not aid: return
        _global_queue.add_task(aid, p, self.drop_zone.file_path)
        self.prompt_input.clear(); self.add_log(f"用户提交快捷任务: {p[:30]}...")

    def add_log(self, m: str) -> None:
        self.console.append(m)

    def toggle_theme(self) -> None:
        GlobalState.theme = "LIGHT" if GlobalState.theme == "DARK" else "DARK"
        self.apply_theme(); GlobalState.save()

    def toggle_key_visibility(self, checked):
        if checked:
            self.key_display.setText(CONFIG["API_MASTER_KEY"])
            self.show_key_btn.setText("🔒 隐藏明文")
        else:
            self.key_display.setText(CONFIG["API_MASTER_KEY"][:4] + "*" * 12)
            self.show_key_btn.setText("👁️ 显示明文")

    def copy_text(self, text):
        from PySide6.QtGui import QClipboard
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
        self.add_log(f"系统提示: 内容已复制到剪贴板")

    def select_acc_table(self, row: int, col: int) -> None:
        if row < 0 or row >= len(GlobalState.accounts): return
        a = GlobalState.accounts[row]
        GlobalState.active_account_id = a["id"]
        GlobalState.active_token = a["token"]
        GlobalState.save()
        self.add_log(f"已选择活跃账号: {a['name']}")
        self.sync_acc_list()
        self.load_browser_session(a["id"])

    def load_browser_session(self, aid: str):
        # Note: In 'Dashboard + Popup' mode, the browser is only used for login
        # However, we keep this method for potential future background validation
        pass

    def add_acc(self) -> None:
        # v5.0: SPAWN STANDALONE PLAYWRIGHT CHROMIUM (The 'Real-User' Standard)
        # This mirrors the reference project 'zai-2api' for 100% realistic fidelity.
        aid = f"pending_{uuid.uuid4().hex[:6]}"
        self.add_log(f"已启动 Playwright 独立内核浏览器执行 [DesignArena] 高级验证...")
        
        # Launch standalone browser in a separate thread to keep Dashboard responsive
        start_login_thread(aid, self.refresh_done_sig.emit)

    def finalize_acc_silent(self, token: str, cookie: str = None) -> None:
        # v6.0: Populate industrial metadata for deep persistence
        aid = f"auto_{token[:8]}"
        now = datetime.now()
        expiry = (now + timedelta(hours=3)).isoformat() # DesignArena standard 3h
                
        # v7.1 FIX: 同时检查 ID 和 Token 是否重复 (更严格的检查)
        found = False
        duplicate_idx = -1
        
        for idx, a in enumerate(GlobalState.accounts):
            # 优先检查 Token 是否完全相同 (最准确)
            if a["token"] == token:
                logger.info(f"[ACCOUNT] 发现相同 Token，更新账号信息：{a['id']}")
                a["expires_at"] = expiry
                a["last_refresh"] = now.isoformat()
                if cookie: a["cookie"] = cookie # Update cookie if provided
                # 确保 ID 也是最新的
                if a["id"] != aid:
                    old_id = a["id"]
                    a["id"] = aid
                    logger.info(f"[ACCOUNT] ID 已更新：{old_id} -> {aid}")
                found = True
                break
            
            # 其次检查 ID 是否重复 (兼容性)
            if a["id"] == aid:
                logger.info(f"[ACCOUNT] 发现相同 ID，但 Token 不同，删除旧账号：{a['id']}")
                # 记录要删除的索引
                duplicate_idx = idx
                break
        
        # 如果发现 ID 重复但 Token 不同的情况，删除旧账号
        if duplicate_idx >= 0 and not found:
            old_account = GlobalState.accounts.pop(duplicate_idx)
            logger.warning(f"[ACCOUNT] 已删除冲突账号：{old_account['name']} (Token 前缀：{old_account['token'][:20]}...)")
        
        # 如果没有找到相同 Token，添加新账号（无论是否删除了旧账号）
        if not found:
            # v7.1: 检查是否超过最大账号数
            max_accounts = 10  # 最多 10 个账号
            if len(GlobalState.accounts) >= max_accounts:
                logger.warning(f"[ACCOUNT] 账号数量已达上限 ({max_accounts}),删除最旧的账号")
                # 删除最久未刷新的账号
                oldest = min(GlobalState.accounts, key=lambda x: x.get("last_refresh", ""))
                GlobalState.accounts.remove(oldest)
                logger.info(f"[ACCOUNT] 已删除账号：{oldest['name']}")
                    
            new_acc = {
                "id": aid,
                "name": f"Unit_{aid[5:]}",
                "token": token,
                "cookie": cookie,
                "expires_at": expiry,
                "last_refresh": now.isoformat(),
                "browser_data_path": f"data/browser_sessions/{aid}",
                "is_active": True,
                "total_calls": 0
            }
            GlobalState.accounts.append(new_acc)
            GlobalState.active_account_id = aid
            GlobalState.active_token = token
            GlobalState.active_cookie = cookie # v8.1 Support
            logger.info(f"[ACCOUNT] 新账号已添加：{new_acc['name']}")
            
        GlobalState.save()
        self.sync_acc_list()
        self.add_log(f"🚀 [v6.0_SUCCESS] 账号会话已建立并进入自动续期监控。")

    def sync_from_captured_files(self):
        """v7.3: 从本地截获的文件同步 Token 到账号矩阵"""
        from core.token_manager import get_token_manager
        tm = get_token_manager()
        
        if tm.current_token and not tm.is_expired():
            # 检查是否已在 GlobalState 中
            exists = any(a["token"] == tm.current_token for a in GlobalState.accounts)
            if not exists:
                self.add_log(f"📋 [v7.3] 发现未关联的本地 Token，正在同步到账号矩阵...")
                self.finalize_acc_silent(tm.current_token)
            else:
                # 即使存在，也要确保 UI 上的活跃单元显示正确
                if not GlobalState.active_token:
                    GlobalState.active_token = tm.current_token
                    for a in GlobalState.accounts:
                        if a["token"] == tm.current_token:
                            GlobalState.active_account_id = a["id"]
                            break
                    self.sync_acc_list()

    def del_acc(self) -> None:
        # Get selected row from table
        row = self.acc_list.currentRow()
        if row < 0: return
        aid = GlobalState.accounts[row]["id"]
        
        GlobalState.accounts = [a for a in GlobalState.accounts if a["id"] != aid]
        if GlobalState.active_account_id == aid: GlobalState.active_account_id = ""; GlobalState.active_token = ""
        GlobalState.save(); self.sync_acc_list(); SessionManager.delete_session(aid)

    def show_acc_menu(self, pos: QPoint) -> None:
        row = self.acc_list.currentRow()
        if row < 0: return
        
        menu = QMenu(self)
        a = GlobalState.accounts[row]
        
        act = menu.addAction("🚀 立即刷新 (Force Refresh)")
        act.triggered.connect(lambda: start_refresh_thread(a["id"], self.refresh_done_sig.emit))
        
        active_act = menu.addAction("✨ 设为当前活跃账号")
        active_act.triggered.connect(lambda: self.set_active_acc(row))
        
        rename_act = menu.addAction("🖊️ 重命名 (Rename)")
        rename_act.triggered.connect(lambda: self.rename_acc(row))
        
        menu.addSeparator()
        
        del_act = menu.addAction("🗑️ 彻底删除 (Delete)")
        del_act.triggered.connect(self.del_acc)
        
        menu.exec(self.acc_list.viewport().mapToGlobal(pos))

    def set_active_acc(self, row: int):
        a = GlobalState.accounts[row]
        GlobalState.active_account_id = a["id"]
        GlobalState.active_token = a["token"]
        GlobalState.save()
        self.sync_acc_list()
        self.add_log(f"已切换活跃账号: {a['name']}")

    def rename_acc(self, row: int):
        a = GlobalState.accounts[row]
        new_name, ok = QInputDialog.getText(self, "重命名单元", f"请输入 [{a['id']}] 的新名称:", text=a.get("name", ""))
        if ok and new_name:
            a["name"] = new_name
            GlobalState.save()
            self.sync_acc_list()
            self.add_log(f"账号已重命名: {new_name}")

    def show_history(self) -> None:
        dlg = HistoryDlg(self); dlg.exec()
