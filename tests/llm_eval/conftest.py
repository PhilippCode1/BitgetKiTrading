"""Eval-Regression: LLM-Orchestrator-Testclient (Fixtures lokal, kein pytest_plugins — pytest 8+)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
LLM_SRC = REPO / "services" / "llm-orchestrator" / "src"
SHARED_SRC = REPO / "shared" / "python" / "src"
for p in (LLM_SRC, SHARED_SRC):
    s = str(p)
    if p.is_dir() and s not in sys.path:
        sys.path.insert(0, s)


def _bad_value(val: str | None) -> bool:
    if val is None:
        return True
    t = val.strip()
    if not t:
        return True
    u = t.upper()
    if "<SET_ME>" in u or u == "SET_ME" or u == "CHANGE_ME":
        return True
    return False


@pytest.fixture(autouse=True)
def _llm_eval_required_secrets_matrix(monkeypatch: pytest.MonkeyPatch) -> None:
    defaults: dict[str, str] = {
        "POSTGRES_PASSWORD": "test-postgres-password",
        "DATABASE_URL": "postgresql://test:test@127.0.0.1:5432/test",
        "DATABASE_URL_DOCKER": "postgresql://test:test@postgres:5432/test",
        "API_GATEWAY_URL": "http://127.0.0.1:8000",
        "NEXT_PUBLIC_API_BASE_URL": "http://127.0.0.1:8000",
        "NEXT_PUBLIC_WS_BASE_URL": "ws://127.0.0.1:8000",
        "REDIS_URL": "redis://127.0.0.1:6379/0",
        "REDIS_URL_DOCKER": "redis://redis:6379/0",
        "JWT_SECRET": "test-jwt-secret-key-for-ci-only-32b!",
        "SECRET_KEY": "test-secret-key-for-ci-only-32bytes!!",
        "ADMIN_TOKEN": "test-admin-token-ci",
        "ENCRYPTION_KEY": "encryption-key-12345678",
        "INTERNAL_API_KEY": "test-internal-api-key-ci",
    }
    for key, val in defaults.items():
        if _bad_value(os.environ.get(key)):
            monkeypatch.setenv(key, val)


@pytest.fixture
def mock_redis_bus(monkeypatch: pytest.MonkeyPatch):
    """In-Memory Redis-API + Eventbus-Stubs."""
    store: dict[str, str] = {}

    def from_url(*_a: object, **_k: object) -> MagicMock:
        m = MagicMock()

        def _get(key: str) -> str | None:
            return store.get(key)

        def _setex(key: str, _ttl: int, val: str) -> bool:
            store[key] = val
            return True

        m.get.side_effect = _get
        m.setex.side_effect = _setex
        m.ping.return_value = True
        return m

    bus = MagicMock()
    bus.publish.return_value = "1-0"
    bus.ping.return_value = True

    with (
        patch("llm_orchestrator.service.Redis.from_url", side_effect=from_url),
        patch("llm_orchestrator.service.RedisStreamBus.from_url", return_value=bus),
    ):
        yield {"store": store, "bus": bus}


@pytest.fixture
def client(mock_redis_bus, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("LLM_USE_FAKE_PROVIDER", "true")
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")
    monkeypatch.setenv("API_GATEWAY_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("NEXT_PUBLIC_API_BASE_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("NEXT_PUBLIC_WS_BASE_URL", "ws://127.0.0.1:8000")
    from llm_orchestrator.app import create_app

    ikey = os.environ.get("INTERNAL_API_KEY", "").strip()
    hdrs = {"X-Internal-Service-Key": ikey} if ikey else {}
    return TestClient(create_app(), headers=hdrs)
