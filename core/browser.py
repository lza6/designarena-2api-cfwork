# -*- coding: utf-8 -*-
import os
import time
import subprocess
import shutil
from datetime import datetime
from loguru import logger
from playwright.sync_api import sync_playwright, BrowserContext, Page, Request
try:
    from playwright_stealth import stealth_sync
except ImportError:
    def stealth_sync(page): pass
from core.config import CONFIG
from core.token_manager import get_token_manager

def find_chrome_executable():
    """Locates the Google Chrome executable on Windows."""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        "chrome.exe"
    ]
    for p in candidates:
        if os.path.isabs(p) and os.path.exists(p):
            return p
    return "chrome.exe"

def kill_chrome_processes():
    """Forcefully terminates all existing Chrome processes to unlock data directories."""
    try:
        # Kill both chrome and its child processes
        subprocess.run('taskkill /F /IM chrome.exe /T', shell=True, capture_output=True, check=False)
        subprocess.run('taskkill /F /IM "Google Chrome" /T', shell=True, capture_output=True, check=False)
        time.sleep(2) # Give OS time to release file locks
    except Exception as e:
        logger.debug(f"Kill failed: {e}")

def setup_mirror_profile(profile_name="Default"):
    """
    v8.0 Industrial Pro: High-Fidelity Mirror Sync (Physical Copy Mode)
    Ensures 100% session persistence by copying the Chrome profile to a mirror directory.
    This avoids file locking issues and protects the original profile data.
    """
    real_data = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google/Chrome/User Data')
    mirror_root = os.path.abspath(os.path.join(CONFIG["ROOT"], "data", "chrome_mirror"))
    
    # 1. Resolve Profile Path
    real_profile = os.path.join(real_data, profile_name)
    if not os.path.exists(real_profile):
        try:
            profiles = [d for d in os.listdir(real_data) if (d.startswith("Profile ") or d == "Default") and os.path.isdir(os.path.join(real_data, d))]
            if profiles:
                profile_name = "Default" if "Default" in profiles else profiles[0]
                real_profile = os.path.join(real_data, profile_name)
        except: pass
    
    mirror_profile = os.path.join(mirror_root, profile_name)
    
    # 2. Perform Industrial Mirror Sync (Robocopy)
    logger.info(f"[MIRROR] 🔄 正在同步工业级物理镜像 (账号: {profile_name})...")
    
    # Ensure root exists
    os.makedirs(mirror_root, exist_ok=True)
    
    # Robocopy Args: 
    # /E: Subdirs /R:3: Retries /W:5: Wait /MT:32: Multi-thread /B: Backup mode (for locked files) /NDL /NFL: Silent
    # /XD: Exclude huge caching blobs to speed up sync while keeping 100% login fidelity
    robocopy_cmd = [
        "robocopy", real_profile, mirror_profile,
        "/E", "/R:3", "/W:5", "/MT:32", "/B", "/NP", "/NDL", "/NFL",
        "/XD", "Cache", "Code Cache", "GPUCache", "Media Cache", "Service Worker", "VideoDecodeStats"
    ]
    
    try:
        # Robocopy return codes 0-7 are success (no errors or non-fatal mismatches)
        res = subprocess.run(robocopy_cmd, check=False)
        if res.returncode <= 7:
            logger.info(f"[SYSTEM] [SUCCESS] v8.0 物理镜像已就绪 (Industrial Copy Ready)")
        else:
            logger.warning(f"[MIRROR_WARN] Robocopy 返回代码: {res.returncode}")
    except Exception as e:
        logger.error(f"[MIRROR_ERROR] 核心镜像同步失败: {e}")
        # Final emergency fallback if robocopy is missing
        if not os.path.exists(mirror_profile): os.makedirs(mirror_profile, exist_ok=True)
        
    return mirror_root

class PlaywrightManager:
    """Industrial-grade browser manager using Managed Mirror Mode."""
    def __init__(self, account_id: str):
        logger.info(f"[BROWSER] 🚀 初始化浏览器管理器 (账号：{account_id})")
        self.account_id = account_id
        self.captured_token = None
        self._is_closing = False
        self._context = None  # 保存 context 引用用于自动刷新
        
        # 获取 Token 管理器
        self.token_manager = get_token_manager()

    def launch_login(self, success_callback):
        """Launches Chrome UI via Mirror Profile for 100% session persistence."""
        # v7.1: Early Exit if valid credentials already exist
        if not self.token_manager.is_expired() and self.token_manager.current_token:
            logger.info(f"[BROWSER] ✅ 发现有效本地凭据，无需启动浏览器。")
            try:
                print(f"\n{self.token_manager.get_status_report()}\n", flush=True)
            except UnicodeEncodeError:
                logger.info("[BROWSER] Token status report printed (emoji stripped for console)")
            success_callback(self.token_manager.current_token, self.token_manager.current_cookie or "")
            return

        logger.info(f"[BROWSER] 🌐 启动 v8.0 Industrial 登录流程 (账号：{self.account_id})")
        
        # 1. v9.0 Industrial Sync: No-Kill physical mirroring
        # Uses Robocopy /B to safely sync sessions without closing user's Chrome.
        logger.info("[BROWSER] � 正在建立工业级实时同步镜像...")
        
        # 2. 准备镜像配置
        logger.info("[BROWSER] 📦 正在建立零拷贝同步镜像...")
        mirror_path = setup_mirror_profile()
        logger.info(f"[BROWSER] ✅ 环境就绪：{mirror_path}")
        
        chrome_path = find_chrome_executable()
        
        with sync_playwright() as p:
            try:
                logger.info("[BROWSER] 🚀 正在启动 Playwright Chromium 引擎...")
                # v6.11: RESTORE DEBUGGING PORT
                # We do NOT use ignore_default_args=True as it strips the CDP port.
                context = p.chromium.launch_persistent_context(
                    user_data_dir=mirror_path,
                    executable_path=chrome_path,
                    channel="chrome",
                    headless=False,
                    no_viewport=True,
                    args=[
                        "--start-maximized",
                        "--no-default-browser-check",
                        "--remote-allow-origins=*",
                        # We don't add --disable-infobars as it's an automation indicator
                    ]
                )
                logger.info("[BROWSER] ✅ Chromium 引擎启动成功")
                
                # Apply stealth ONLY via init script to remain invisible to trackers
                logger.info("[BROWSER] 🛡️  正在应用反检测脚本...")
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    window.chrome = {runtime: {}};
                """)
                logger.info("[BROWSER] ✅ 反检测脚本已加载")
                
                page = context.pages[0] if context.pages else context.new_page()

                def on_request(request):
                    if self._is_closing: return
                    try:
                        url = request.url
                        headers = request.headers
                        
                        # v8.0 Global Regex Sniffer
                        import re
                        TOKEN_PATTERN = r"Bearer\s+(ey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*)"
                        
                        found_token = None
                        for h_val in headers.values():
                            match = re.search(TOKEN_PATTERN, str(h_val))
                            if match:
                                found_token = match.group(1)
                                break
                        
                        if found_token:
                            print(f"\n{'='*80}", flush=True)
                            print(f"[v8.0 SNIFFER] Active Token Captured! (Source: {url[:60]}...)", flush=True)
                            print(f"{'='*80}", flush=True)
                            
                            cookie = headers.get('cookie') or headers.get('Cookie') or ""
                            self.token_manager.update_token(found_token, cookie, expires_in_minutes=60)
                            success_callback(found_token, cookie)
                            
                            time.sleep(1)
                            self._is_closing = True
                    except Exception as e:
                        logger.debug(f"Sniffer error: {e}")
                
                context.on("request", on_request)
                logger.info("[BROWSER] ✅ v8.0 流量嗅探已绑定")

                # v6.15: Optimized Navigation Trigger -> Target Naked Domain to avoid Next.js not-found state
                target_url = "https://designarena.ai/"
                                
                try:
                    page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
                    print(f"\n[SYSTEM] [NAV_DONE] 到达页面：{page.url}", flush=True)
                    print(f"[INFO] 页面加载完成，等待背景流量或尝试自动交互...", flush=True)
                                    
                    # 等待页面完全加载和初始化
                    time.sleep(5)
                                    
                    # 尝试自动点击可能的聊天入口
                    try:
                        # 查找聊天相关的链接或按钮
                        chat_selectors = [
                            'a[href*="/chat"]',
                            'a[href*="/chats"]',
                            'a[href="chat"]',
                            'button:has-text("Chat")',
                            'button:has-text("聊天")',
                            '[data-testid*="chat"]',
                            '.chat-button',
                            '#chat-button',
                            'nav a:has-text("Chat")',
                            'nav a:has-text("聊天")',
                            'header a:has-text("Chat")',
                            'header a:has-text("聊天")',
                        ]
                                        
                        clicked = False
                        for selector in chat_selectors:
                            try:
                                elements = page.query_selector_all(selector)
                                for element in elements:
                                    if element and element.is_visible():
                                        bounding_box = element.bounding_box()
                                        if bounding_box and bounding_box['width'] > 0 and bounding_box['height'] > 0:
                                            print(f"\n[AUTO_CLICK] 发现聊天入口：{selector}", flush=True)
                                            print(f"[AUTO_CLICK] 元素位置：{bounding_box}", flush=True)
                                                            
                                            # 使用 JavaScript 点击以避免 EPIPE 错误
                                            page.evaluate('(el) => el.click()', element)
                                                            
                                            print(f"[AUTO_CLICK] ✅ 已点击聊天入口，等待 API 请求...", flush=True)
                                            time.sleep(3)  # 等待 API 请求发起
                                            clicked = True
                                            break
                                if clicked:
                                    break
                            except Exception as e:
                                logger.debug(f"Try selector {selector} failed: {e}")
                                continue
                                        
                        if not clicked:
                            print(f"\n[INFO] 未找到可点击的聊天入口，继续监控背景流量...", flush=True)
                                            
                    except Exception as e:
                        logger.error(f"Auto-click error: {e}")
                        print(f"[INFO] 自动点击失败，继续监控...", flush=True)
                                    
                except Exception as ne:
                    logger.debug(f"Navigation warning: {ne}")

                # v6.16: Smart Maintenance Loop with Traffic Heartbeat + Auto Refresh
                last_check_time = time.time()
                check_interval = 120  # 每 2 分钟检查一次 Token 状态
                
                while not self._is_closing:
                    try:
                        if not context.pages: break
                        time.sleep(1)
                        curr = time.time()
                        uptime = int(curr - start_time)
                        
                        # Show listening status if NO traffic for 15s
                        if curr - self._last_traffic_time > 15:
                            print(f"[LISTENING] 正在监测背景流量... (UP: {uptime}s)", flush=True)
                            self._last_traffic_time = curr # Reset to avoid spam log
                            
                        if uptime % 60 == 0:
                            print(f"[SYSTEM] [ALIVE] 抓包引擎持续运行中... (UP: {uptime}s)", flush=True)
                        
                        # 定期检查 Token 状态并自动刷新
                        if curr - last_check_time >= check_interval:
                            last_check_time = curr
                            
                            # 检查是否需要刷新
                            if self.token_manager.needs_refresh() or self.token_manager.is_expired():
                                print(f"\n[AUTO_REFRESH] 🔄 检测到 Token 需要刷新...", flush=True)
                                print(self.token_manager.get_status_report(), flush=True)
                                
                                # 尝试静默刷新（打开新页面触发登录状态更新）
                                try:
                                    refresh_page = context.new_page()
                                    refresh_page.goto("https://designarena.ai/", wait_until="domcontentloaded", timeout=30000)
                                    print(f"[AUTO_REFRESH] ✅ 已触发后台刷新，等待 API 请求...", flush=True)
                                    time.sleep(5)  # 等待背景请求
                                    refresh_page.close()
                                    print(f"[AUTO_REFRESH] ✅ Token 刷新完成", flush=True)
                                except Exception as e:
                                    logger.debug(f"Auto-refresh failed: {e}")
                            else:
                                # 显示健康状态
                                remaining_minutes = 0
                                if self.token_manager.token_expires_at:
                                    remaining = self.token_manager.token_expires_at - datetime.now()
                                    remaining_minutes = remaining.seconds // 60
                                print(f"[TOKEN_STATUS] ✅ Token 健康，剩余时间：{remaining_minutes}分钟", flush=True)
                                
                    except Exception as e:
                        logger.debug(f"Maintenance loop error: {e}")
                        break
                
                # 关闭前保存最终状态
                self.token_manager.save_to_files()
                context.close()
            except Exception as e:
                logger.error(f"[MIRROR_LAUNCH_FAIL] {e}")
                print(f"\n[ERROR] 影子镜像挂载失败。请彻底关闭所有 Chrome 窗口后再试。\n")
            finally:
                logger.info("🔒 [PLAYWRIGHT_END] Managed session ended.")

    def launch_refresh(self, success_callback):
        """
        v10.0 Enhanced Background Refresh: Always sync from real Chrome profile.
        Directly extracts cookies and uses real Chrome data for maximum reliability.
        """
        logger.info(f"🔄 [REFRESH_START] 启动 v10.0 增强后台静默刷新 (账号：{self.account_id})")
        
        chrome_path = find_chrome_executable()
        
        # v10.0: ALWAYS sync from real Chrome profile for maximum freshness
        logger.info(f"[REFRESH] 🔄 正在从真实 Chrome 同步最新数据...")
        mirror_path = setup_mirror_profile()
        logger.info(f"[REFRESH] ✅ 真实 Chrome 数据已同步：{mirror_path}")
        
        with sync_playwright() as p:
            self._is_closing = False
            try:
                # v9.0: Enhanced Headless Mode with anti-detection
                context = p.chromium.launch_persistent_context(
                    user_data_dir=mirror_path,  
                    executable_path=chrome_path,
                    channel="chrome",
                    headless=True,
                    args=[
                        "--headless=new",
                        "--remote-allow-origins=*",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--no-sandbox"
                    ]
                )
                logger.info("[REFRESH] ✅ v9.0 静默引擎启动成功")
                
                # Apply Stealth & Sniffer
                page = context.pages[0] if context.pages else context.new_page()
                self._apply_stealth(page)

                def on_request(request):
                    if self._is_closing: return
                    try:
                        url = request.url
                        headers = request.headers
                        
                        # v9.0 Enhanced Token Sniffer
                        import re
                        TOKEN_PATTERN = r"Bearer\s+(ey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*)"
                        
                        found_token = None
                        for h_val in headers.values():
                            match = re.search(TOKEN_PATTERN, str(h_val))
                            if match:
                                found_token = match.group(1)
                                break
                        
                        if found_token:
                            logger.info(f"✨ [REFRESH_SUCCESS] 捕获到刷新令牌！(来源: {url[:50]}...)")
                            cookie = headers.get('cookie') or headers.get('Cookie') or ""
                            self.token_manager.update_token(found_token, cookie, expires_in_minutes=60)
                            success_callback(found_token, cookie)
                            self._is_closing = True
                    except Exception as e:
                        logger.debug(f"[REFRESH] Request sniff error: {e}")

                def on_response(response):
                    if self._is_closing: return
                    try:
                        # v9.0: Enhanced Response Sniffing
                        url = response.url
                        if "/api/" in url or "/v1/" in url:
                            try:
                                body_text = response.text()
                                import re
                                JWT_REGEX = r"(ey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*)"
                                match = re.search(JWT_REGEX, body_text)
                                if match:
                                    token = match.group(1)
                                    if len(token) > 100:
                                        logger.info(f"💎 [DEEP_CAPTURE] 从响应体中捕获到令牌！(来源: {url[:50]}...)")
                                        self.captured_token = token
                                        cookie = response.request.headers.get('cookie') or response.request.headers.get('Cookie') or ""
                                        self.token_manager.update_token(token, cookie, expires_in_minutes=60)
                                        success_callback(token, cookie)
                                        self._is_closing = True
                            except:
                                pass
                    except Exception as e:
                        logger.debug(f"[REFRESH] Response sniff error: {e}")

                context.on("request", on_request)
                context.on("response", on_response)

                # v9.0: Robust Navigation Strategy (using www as per actual site)
                target_urls = [
                    "https://www.designarena.ai/"
                ]
                
                for url_idx, target_url in enumerate(target_urls):
                    if self._is_closing:
                        break
                    
                    try:
                        logger.info(f"[REFRESH] 🔄 访问目标页面: {target_url}")
                        page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
                        logger.info("[REFRESH] ✅ 页面首屏就绪")
                        time.sleep(4)
                        
                        # v10.0: Enhanced strategies - first get cookies directly, then trigger API traffic
                        strategies = [
                            ("extract_cookies", lambda: self._try_extract_cookies_directly(context)),
                            ("auto_click", lambda: self._try_auto_click(page)),
                            ("api_ping", lambda: self._try_api_ping(context)),
                            ("scroll_interact", lambda: self._try_scroll_interact(page))
                        ]
                        
                        for strategy_name, strategy_func in strategies:
                            if self._is_closing:
                                break
                            try:
                                logger.info(f"[REFRESH] 执行策略: {strategy_name}")
                                strategy_func()
                                time.sleep(4)
                            except Exception as e:
                                logger.debug(f"[REFRESH] Strategy {strategy_name} failed: {e}")
                    
                    except Exception as e:
                        logger.warning(f"[REFRESH] 访问 {target_url} 异常: {e}")
                
                # v9.0: Snapshot for debugging
                try:
                    snapshot_path = os.path.join(CONFIG["ROOT"], "data", "refresh_snapshot.png")
                    page.screenshot(path=snapshot_path)
                    logger.info(f"📸 [REFRESH_DEBUG] 已保存后台快照: {snapshot_path}")
                except Exception as e:
                    logger.debug(f"[REFRESH] Snapshot failed: {e}")

                # v9.0: Extended monitor loop - 90 seconds total
                logger.info("[REFRESH] ⏳ 等待 Token 捕获 (最长 90 秒)...")
                for i in range(90):
                    if self._is_closing:
                        break
                    time.sleep(1)
                    if (i + 1) % 15 == 0:
                        logger.info(f"[REFRESH] ⏳ 已等待 {i + 1} 秒...")
                
            except Exception as e:
                logger.error(f"[REFRESH_ERROR] {e}")
            finally:
                try:
                    context.close()
                except:
                    pass
                logger.info(f"🔒 [REFRESH_END] 后台刷新关闭")

    def _try_auto_click(self, page):
        """Strategy 1: Try to auto-click chat-related elements"""
        chat_selectors = [
            'a[href*="/chat"]',
            'a[href*="/chats"]',
            'button:has-text("Chat")',
            'button:has-text("聊天")',
            'nav a:has-text("Chat")',
            'header a:has-text("Chat")',
            '[role="button"]:has-text("Chat")',
            '.chat-btn',
            '#chat-button'
        ]
        
        for selector in chat_selectors:
            try:
                elements = page.query_selector_all(selector)
                for el in elements:
                    if el and el.is_visible():
                        try:
                            box = el.bounding_box()
                            if box and box['width'] > 0 and box['height'] > 0:
                                logger.info(f"[REFRESH] 执行静默点击: {selector}")
                                page.evaluate('(el) => el.click()', el)
                                time.sleep(3)
                                return
                        except:
                            continue
            except:
                continue

    def _try_api_ping(self, context):
        """v10.0 Strategy 2: Enhanced API ping with cookie extraction"""
        try:
            # First, extract cookies directly before making API call
            cookies = context.cookies()
            cookie_str = ""
            if cookies:
                cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
                logger.info(f"[REFRESH] API ping 前已提取 {len(cookies)} 个 Cookie")
            
            # Try to fetch the actual /api/chats endpoint to trigger token usage
            logger.info("[REFRESH] 正在调用 /api/chats API...")
            
            # Prepare headers - include cookies if available
            headers = {
                "Content-Type": "application/json",
                "Accept": "*/*"
            }
            
            # Use Playwright's request API to make the call
            result = context.request.post(
                "https://www.designarena.ai/api/chats",
                headers=headers,
                data={
                    "prompt": "a simple refresh test"
                }
            )
            
            logger.info(f"[REFRESH] API 调用完成，状态码: {result.status}")
            
            # If API call is successful (200), we can use this opportunity
            # to refresh our token/cookie even if no new token was sniffed
            if result.status == 200:
                logger.info("[REFRESH] ✅ API 调用成功！")
                
                # Re-extract cookies after API call (they might have been updated)
                updated_cookies = context.cookies()
                if updated_cookies:
                    updated_cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in updated_cookies])
                    
                    # If we have an existing token, update it with fresh cookies
                    if self.token_manager.current_token:
                        logger.info("[REFRESH] 🔄 使用现有 Token 并更新 Cookie")
                        self.token_manager.update_token(
                            self.token_manager.current_token,
                            updated_cookie_str,
                            expires_in_minutes=60
                        )
            
            time.sleep(3)  # Wait for the request to complete and token to be captured
        except Exception as e:
            logger.debug(f"[REFRESH] API ping error: {e}")

    def _try_scroll_interact(self, page):
        """Strategy 3: Scroll and interact with the page"""
        try:
            # Scroll down and up
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(1)
        except:
            pass

    def _try_extract_cookies_directly(self, context):
        """v10.0 Strategy 0: Extract cookies directly from browser context"""
        try:
            logger.info("[REFRESH] 🔑 正在从浏览器上下文直接提取 Cookie...")
            
            # Get all cookies from context
            cookies = context.cookies()
            
            if not cookies:
                logger.debug("[REFRESH] 未找到 Cookie")
                return
            
            # Format cookies into cookie string
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            
            logger.info(f"[REFRESH] ✅ 成功提取 {len(cookies)} 个 Cookie")
            
            # If we already have a token from previous capture, update with fresh cookies
            if self.token_manager.current_token:
                logger.info("[REFRESH] 🔄 使用现有 Token 并更新 Cookie")
                self.token_manager.update_token(
                    self.token_manager.current_token,
                    cookie_str,
                    expires_in_minutes=60
                )
                # Note: We don't call success_callback here since we're just updating cookies
            
        except Exception as e:
            logger.debug(f"[REFRESH] Direct cookie extraction failed: {e}")


    def _apply_stealth(self, page: Page):
        """v8.0: Injects proven stealth patterns."""
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
        """)
        stealth_sync(page)

    def _init_page(self, page: Page, url: str):
        """Initializes page and automatically handles introductory terms."""
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
            
            # v6.1: Industrial Auto-Accept Terms (Ported from reference project)
            self._handle_modal_terms(page)
            self._handle_page_terms(page)
            
            # v6.2: Inject Cyber-Active HUD (Wow Factor)
            self._inject_cyber_hud(page)
            
        except Exception as e:
            logger.error(f"Page init failed: {e}")

    def _handle_modal_terms(self, page: Page):
        """Handles TOS modals/popups automatically."""
        try:
            # 1. Check for checkboxes
            checkboxes = page.query_selector_all('input[type="checkbox"]')
            for cb in checkboxes:
                if cb.is_visible() and not cb.is_checked():
                    cb.evaluate('(el) => el.click()')
                    time.sleep(0.5)
            
            # 2. Click confirm buttons
            btn_selectors = [
                'button:has-text("同意")', 'button:has-text("继续")', 
                'button:has-text("Accept")', 'button:has-text("Continue")',
                'button:has-text("Agree")', 'button:has-text("确定")'
            ]
            for sel in btn_selectors:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.evaluate('(el) => el.click()')
                    time.sleep(1)
                    break
        except: pass

    def _handle_page_terms(self, page: Page):
        """Handles main page TOS checkboxes/buttons."""
        # Similar logic to modal but targeting main content
        self._handle_modal_terms(page)

    def _inject_cyber_hud(self, page: Page):
        """Injects a premium, semi-transparent HUD onto the site for real-time status."""
        page.evaluate("""
            const hud = document.createElement('div');
            hud.id = 'cyber-hud';
            hud.innerHTML = `
                <div style="position: fixed; top: 20px; right: 20px; z-index: 999999; 
                            background: rgba(2, 2, 5, 0.9); border: 2px solid #00d2ff; 
                            border-radius: 15px; padding: 15px 25px; color: #FFF; 
                            font-family: 'Segoe UI', sans-serif; box-shadow: 0 0 30px rgba(0, 210, 255, 0.4);
                            backdrop-filter: blur(10px); display: flex; align-items: center; gap: 15px;">
                    <div style="width: 12px; height: 12px; background: #00FFC2; border-radius: 50%; box-shadow: 0 0 10px #00FFC2;"></div>
                    <div>
                        <div style="font-weight: 900; font-size: 14px; letter-spacing: 1px;">DESIGN.ARENA // 2API PRO</div>
                        <div style="font-size: 11px; color: #00d2ff; opacity: 0.8;">CYBER-ACTIVE: MONITORING TRAFFIC...</div>
                    </div>
                </div>
            `;
            document.body.appendChild(hud);
        """)

def start_login_thread(account_id: str, callback):
    """Utility to run the login flow in a background thread."""
    import threading
    pm = PlaywrightManager(account_id)
    t = threading.Thread(target=lambda: pm.launch_login(callback), daemon=True)
    t.start()
    return t

def start_refresh_thread(account_id: str, callback):
    """Utility to run the headless refresh in a background thread."""
    import threading
    pm = PlaywrightManager(account_id)
    t = threading.Thread(target=lambda: pm.launch_refresh(callback), daemon=True)
    t.start()
    return t
