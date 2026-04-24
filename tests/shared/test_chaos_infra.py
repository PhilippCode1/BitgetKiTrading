from __future__ import annotations

import os
import time

import pytest
import redis

from shared_py.chaos.infra_chaos import (
    ChaosCallCounter,
    connection_refused_factory,
    wrap_redis_with_chaos_latency,
)


def test_chaos_counter_hits_every_n() -> None:
    c = ChaosCallCounter(every_n=3)
    hits = [c.is_chaos_hit() for _ in range(9)]
    assert hits[2] is True
    assert hits[0] is False
    assert hits[1] is False


@pytest.mark.skipif(redis is None, reason="redis fehlt")
def test_chaos_redis_injects_delay() -> None:
    u = (os.environ.get("TEST_REDIS_URL") or "").strip()
    if not u:
        pytest.skip("TEST_REDIS_URL")
    c = redis.Redis.from_url(
        u, decode_responses=True, socket_connect_timeout=1, socket_timeout=0.2
    )
    wrap_redis_with_chaos_latency(c, every_n=2, delay_sec=0.4)
    t0 = time.monotonic()
    with pytest.raises(redis.exceptions.TimeoutError):
        c.ping()
        c.ping()
    assert time.monotonic() - t0 >= 0.3
    c.close()


def test_connection_refused_factory() -> None:
    import errno

    e = connection_refused_factory()
    assert e.errno == errno.ECONNREFUSED
