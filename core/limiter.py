# -*- coding: utf-8 -*-
import time
import asyncio
from typing import Dict

class TokenLimiter:
    def __init__(self, rate: int, per: int) -> None:
        self.rate: float = float(rate)
        self.per: float = float(per)
        self.allowance: float = float(rate)
        self.last_check: float = time.time()

    async def wait_for_token(self) -> bool:
        while True:
            now = time.time()
            time_passed = now - self.last_check
            self.last_check = now
            self.allowance += time_passed * (self.rate / self.per)
            if self.allowance > self.rate:
                self.allowance = float(self.rate)
            
            if self.allowance >= 1.0:
                self.allowance -= 1.0
                return True
            await asyncio.sleep(0.1)

RateLimiter = TokenLimiter # Alias for backward compatibility

class GlobalLimiter:
    def __init__(self) -> None:
        self._limiters: Dict[str, TokenLimiter] = {}

    async def wait_for_token(self, account_id: str) -> None:
        if account_id not in self._limiters:
            # 40 requests per 60 seconds (as requested)
            self._limiters[account_id] = TokenLimiter(40, 60)
        await self._limiters[account_id].wait_for_token()

_global_limiter: GlobalLimiter = GlobalLimiter()
