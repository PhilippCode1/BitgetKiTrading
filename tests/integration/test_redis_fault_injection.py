"""
Redis: leichte Fault-Injection / Wiederanlauf ohne externe Tools.

Nutzt TEST_REDIS_URL (CI: DB-Index 1).
"""

from __future__ import annotations

import os

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.stack_recovery]


def test_redis_recovers_after_response_error_new_connection(
    integration_redis_client,
) -> None:
    import redis

    url = (os.getenv("TEST_REDIS_URL") or "").strip()
    key = "integration:prompt35:chaos_type"
    r1 = redis.Redis.from_url(url, socket_connect_timeout=3, socket_timeout=3)
    try:
        r1.delete(key)
        r1.set(key, "string_value")
        with pytest.raises(redis.exceptions.ResponseError):
            r1.rpush(key, "x")
    finally:
        r1.close()

    assert integration_redis_client.get(key) == b"string_value"
    assert integration_redis_client.ping() is True
    integration_redis_client.delete(key)


def test_redis_pipeline_burst_then_consistent_read(
    integration_redis_client,
) -> None:
    prefix = "integration:prompt35:pipe:"
    try:
        pipe = integration_redis_client.pipeline(transaction=False)
        for i in range(50):
            pipe.set(f"{prefix}{i}", i, ex=60)
        pipe.execute()
        assert int(integration_redis_client.get(f"{prefix}0")) == 0
    finally:
        for i in range(50):
            integration_redis_client.delete(f"{prefix}{i}")
