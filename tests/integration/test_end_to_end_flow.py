"""
Integrations-Checks: DB-Erreichbarkeit (Test-Compose), keine Live-Sleeps.
"""

from __future__ import annotations

import os

import pytest


@pytest.mark.integration
def test_test_database_connects() -> None:
    dsn = os.getenv("TEST_DATABASE_URL", "").strip()
    if not dsn:
        pytest.skip("TEST_DATABASE_URL nicht gesetzt (siehe .env.test.example)")
    import psycopg

    with psycopg.connect(dsn, connect_timeout=5) as conn:
        conn.execute("SELECT 1")


@pytest.mark.integration
def test_test_redis_pings() -> None:
    url = os.getenv("TEST_REDIS_URL", "").strip()
    if not url:
        pytest.skip("TEST_REDIS_URL nicht gesetzt")
    import redis

    r = redis.Redis.from_url(url, socket_connect_timeout=3, socket_timeout=3)
    assert r.ping()
