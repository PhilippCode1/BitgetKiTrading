from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_BROKER_SRC = REPO_ROOT / "services" / "live-broker" / "src"

for candidate in (REPO_ROOT, LIVE_BROKER_SRC):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)


def _fill_local_matrix_gaps(monkeypatch: pytest.MonkeyPatch) -> None:
    from config import required_secrets as rs
    from config.required_secrets import required_env_names_for_env_file_profile

    def _val(name: str) -> str:
        u = name.upper()
        if "DATABASE_URL" in u:
            return "postgresql://test:test@127.0.0.1:5432/test"
        if "REDIS_URL" in u:
            return "redis://127.0.0.1:6379/0"
        return "ci_repeatable_secret_min_32_chars_x"

    for key in required_env_names_for_env_file_profile(profile="local"):
        if rs._bad_value(os.environ.get(key)):
            monkeypatch.setenv(key, _val(key))


@pytest.fixture
def ops_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    _fill_local_matrix_gaps(monkeypatch)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PRODUCTION", "false")
    monkeypatch.setenv("INTERNAL_API_KEY", "unit-test-internal-key-32chars!!")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@127.0.0.1:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("EXECUTION_MODE", "paper")
    monkeypatch.setenv("STRATEGY_EXEC_MODE", "manual")
    monkeypatch.setenv("LIVE_BROKER_ENABLED", "false")
    monkeypatch.setenv("LIVE_TRADE_ENABLE", "false")
    monkeypatch.setenv("SHADOW_TRADE_ENABLE", "false")
    monkeypatch.setenv("LIVE_REQUIRE_EXCHANGE_HEALTH", "false")
    monkeypatch.setenv("LIVE_BROKER_BASE_URL", "http://localhost:9080")
    monkeypatch.setenv("LIVE_BROKER_WS_PRIVATE_URL", "ws://localhost:9080/ws/private")
    monkeypatch.setenv("BITGET_SYMBOL", "BTCUSDT")

    from live_broker.app import create_app

    return TestClient(create_app(start_background=False))


def test_live_broker_ops_401_without_internal_header(ops_client: TestClient) -> None:
    r = ops_client.get("/live-broker/runtime")
    assert r.status_code == 401, r.text
    body = r.json()["detail"]
    assert body["code"] == "INTERNAL_AUTH_REQUIRED"


def test_live_broker_ops_200_with_internal_header(ops_client: TestClient) -> None:
    r = ops_client.get(
        "/live-broker/runtime",
        headers={"X-Internal-Service-Key": "unit-test-internal-key-32chars!!"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["service"] == "live-broker"
