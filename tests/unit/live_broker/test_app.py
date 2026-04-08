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
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    _fill_local_matrix_gaps(monkeypatch)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PRODUCTION", "false")
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


def test_live_broker_health_route_exposes_runtime_contract(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["service"] == "live-broker"
    assert payload["execution_mode"] == "paper"
    assert payload["runtime_mode"] == "paper"
    assert payload["strategy_execution_mode"] == "manual"
    assert "interfaces" in payload
    assert payload["interfaces"]["signal_engine_stream"] == "events:signal_created"
    assert "/live-broker/orders/create" in payload["interfaces"]["live_broker_order_routes"]
    assert "/live-broker/kill-switch/arm" in payload["interfaces"]["live_broker_order_routes"]


def test_live_broker_ready_route_reports_core_checks(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["service"] == "live-broker"
    assert "postgres" in payload["checks"]
    assert "redis" in payload["checks"]
    assert "persistence_schema" in payload["checks"]
