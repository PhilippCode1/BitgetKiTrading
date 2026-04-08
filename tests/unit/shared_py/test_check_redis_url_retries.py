from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import redis

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"
for candidate in (REPO_ROOT, str(SHARED_SRC)):
    if candidate not in sys.path:
        sys.path.insert(0, str(candidate))


@pytest.fixture()
def check_redis_url():
    from shared_py.observability.health import check_redis_url as fn

    return fn


def test_check_redis_url_empty_url(check_redis_url) -> None:
    ok, detail = check_redis_url("   ", retries=2)
    assert ok is False
    assert "empty" in detail.lower()


def test_check_redis_url_retries_then_ok(check_redis_url) -> None:
    calls = {"n": 0}

    def fake_from_url(*_a, **_kw) -> MagicMock:
        m = MagicMock()
        idx = calls["n"]
        calls["n"] += 1
        if idx == 0:
            m.ping.side_effect = redis.TimeoutError("Timeout reading from socket")
        else:
            m.ping.return_value = True
        return m

    with patch("shared_py.observability.health.redis.Redis.from_url", side_effect=fake_from_url):
        ok, detail = check_redis_url("redis://127.0.0.1:6379/0", timeout_sec=1.0, retries=2)
    assert ok is True
    assert detail == "ok"
    assert calls["n"] == 2


def test_check_redis_url_no_retry_on_first_success(check_redis_url) -> None:
    calls = {"n": 0}

    def fake_from_url(*_a, **_kw) -> MagicMock:
        calls["n"] += 1
        m = MagicMock()
        m.ping.return_value = True
        return m

    with patch("shared_py.observability.health.redis.Redis.from_url", side_effect=fake_from_url):
        ok, detail = check_redis_url("redis://127.0.0.1:6379/0", retries=2)
    assert ok is True
    assert calls["n"] == 1


def test_check_redis_url_all_fail_returns_last_error(check_redis_url) -> None:
    def fake_from_url(*_a, **_kw) -> MagicMock:
        m = MagicMock()
        m.ping.side_effect = redis.TimeoutError("Timeout reading from socket")
        return m

    with patch("shared_py.observability.health.redis.Redis.from_url", side_effect=fake_from_url):
        ok, detail = check_redis_url("redis://127.0.0.1:6379/0", timeout_sec=0.1, retries=1)
    assert ok is False
    assert "Timeout" in detail
