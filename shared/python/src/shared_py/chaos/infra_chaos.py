"""
Test-/Diagnose-Hilfen: künstliche Latenz und gezielte Fehler (Chaos) für Redis und gRPC-Pfade.
"""

from __future__ import annotations

import errno
import time
from typing import TypeVar

T = TypeVar("T")

try:
    import redis
except ImportError:  # pragma: no cover
    redis = None  # type: ignore[assignment]


class ChaosCallCounter:
    """Zähler für ``every_n``-Injektionen (z. B. jeder 10. Aufruf)."""

    def __init__(self, every_n: int = 10) -> None:
        self._n = max(1, int(every_n))
        self._c = 0

    def bump(self) -> int:
        self._c += 1
        return self._c

    def is_chaos_hit(self) -> bool:
        return self.bump() % self._n == 0


def chaos_delay_before_call(
    counter: ChaosCallCounter,
    *,
    delay_sec: float = 6.0,
) -> None:
    """Vor echtem I/O: optional künstliche Latenz oberhalb typischer Client-Deadlines (z. B. 5s)."""
    if counter.is_chaos_hit():
        time.sleep(float(max(0.0, delay_sec)))


def wrap_redis_with_chaos_latency(
    client: T,
    *,
    every_n: int = 10,
    delay_sec: float = 6.0,
) -> T:
    """
    Proxy um ``redis.Redis``: leitet ``execute_command`` mit gelegentlichem Sleep weiter.
    """
    if redis is None:
        raise RuntimeError("redis-Paket fehlt")
    r = client
    if not isinstance(r, redis.Redis):
        raise TypeError("erwartet redis.Redis")
    counter = ChaosCallCounter(every_n=every_n)
    real_exec = r.execute_command

    def _exec(*a: object, **kw: object) -> object:
        chaos_delay_before_call(counter, delay_sec=delay_sec)
        return real_exec(*a, **kw)

    r.execute_command = _exec  # type: ignore[assignment]
    return client


def connection_refused_factory() -> OSError:
    return OSError(errno.ECONNREFUSED, "Connection refused (chaos)")
