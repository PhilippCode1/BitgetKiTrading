from __future__ import annotations

import time

from alert_engine.alerts.rate_limit import GlobalSendRateLimiter, PerChatMinuteLimiter


def test_per_chat_limit_blocks() -> None:
    lim = PerChatMinuteLimiter(2)
    assert lim.acquire(1) is True
    assert lim.acquire(1) is True
    assert lim.acquire(1) is False


def test_global_limiter_sleeps() -> None:
    lim = GlobalSendRateLimiter(100.0)
    t0 = time.monotonic()
    lim.acquire()
    lim.acquire()
    dt = time.monotonic() - t0
    assert dt < 0.5
