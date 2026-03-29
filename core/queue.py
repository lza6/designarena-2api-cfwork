# -*- coding: utf-8 -*-
import asyncio
import uuid
import time
from typing import Dict, Optional, Callable

class Task:
    def __init__(self, account_id: str, prompt: str, image_url: Optional[str] = None) -> None:
        self.id: str = str(uuid.uuid4())
        self.account_id: str = account_id
        self.prompt: str = prompt
        self.image_url: Optional[str] = image_url
        self.status: str = "QUEUED" # QUEUED, PROCESSING, COMPLETED, FAILED
        self.progress: int = 0
        self.message: str = "等待中..."
        self.result: Optional[dict] = None
        self.error: Optional[str] = None
        self.created_at: float = time.time()

class TaskQueue:
    def __init__(self, max_size=100):
        self.queue = asyncio.Queue(max_size)
        self.tasks: Dict[str, Task] = {}
        self.on_task_update: Optional[Callable] = None
        self.active_count = 0

    def add_task(self, account_id: str, prompt: str, image_url: Optional[str] = None) -> str:
        task = Task(account_id, prompt, image_url)
        self.tasks[task.id] = task
        self.queue.put_nowait(task)
        return task.id

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def set_callback(self, callback: Callable):
        self.on_task_update = callback

    async def _notify(self, task: Task):
        if self.on_task_update:
            if asyncio.iscoroutinefunction(self.on_task_update):
                await self.on_task_update(task)
            else:
                self.on_task_update(task)

    async def worker(self, process_fn: Callable):
        """
        process_fn(prompt, image_url, on_progress_callback, account_id) -> result
        """
        while True:
            task = await self.queue.get()
            self.active_count += 1
            task.status = "PROCESSING"
            task.message = "正在准备生成..."
            await self._notify(task)

            async def on_progress(msg, progress):
                task.message = msg
                task.progress = progress
                await self._notify(task)

            try:
                # result = await process_fn(task.prompt, task.image_url, on_progress, task.account_id)
                # Ensure the process_fn handles all necessary arguments
                task.result = await process_fn(task.prompt, task.image_url, on_progress, task.account_id)
                task.status = "COMPLETED"
                task.progress = 100
                task.message = "生成完成"
            except Exception as e:
                task.status = "FAILED"
                task.error = str(e)
                task.message = f"生成失败: {str(e)}"
            
            await self._notify(task)
            self.active_count -= 1
            self.queue.task_done()

_global_queue = TaskQueue()
