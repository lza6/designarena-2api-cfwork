# -*- coding: utf-8 -*-
import aiohttp
import asyncio
import json
import time
import os
import mimetypes
from typing import Optional, AsyncGenerator, Callable, Dict, Any
from core.config import CONFIG
from core.manager import GlobalState
from core.limiter import _global_limiter
from core.audit import log_task
from core.logger import logger

class TaskQueue:
    def __init__(self, max_size: int = 100) -> None:
        self.queue: asyncio.Queue = asyncio.Queue(max_size)
        self.tasks: Dict[str, Any] = {}
        self.on_task_update: Optional[Callable[[Any], Any]] = None
        self.active_count: int = 0

class CircuitBreaker:
    def __init__(self, threshold: int = 5, recovery_timeout: int = 60) -> None:
        self.threshold = threshold; self.recovery_timeout = recovery_timeout
        self.failures = 0; self.last_failure_time = 0; self.state = "CLOSED"

    def record_failure(self) -> None:
        self.failures += 1; self.last_failure_time = time.time()
        if self.failures >= self.threshold: self.state = "OPEN"; logger.error(f"Circuit Breaker TRIPPED")

    def record_success(self) -> None:
        self.failures = 0; self.state = "CLOSED"

    def can_request(self):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF-OPEN"; return True
            return False
        return True

_cb = CircuitBreaker()

# Lazy Session Management
_http_session: Optional[aiohttp.ClientSession] = None

# v7.1: DNS 缓存 (避免重复解析)
_dns_cache: Dict[str, str] = {}

async def get_session() -> aiohttp.ClientSession:
    global _http_session
    if _http_session is None or _http_session.closed:
        # v7.1: 优化连接池和 DNS 解析
        connector = aiohttp.TCPConnector(
            limit=0,
            keepalive_timeout=60,
            enable_cleanup_closed=True,
            use_dns_cache=True,  # ✅ 启用 DNS 缓存
            ttl_dns_cache=300,   # ✅ DNS 缓存 5 分钟
            resolver=aiohttp.AsyncResolver(nameservers=['8.8.8.8', '1.1.1.1'])  # ✅ 使用公共 DNS
        )
        
        # v7.1: 优化超时配置
        timeout = aiohttp.ClientTimeout(
            total=CONFIG["TIMEOUT_SECONDS"],
            connect=15,      # 连接超时 15 秒
            sock_read=60,    # 读取超时 60 秒
            sock_connect=10  # Socket 连接超时 10 秒
        )
        
        _http_session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            trace_configs=[aiohttp.TraceConfig()]  # 添加追踪配置用于调试
        )
        logger.info("[HTTP] 优化的 HTTP 会话已初始化 (DNS 缓存 + 公共 DNS)")
    return _http_session

class DesignArenaClient:
    @staticmethod
    async def upload_image(session: aiohttp.ClientSession, file_path_or_url: str, headers: dict):
        try:
            if os.path.isfile(file_path_or_url):
                file_name = os.path.basename(file_path_or_url)
                content_type, _ = mimetypes.guess_type(file_path_or_url)
                content_type = content_type or "image/png"
                with open(file_path_or_url, 'rb') as f: data = f.read()
            else: raise Exception("Only local file upload is supported currently.")

            logger.info(f"Uploading image: {file_name} ({content_type})")
            p = {"fileName": file_name, "contentType": content_type}
            async with session.post(f"{CONFIG['BASE_URL']}/api/voteNew/upload-url", headers=headers, json=p) as resp:
                res = await resp.json()
                upload_url = res.get("uploadUrl"); storage_path = res.get("storagePath")
                logger.info(f"Got signed URL. Storage path: {storage_path}")

            async with session.put(upload_url, data=data, headers={"Content-Type": content_type}) as resp:
                if resp.status != 200: raise Exception(f"Upload failed: {resp.status}")
                logger.info(f"Binary upload successful.")
            return storage_path
        except Exception as e: logger.error(f"Image Upload Failed: {e}"); raise e

    @staticmethod
    async def execute_flow(prompt: str, image_path: Optional[str], token: str, account_id: str, on_progress: Callable, cookie: str = None, ip: str = None, ua: str = None):
        """
        v7.1: 添加重试机制，应对 DNS 超时等临时错误
        """
        if not _cb.can_request(): raise Exception("熔断器已开启")
        await _global_limiter.wait_for_token(account_id)
        
        # v8.1: Hardened Industrial Headers
        real_ua = ua or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": real_ua,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "Referer": f"{CONFIG['BASE_URL']}/",
            "Origin": CONFIG['BASE_URL'],
            "X-Requested-With": "XMLHttpRequest",
            "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
        }
        if cookie:
            headers["Cookie"] = cookie
        
        session = await get_session()
        
        # v7.1: 重试逻辑 (最多 3 次)
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                storage_path = None
                if image_path:
                    logger.info(f"Flow-I2I: Starting image upload chain...")
                    on_progress("📤 [0/3] 同步素材...", 10)
                    storage_path = await DesignArenaClient.upload_image(session, image_path, headers)

                def _parse_id(data, primary_key, secondary_key=None):
                    if not isinstance(data, dict): return None
                    res = data.get(primary_key) or data.get("id") or data.get("_id")
                    if not res and "data" in data and isinstance(data["data"], dict):
                        res = data["data"].get(primary_key) or data["data"].get("id")
                    if not res and secondary_key:
                        res = data.get(secondary_key)
                    return res

                logger.info(f"Flow-Step 1: Creating Chat context...")
                on_progress("🚀 [1/3] 挂载信道...", 20)
                async with session.post(f"{CONFIG['BASE_URL']}/api/chats", headers=headers, json={"prompt": prompt}) as resp:
                    resp_json = await resp.json()
                    chat_id = _parse_id(resp_json, "chatId")
                    if not chat_id:
                        logger.warning(f"ChatID parsing failed. Raw response: {resp_json}")
                    logger.info(f"Chat Context created: {chat_id}")

                logger.info(f"Flow-Step 2: Starting Tournament submission...")
                on_progress(f"📡 [2/3] 构建矩阵...", 40)
                p = {"prompt": prompt, "arena": "models", "category": "image", "premiumMode": True, "chatId": chat_id, 
                     "inputImageStoragePath": storage_path, "inputImageStoragePaths": [storage_path] if storage_path else []}
                # Ensure chatId is at least an empty string if None to avoid URL breakage in some variants
                t_referer = f"{CONFIG['BASE_URL']}/chat/{chat_id}" if chat_id else f"{CONFIG['BASE_URL']}/chat"
                async with session.post(f"{CONFIG['BASE_URL']}/api/voteNew/tournament", headers={**headers, "Referer": t_referer}, json=p) as resp:
                    resp_json = await resp.json()
                    tour_id = _parse_id(resp_json, "tournamentId")
                    if not tour_id:
                        logger.warning(f"TournamentID parsing failed. Raw response: {resp_json}")
                    logger.info(f"Tournament ID acquired: {tour_id}")

                logger.info(f"Flow-Step 3: Triggering Generation...")
                on_progress("🎨 [3/3] 引擎渲染...", 60)
                if not tour_id:
                    raise Exception("Tournament ID missing! (Authentication might have failed)")
                
                gen_url = f"{CONFIG['BASE_URL']}/api/voteNew/tournament/{tour_id}/generate"
                async with session.post(gen_url, headers=headers, json={}) as resp:
                    res_data = await resp.json()
                    # v9.0: Ensure we pack the tournament results into the return if it's missing in some API versions
                    if res_data.get("success") and "tournament" not in res_data and tour_id:
                        logger.info("Injecting tournament data from ID...")
                        res_data["tournament"] = {"id": tour_id}
                    logger.info(f"Generation triggered successfully for account {account_id}")

                on_progress("✨ [Final] 完成导出", 100)
                _cb.record_success()
                log_task(account_id, "GENERATE", "SUCCESS", prompt, ip=ip, ua=ua)
                return res_data
                
            except Exception as e:
                last_error = e
                logger.warning(f"[尝试 {attempt + 1}/{max_retries}] 请求失败：{str(e)}")
                
                # 如果是 DNS 超时或连接错误，等待后重试
                if "Timeout" in str(e) or "connect" in str(e).lower():
                    if attempt < max_retries - 1:
                        wait_time = 2 * (attempt + 1)  # 指数退避：2 秒，4 秒
                        logger.info(f"⏳ 等待 {wait_time} 秒后重试...")
                        await asyncio.sleep(wait_time)
                    continue
                else:
                    # 其他错误直接抛出
                    raise e
        
        # 所有重试都失败
        logger.error(f"所有重试均失败，最后错误：{str(last_error)}")
        _cb.record_failure()
        log_task(account_id, "GENERATE", "FAILED", prompt, str(last_error), ip=ip, ua=ua)
        raise last_error
