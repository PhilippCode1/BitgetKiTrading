from __future__ import annotations

import threading
import time
from typing import Any


class CircuitBreaker:
    """Einfacher Circuit Breaker pro Ressource (z. B. Provider-Name)."""

    def __init__(self, *, fail_threshold: int, open_seconds: int) -> None:
        self._fail_threshold = max(1, fail_threshold)
        self._open_seconds = max(1, open_seconds)
        self._failures: dict[str, int] = {}
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
            self._failures[key] = 0
            return False

    def record_success(self, key: str) -> None:
        with self._lock:
            self._failures[key] = 0
            self._open_until.pop(key, None)

    def record_failure(self, key: str) -> None:
        with self._lock:
            n = self._failures.get(key, 0) + 1
            self._failures[key] = n
            if n >= self._fail_threshold:
                self._open_until[key] = time.monotonic() + self._open_seconds
                self._failures[key] = 0

    def state_snapshot(self) -> dict[str, Any]:
        with self._lock:
            now = time.monotonic()
            open_keys = sorted(
                k for k, until in self._open_until.items() if now < until
            )
            return {
                "failures": dict(self._failures),
                "open_until_mono": dict(self._open_until),
                "providers_currently_open": open_keys,
            }
