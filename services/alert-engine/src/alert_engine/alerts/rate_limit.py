from __future__ import annotations

import threading
import time
from collections import deque


class GlobalSendRateLimiter:
    """Token bucket: max `rate_per_sec` sends per second (float)."""

    def __init__(self, rate_per_sec: float) -> None:
        self._rate = max(0.1, rate_per_sec)
        self._lock = threading.Lock()
        self._last = 0.0
        self._tokens = self._rate

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._last = now
            self._tokens = min(self._rate, self._tokens + elapsed * self._rate)
            if self._tokens < 1:
                sleep_for = (1 - self._tokens) / self._rate
                time.sleep(max(0.001, sleep_for))
                self._tokens = 0
            else:
                self._tokens -= 1


class PerChatMinuteLimiter:
    """Sliding window: max `cap` events per chat per 60s wall clock."""

    def __init__(self, cap: int) -> None:
        self._cap = max(1, cap)
        self._lock = threading.Lock()
        self._hits: dict[int, deque[float]] = {}

    def acquire(self, chat_id: int) -> bool:
        now = time.time()
        with self._lock:
            q = self._hits.setdefault(chat_id, deque())
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self._cap:
                return False
            q.append(now)
            return True
