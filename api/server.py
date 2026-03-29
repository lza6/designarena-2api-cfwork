# -*- coding: utf-8 -*-
import json
import asyncio
import time
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.config import CONFIG
from core.manager import GlobalState
from core.client import DesignArenaClient, _cb
from core.queue import _global_queue, Task
from core.cache import _global_cache
from core.logger import logger
from core.metrics import get_metrics as get_metrics_collector
from core.health_monitor import get_health_monitor

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_headers=["*"], allow_methods=["*"])

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    logger.info(f"NETWORK | {request.method} {request.url.path} | STATUS: {response.status_code} | {duration:.2f}s")
    return response

class ChatReq(BaseModel):
    model: Optional[str] = "designarena-image"
    messages: List[dict]
    stream: Optional[bool] = True

from core.scheduler import _global_balancer

# Start Task Queue Worker
@app.on_event("startup")
async def startup_event():
    app.start_time = time.time()
    logger.info("API Server Starting Up")
    
    async def process_task(prompt, image_url, on_progress, account_id=None):
        # Multi-Account Scheduler: If no ID, get next available
        acc = None
        if account_id:
            for a in GlobalState.accounts:
                if a["id"] == account_id: acc = a; break
        if not acc:
            acc = await _global_balancer.get_next_account()
        
        if not acc: raise Exception("No accounts available for processing")
        cookie = acc.get("cookie")
        return await DesignArenaClient.execute_flow(prompt, image_url, acc["token"], acc["id"], on_progress, cookie=cookie, ip="127.0.0.1", ua="EnterpriseScheduler/1.0")

    # Dynamic Workers: Start 3 workers for improved throughput
    for _ in range(3):
        asyncio.create_task(_global_queue.worker(process_task))

@app.get("/health")
async def health_check():
    return {
        "status": "healthy" if _cb.state != "OPEN" else "degraded",
        "circuit_breaker": _cb.state,
        "active_accounts": len(GlobalState.accounts),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/metrics")
async def get_metrics(format: Optional[str] = "json"):
    """
    获取系统指标
    :param format: 输出格式 (json/prometheus)
    """
    metrics = get_metrics_collector()
    
    if format == "prometheus":
        from fastapi.responses import PlainTextResponse
        return PlainTextContent(
            content=metrics.to_prometheus(),
            media_type="text/plain"
        )
    
    # JSON 格式
    return {
        "timestamp": datetime.now().isoformat(),
        "metrics": metrics.get_all()
    }


@app.get("/health")
async def health_check():
    """健康检查端点"""
    monitor = get_health_monitor()
    report = monitor.get_health_report()
    
    return {
        "status": report["overall_status"],
        "timestamp": report["timestamp"],
        "components": report["components"]
    }

@app.get("/v1/models")
async def list_models():
    cached = _global_cache.get("models")
    if cached: return cached
    models = {
        "object": "list",
        "data": [{"id": m, "object": "model", "created": int(time.time()), "owned_by": "designarena"} for m in ["designarena-image", "dall-e-3"]]
    }
    _global_cache.set("models", models)
    return models

import threading as _threading

_refresh_lock = _threading.Lock()
_last_demand_refresh = 0  # Cooldown tracker

async def _on_demand_refresh():
    """v8.5: On-demand token refresh when API request detects expired token."""
    global _last_demand_refresh
    from core.token_manager import get_token_manager
    import time as _time

    tm = get_token_manager()
    if not tm.is_expired() and not tm.needs_refresh():
        return  # Token is still valid

    # Cooldown: Don't retry within 60 seconds of last attempt
    if _time.time() - _last_demand_refresh < 60:
        logger.info("[AUTO_RENEWAL] ⏳ 续杯冷却中 (60s)，跳过此次检查")
        return

    if not _refresh_lock.acquire(blocking=False):
        logger.info("[AUTO_RENEWAL] 🔒 另一个续杯任务正在执行，跳过")
        return

    try:
        _last_demand_refresh = _time.time()
        logger.info("🔄 [AUTO_RENEWAL] API 检测到 Token 过期/需刷新，启动即时续杯...")

        refresh_event = _threading.Event()
        new_token_holder = [None]

        def on_refresh_done(token, cookie=""):
            new_token_holder[0] = token
            for a in GlobalState.accounts:
                if a.get("token"):
                    a["token"] = token
                    if cookie:
                        a["cookie"] = cookie
            GlobalState.active_token = token
            if cookie:
                GlobalState.active_cookie = cookie
            GlobalState.save()
            logger.info(f"✨ [AUTO_RENEWAL] 即时续杯成功！新 Token: {token[:20]}...")
            refresh_event.set()

        def run_refresh():
            try:
                from core.browser import PlaywrightManager
                aid = GlobalState.active_account_id or "auto_renewal"
                pm = PlaywrightManager(account_id=aid)
                pm.launch_refresh(success_callback=on_refresh_done)
            except Exception as e:
                logger.error(f"[AUTO_RENEWAL] 续杯失败: {e}")
            finally:
                refresh_event.set()

        t = _threading.Thread(target=run_refresh, daemon=True)
        t.start()

        # Non-blocking wait: poll the event in small intervals
        for _ in range(180):  # 90 seconds max (180 * 0.5s)
            if refresh_event.is_set():
                break
            await asyncio.sleep(0.5)

        if new_token_holder[0]:
            logger.info("[AUTO_RENEWAL] ✅ 即时续杯完成，请求将使用新 Token 继续执行")
        else:
            logger.warning("[AUTO_RENEWAL] ⚠️ 续杯超时，将使用现有 Token 尝试")
    finally:
        _refresh_lock.release()

@app.post("/v1/chat/completions")
async def chat_completions(req: ChatReq, r: Request):
    # v8.5: On-demand auto-renewal check
    await _on_demand_refresh()

    acc = await _global_balancer.get_next_account()
    if not acc:
        aid = GlobalState.active_account_id
        token = GlobalState.active_token
        cookie = GlobalState.active_cookie
    else:
        aid = acc["id"]
        token = acc["token"]
        cookie = acc.get("cookie")
        
    if not aid or not token: raise HTTPException(status_code=400, detail="无活跃账号")
    
    ip = r.client.host
    ua = r.headers.get("user-agent")

    prompt = "an image"; image_url = None
    for m in reversed(req.messages):
        c = m.get("content")
        if isinstance(c, str): prompt = c
        elif isinstance(c, list):
            for p in c:
                if p["type"]=="text": prompt=p["text"]
                if p["type"]=="image_url": image_url=p["image_url"]["url"] if isinstance(p["image_url"],dict) else p["image_url"]

    if req.stream:
        async def event_generator():
            try:
                async def on_p(msg, val):
                    yield f"data: {json.dumps({'choices':[{'index':0,'delta':{'content':f'[{msg}] '}}]}, ensure_ascii=False)}\n\n"
                
                result = await DesignArenaClient.execute_flow(prompt, image_url, token, aid, on_p, cookie=cookie, ip=ip, ua=ua)
                _global_balancer.record_success(aid)
                
                md = "### 🎨 DesignArena Result\n\n"
                
                # v9.0: Ultra-Flexible Result Parsing
                def extract_images(data):
                    imgs = []
                    # 1. Check nested tournament structure (legacy/v1)
                    for g in data.get("tournament", {}).get("generations", []):
                        if g.get("imageUrl"): imgs.append(g["imageUrl"])
                    # 2. Check root-level generations (v2/new)
                    for g in data.get("generations", []):
                        if g.get("imageUrl"): imgs.append(g["imageUrl"])
                    # 3. Check data.generations (variant)
                    if isinstance(data.get("data"), dict):
                        for g in data["data"].get("generations", []):
                            if g.get("imageUrl"): imgs.append(g["imageUrl"])
                    return list(set(imgs)) # De-duplicate

                found_imgs = extract_images(result)
                if found_imgs:
                    for img in found_imgs:
                        md += f"![Generated Image]({img})\n\n"
                else:
                    if result.get("success"):
                        md += "✅ 生成已触发，结果可能在处理中或无图片输出。\n"
                    else:
                        md += "⚠️ 任务已完成，但未检测到图像输出负载。\n"

                yield f"data: {json.dumps({'choices':[{'index':0,'delta':{'content':md},'finish_reason':'stop'}]}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                is_rl = "limit" in str(e).lower() or "429" in str(e)
                _global_balancer.record_failure(aid, is_rl)
                error_obj = {"error": {"message": str(e), "type": "server_error", "code": "generation_failed"}}
                yield f"data: {json.dumps(error_obj, ensure_ascii=False)}\n\n"
        return StreamingResponse(event_generator(), media_type="text/event-stream")
    else:
        try:
            result = await DesignArenaClient.execute_flow(prompt, image_url, token, aid, lambda m,v: None, cookie=cookie, ip=ip, ua=ua)
            _global_balancer.record_success(aid)
            
            # v7.5: Align non-streaming with OpenAI schema
            # v9.0: Ultra-Flexible Result Parsing (Non-Streaming Sync)
            def extract_images(data):
                imgs = []
                for g in data.get("tournament", {}).get("generations", []):
                    if g.get("imageUrl"): imgs.append(g["imageUrl"])
                for g in data.get("generations", []):
                    if g.get("imageUrl"): imgs.append(g["imageUrl"])
                if isinstance(data.get("data"), dict):
                    for g in data["data"].get("generations", []):
                        if g.get("imageUrl"): imgs.append(g["imageUrl"])
                return list(set(imgs))

            found_imgs = extract_images(result)
            md = "### 🎨 DesignArena Result\n\n"
            if found_imgs:
                for img in found_imgs:
                    md += f"![Generated Image]({img})\n\n"
            else:
                if result.get("success"):
                    md += "✅ 生成已触发，结果可能在处理中或无图片输出。\n"
                else:
                    md += "⚠️ 任务已完成，但未检测到图像输出负载。\n"
            
            return {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": req.model,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": md},
                    "finish_reason": "stop"
                }]
            }
        except Exception as e:
            is_rl = "limit" in str(e).lower() or "429" in str(e)
            _global_balancer.record_failure(aid, is_rl)
            # v7.5: Standard OpenAI error format
            error_data = {
                "error": {
                    "message": str(e),
                    "type": "server_error",
                    "code": "timeout" if "Timeout" in str(e) else "api_error"
                }
            }
            return json.loads(json.dumps(error_data)) # Ensure JSON serializable

@app.websocket("/v1/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    async def task_callback(task: Task):
        try:
            await websocket.send_json({"type": "task_update", "task_id": task.id, "status": task.status, "progress": task.progress, "message": task.message})
        except: pass
    _global_queue.set_callback(task_callback)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect: pass

@app.post("/v1/tasks")
async def create_task(req: ChatReq):
    aid = GlobalState.active_account_id
    if not aid: raise HTTPException(status_code=400, detail="无活跃账号")
    prompt = "an image"; image_url = None
    for m in reversed(req.messages):
        c = m.get("content")
        if isinstance(c, str): prompt = c
        elif isinstance(c, list):
            for p in c:
                if p["type"]=="text": prompt=p["text"]
                if p["type"]=="image_url": image_url=p["image_url"]["url"] if isinstance(p["image_url"],dict) else p["image_url"]
    task_id = _global_queue.add_task(aid, prompt, image_url)
    return {"task_id": task_id, "status": "QUEUED"}

@app.get("/v1/tasks/{task_id}")
async def get_task_status(task_id: str):
    task = _global_queue.get_task(task_id)
    if not task: raise HTTPException(status_code=404, detail="任务不存在")
    return {"task_id": task.id, "status": task.status, "progress": task.progress, "message": task.message, "result": task.result, "error": task.error}
