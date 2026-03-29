# -*- coding: utf-8 -*-
import pytest
import time
import asyncio
from core.scheduler import SmartLoadBalancer
from core.limiter import TokenLimiter
from core.manager import GlobalState

@pytest.mark.asyncio
async def test_smart_balancer_rotation():
    balancer = SmartLoadBalancer()
    # Mock accounts
    GlobalState.accounts = [{"id": "A", "token": "T1"}, {"id": "B", "token": "T2"}]
    
    acc1 = await balancer.get_next_account()
    acc2 = await balancer.get_next_account()
    
    assert acc1["id"] != acc2["id"]
    assert balancer.health_map["A"].active_tasks == 1
    assert balancer.health_map["B"].active_tasks == 1

@pytest.mark.asyncio
async def test_balancer_cool_off():
    balancer = SmartLoadBalancer()
    GlobalState.accounts = [{"id": "A", "token": "T1"}]
    
    balancer.record_failure("A", is_rate_limit=True)
    acc = await balancer.get_next_account()
    assert acc is None

@pytest.mark.asyncio
async def test_token_limiter():
    # Rate: 2 tokens per 1 second
    limiter = TokenLimiter(rate=2, per=1)
    
    start = time.time()
    await limiter.wait_for_token()
    await limiter.wait_for_token()
    
    # Third one should wait
    task = asyncio.create_task(limiter.wait_for_token())
    await asyncio.sleep(0.1)
    assert not task.done()
    
    # Wait for token replenishment
    await asyncio.sleep(0.5)
    assert task.done()
