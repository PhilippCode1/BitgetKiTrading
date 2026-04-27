"""POST /v1/llm/assist/*/turn — Segment-Routing und Forward (gemockt)."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# require_admin_read: lokal / nicht-production mit GATEWAY_ENFORCE_SENSITIVE_AUTH=false: Legacy-Admin-Token
_ASSIST_ADMIN_HEADERS = {"X-Admin-Token": "admin-token-123456789012"}


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
    monkeypatch.setenv("GATEWAY_ALLOW_LEGACY_ADMIN_TOKEN", "true")
    monkeypatch.setenv("GATEWAY_ENFORCE_SENSITIVE_AUTH", "false")
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


def _turn_body(**kwargs: object) -> dict:
    base = {
        "conversation_id": str(uuid.uuid4()),
        "user_message_de": "Kurze Testfrage hier?",
        "context_json": {},
    }
    base.update(kwargs)
    return base


@patch("api_gateway.routes_llm_assist.record_gateway_audit_line")
@patch("api_gateway.routes_llm_assist.post_llm_orchestrator_json")
def test_assist_admin_operations_turn(mock_post, _audit, client: TestClient) -> None:
    mock_post.return_value = {
        "ok": True,
        "provider": "fake",
        "result": {"assistant_reply_de": "Antwort.", "assist_role_echo": "admin_operations"},
        "assist_session": {"assist_role": "admin_operations", "history_message_count": 2},
    }
    r = client.post(
        "/v1/llm/assist/admin-operations/turn",
        json=_turn_body(
            context_json={"platform_health": {"ok": True}, "evil": 1},
        ),
        headers=_ASSIST_ADMIN_HEADERS,
    )
    assert r.status_code == 200, r.text
    mock_post.assert_called_once()
    payload = mock_post.call_args[0][2]
    assert payload["assist_role"] == "admin_operations"
    assert "platform_health" in payload["context_json"]
    assert "evil" not in payload["context_json"]


@patch("api_gateway.routes_llm_assist.record_gateway_audit_line")
@patch("api_gateway.routes_llm_assist.post_llm_orchestrator_json")
def test_assist_customer_onboarding_turn(mock_post, _audit, client: TestClient) -> None:
    mock_post.return_value = {
        "ok": True,
        "provider": "fake",
        "result": {
            "assistant_reply_de": "Willkommen.",
            "assist_role_echo": "customer_onboarding",
        },
    }
    r = client.post(
        "/v1/llm/assist/customer-onboarding/turn",
        json=_turn_body(context_json={"tenant_profile": {"id": "t1"}}),
    )
    assert r.status_code == 200, r.text
    assert mock_post.call_args[0][2]["assist_role"] == "customer_onboarding"


def test_assist_turn_rejects_invalid_conversation_uuid(client: TestClient) -> None:
    r = client.post(
        "/v1/llm/assist/admin-operations/turn",
        json={
            "conversation_id": "not-a-uuid",
            "user_message_de": "Zu kurz?",  # noqa: wrong len — pydantic may catch uuid first
        },
        headers=_ASSIST_ADMIN_HEADERS,
    )
    assert r.status_code == 422


def test_assist_unknown_segment_returns_404(client: TestClient) -> None:
    r = client.post(
        "/v1/llm/assist/unknown-segment/turn",
        json=_turn_body(),
    )
    assert r.status_code == 404
