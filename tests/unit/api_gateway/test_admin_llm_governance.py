"""GET /v1/admin/llm-governance — Forward zum Orchestrator (gemockt)."""

from __future__ import annotations

from unittest.mock import patch

import jwt
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
    monkeypatch.setenv("API_GATEWAY_URL", "http://localhost:8000")
    monkeypatch.setenv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("NEXT_PUBLIC_WS_BASE_URL", "ws://localhost:8000")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("COMMERCIAL_ENABLED", "false")
    monkeypatch.setenv("ADMIN_TOKEN", "admin-token-123456789012")
    monkeypatch.setenv("SECRET_KEY", "secret-key-1234567890ab")
    monkeypatch.setenv("JWT_SECRET", "jwt-secret-1234567890ab")
    monkeypatch.setenv("ENCRYPTION_KEY", "encryption-key-12345678")
    monkeypatch.setenv("GATEWAY_JWT_SECRET", "unit-test-gateway-jwt-secret-32b!")
    monkeypatch.setenv("INTERNAL_API_KEY", "internal-service-key-12345")
    monkeypatch.setenv("DATABASE_URL_DOCKER", "postgresql://u:p@postgres:5432/db")
    monkeypatch.setenv("REDIS_URL_DOCKER", "redis://redis:6379/0")
    monkeypatch.setenv("POSTGRES_PASSWORD", "postgres-test-password-ok")
    monkeypatch.setenv("MODEL_OPS_ENABLED", "false")
    from config.gateway_settings import get_gateway_settings

    get_gateway_settings.cache_clear()
    from api_gateway.app import create_app

    app = create_app()
    with TestClient(app) as tc:
        yield tc
    get_gateway_settings.cache_clear()


def _admin_jwt() -> str:
    return jwt.encode(
        {
            "sub": "admin-tester",
            "role": "admin",
            "aud": "api-gateway",
            "iss": "bitget-btc-ai-gateway",
            "gateway_roles": ["admin:read"],
        },
        "unit-test-gateway-jwt-secret-32b!",
        algorithm="HS256",
    )


def _customer_jwt() -> str:
    return jwt.encode(
        {
            "sub": "cu-1",
            "role": "customer",
            "aud": "api-gateway",
            "iss": "bitget-btc-ai-gateway",
            "gateway_roles": ["billing:read", "admin:read"],
            "portal_roles": ["customer"],
        },
        "unit-test-gateway-jwt-secret-32b!",
        algorithm="HS256",
    )


@patch("api_gateway.routes_admin.record_gateway_audit_line")
@patch("api_gateway.routes_admin.get_llm_orchestrator_json")
def test_admin_llm_governance_ok(mock_get, _audit, client: TestClient) -> None:
    mock_get.return_value = {
        "ok": True,
        "prompt_manifest_version": "2026.04.03",
        "guardrails_version": "2026.04.03-1",
        "tasks": [],
    }
    r = client.get(
        "/v1/admin/llm-governance",
        headers={"Authorization": f"Bearer {_admin_jwt()}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "llm-orchestrator"
    assert body["summary"]["ok"] is True
    mock_get.assert_called_once()
    assert mock_get.call_args[0][1] == "/llm/governance/summary"


@patch("api_gateway.routes_admin.get_llm_orchestrator_json")
def test_admin_llm_governance_403_for_portal_customer_jwt(mock_get, client: TestClient) -> None:
    """Gueltiges Kunden-JWT: /v1/admin trotzdem 403 (RBAC, nicht nur Build-Flags)."""
    r = client.get(
        "/v1/admin/llm-governance",
        headers={"Authorization": f"Bearer {_customer_jwt()}"},
    )
    assert r.status_code == 403, r.text
    body = r.json()
    assert body["detail"]["code"] == "GATEWAY_FORBIDDEN_CUSTOMER_SESSION"
    mock_get.assert_not_called()
