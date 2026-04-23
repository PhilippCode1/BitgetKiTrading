from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any


class CircuitBreaker:
    """
    Schiebefenster: N Degradationen (5xx/Timeout) oeffnet den Circuit.
    Kein 429; Erfolg setzt Ereignis-Fenster zurueck.
    """

    def __init__(
        self,
        *,
        fail_threshold: int,
        open_seconds: int,
        window_seconds: int = 60,
    ) -> None:
        self._fail_threshold = max(1, fail_threshold)
        self._open_seconds = max(1, open_seconds)
        self._window_seconds = max(1, window_seconds)
        self._degraded_events: dict[str, deque[float]] = {}
        self._open_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def is_open(self, key: str) -> bool:
        with self._lock:
            until = self._open_until.get(key)
            if until is None:
                return False
            if time.monotonic() < until:
                return True
            del self._open_until[key]
            self._degraded_events.pop(key, None)
            return False

    def record_success(self, key: str) -> None:
        with self._lock:
            self._degraded_events.pop(key, None)
            self._open_until.pop(key, None)

    def record_upstream_degraded(self, key: str) -> None:
        """5xx/Timeout-Event; zaehlt im Schiebefenster."""
        with self._lock:
            now = time.monotonic()
            q = self._degraded_events.setdefault(key, deque())
            bound = now - self._window_seconds
            while q and q[0] < bound:
                q.popleft()
            q.append(now)
            if len(q) >= self._fail_threshold:
                self._open_until[key] = now + self._open_seconds
                q.clear()

    def state_snapshot(self) -> dict[str, Any]:
        with self._lock:
            now = time.monotonic()
            open_keys = sorted(
                k for k, until in self._open_until.items() if now < until
            )
            in_window: dict[str, int] = {}
            for k, q in self._degraded_events.items():
                bound = now - self._window_seconds
                c = sum(1 for t in q if t >= bound)
                if c:
                    in_window[k] = c
            return {
                "window_seconds": self._window_seconds,
                "fail_threshold": self._fail_threshold,
                "degraded_in_window": in_window,
                "open_until_mono": dict(self._open_until),
                "providers_currently_open": open_keys,
            }
