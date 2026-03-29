# -*- coding: utf-8 -*-
import asyncio
import time
from typing import List, Optional
from core.manager import GlobalState
from core.logger import logger

class AccountHealth:
    def __init__(self, account_id: str) -> None:
        self.account_id: str = account_id
        self.failures: int = 0
        self.active_tasks: int = 0
        self.last_failure_time: float = 0
        self.last_success_time: float = 0
        self.cool_off_until: float = 0

class SmartLoadBalancer:
    def __init__(self):
        self.health_map: dict[str, AccountHealth] = {}
        self._lock = asyncio.Lock()

    def _get_health(self, aid: str) -> AccountHealth:
        if aid not in self.health_map:
            self.health_map[aid] = AccountHealth(aid)
        return self.health_map[aid]

    async def get_next_account(self) -> Optional[dict]:
        """Smart Selection: Prioritize idle and healthy accounts."""
        async with self._lock:
            accounts = GlobalState.accounts
            if not accounts: return None
            
            now = time.time()
            candidates = []
            
            for acc in accounts:
                h = self._get_health(acc["id"])
                # Skip if in cool-off
                if now < h.cool_off_until: continue
                
                # Weight = Active Tasks * 10 + Failures
                # We want the lowest weight
                weight = (h.active_tasks * 10) + (h.failures * 5)
                candidates.append((weight, acc))
            
            if not candidates:
                logger.warning("Load Balancer: All accounts are in cool-off or unavailable.")
                return None
                
            # Sort by weight (Lowest first)
            candidates.sort(key=lambda x: x[0])
            selected = candidates[0][1]
            
            # Increment active task count for the selected account
            h = self._get_health(selected["id"])
            h.active_tasks += 1
            
            logger.info(f"Load Balancer: Selected account {selected['id']} (Active Tasks: {h.active_tasks})")
            return selected

    def record_success(self, aid: str) -> None:
        h: AccountHealth = self._get_health(aid)
        h.failures = max(0, h.failures - 1)
        h.active_tasks = max(0, h.active_tasks - 1)
        h.last_success_time = time.time()
        
        # v6.0: Increment persistent usage counter
        for a in GlobalState.accounts:
            if a["id"] == aid:
                a["total_calls"] = a.get("total_calls", 0) + 1
                GlobalState.save()
                break

    def record_failure(self, aid: str, is_rate_limit: bool = False) -> None:
        h: AccountHealth = self._get_health(aid)
        h.failures += 1
        h.active_tasks = max(0, h.active_tasks - 1)
        h.last_failure_time = time.time()
        
        if is_rate_limit:
            # 5-minute cool-off for rate limits
            h.cool_off_until = time.time() + 300
            logger.warning(f"Load Balancer: Account {aid} rate limited. Cool-off for 5m.")
        elif h.failures >= 3:
            # 1-minute cool-off for consecutive failures
            h.cool_off_until = time.time() + 60
            logger.warning(f"Load Balancer: Account {aid} too many failures. Cool-off for 1m.")

_global_balancer = SmartLoadBalancer()
