# -*- coding: utf-8 -*-
import time
from typing import Dict, Any, Optional

class TTLCache:
    def __init__(self, ttl: int = 3600):
        self.ttl = ttl
        self.cache: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry["timestamp"] < self.ttl:
                return entry["data"]
            del self.cache[key]
        return None

    def set(self, key: str, data: Any):
        self.cache[key] = {
            "data": data,
            "timestamp": time.time()
        }

    def clear(self):
        self.cache.clear()

_global_cache = TTLCache()
