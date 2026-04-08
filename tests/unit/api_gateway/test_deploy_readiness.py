from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("PRODUCTION", "false")
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("EXECUTION_MODE", "paper")
    monkeypatch.setenv("SHADOW_TRADE_ENABLE", "false")
    monkeypatch.setenv("LIVE_TRADE_ENABLE", "false")
    monkeypatch.setenv("LIVE_BROKER_ENABLED", "false")
    monkeypatch.setenv("STRATEGY_EXEC_MODE", "manual")
    monkeypatch.setenv("RISK_HARD_GATING_ENABLED", "true")
    monkeypatch.setenv("RISK_REQUIRE_7X_APPROVAL", "true")
    monkeypatch.setenv("RISK_ALLOWED_LEVERAGE_MIN", "7")
    monkeypatch.setenv("RISK_ALLOWED_LEVERAGE_MAX", "75")
    monkeypatch.setenv("LIVE_KILL_SWITCH_ENABLED", "true")
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("APP_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    from config.gateway_settings import get_gateway_settings

    get_gateway_settings.cache_clear()
    from api_gateway.app import create_app

    app = create_app()
    with TestClient(app) as tc:
        yield tc
    get_gateway_settings.cache_clear()


def test_edge_readiness_public(client: TestClient) -> None:
    r = client.get(
        "/v1/deploy/edge-readiness",
        headers={"X-Forwarded-Proto": "https"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["public_endpoints"]["health"] == "/health"
    assert data["request_forwarding"]["x_forwarded_proto"] == "https"
    assert "security_headers" in data
