from __future__ import annotations

import asyncio
import time


class RateLimiter:
    def __init__(self, max_per_sec: int) -> None:
        if max_per_sec <= 0:
            raise ValueError("max_per_sec muss > 0 sein")
        self.max_per_sec = max_per_sec
        self._tokens = float(max_per_sec)
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self._last
                self._last = now
                self._tokens = min(
                    float(self.max_per_sec),
                    self._tokens + elapsed * self.max_per_sec,
                )
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait_for = (1.0 - self._tokens) / self.max_per_sec
                await asyncio.sleep(wait_for)
