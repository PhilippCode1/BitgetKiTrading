"""POST /v1/llm/operator/explain — Forward zum Orchestrator (gemockt)."""

from __future__ import annotations

from unittest.mock import patch

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


@patch("api_gateway.routes_llm_operator.record_gateway_audit_line")
@patch("api_gateway.routes_llm_operator.post_llm_orchestrator_json")
def test_operator_explain_returns_upstream_payload(mock_post, mock_audit, client: TestClient) -> None:
    mock_post.return_value = {
        "ok": True,
        "provider": "fake",
        "result": {
            "schema_version": "1.0",
            "execution_authority": "none",
            "explanation_de": "Test.",
            "referenced_artifacts_de": [],
            "non_authoritative_note_de": "Hinweis.",
        },
        "provenance": {"task_type": "operator_explain"},
    }
    r = client.post(
        "/v1/llm/operator/explain",
        json={
            "question_de": "Was ist ein Live-Gate?",
            "readonly_context_json": {"a": 1, "b": 2},
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data["provider"] == "fake"
    assert data["result"]["explanation_de"] == "Test."
    mock_post.assert_called_once()
    mock_audit.assert_called_once()
    pos, kw = mock_audit.call_args
    assert pos[2] == "llm_operator_explain"
    extra = kw["extra"]
    assert extra["question_len"] == len("Was ist ein Live-Gate?")
    assert extra["context_key_count"] == 2
    assert extra["context_top_keys"] == ["a", "b"]


@patch("api_gateway.routes_llm_operator.record_gateway_audit_line")
@patch("api_gateway.routes_llm_operator.post_llm_orchestrator_json")
def test_operator_explain_503_on_runtime_config_error(mock_post, _audit, client: TestClient) -> None:
    mock_post.side_effect = RuntimeError("INTERNAL_API_KEY fehlt fuer LLM-Orchestrator-Forward")
    r = client.post(
        "/v1/llm/operator/explain",
        json={"question_de": "Kurze Frage hier?", "readonly_context_json": {}},
    )
    assert r.status_code == 503
    body = r.json()
    assert body["detail"]["code"] == "LLM_ORCH_UNAVAILABLE"


def test_operator_explain_422_short_question(client: TestClient) -> None:
    r = client.post(
        "/v1/llm/operator/explain",
        json={"question_de": "ab", "readonly_context_json": {}},
    )
    assert r.status_code == 422


@patch("api_gateway.routes_llm_operator.record_gateway_audit_line")
@patch("api_gateway.routes_llm_operator.post_llm_orchestrator_json")
def test_strategy_signal_explain_returns_upstream_payload(mock_post, _audit, client: TestClient) -> None:
    mock_post.return_value = {
        "ok": True,
        "provider": "fake",
        "result": {
            "schema_version": "1.0",
            "execution_authority": "none",
            "strategy_explanation_de": "Kurz erklaert.",
            "risk_and_caveats_de": "Risiko.",
            "referenced_input_keys_de": ["signal_id"],
            "non_authoritative_note_de": "Hinweis.",
        },
        "provenance": {"task_type": "strategy_signal_explain"},
    }
    r = client.post(
        "/v1/llm/operator/strategy-signal-explain",
        json={"signal_context_json": {"signal_id": "x"}, "focus_question_de": None},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data["result"]["strategy_explanation_de"] == "Kurz erklaert."
    mock_post.assert_called_once()
    call_kw = mock_post.call_args
    assert call_kw[0][1] == "/llm/analyst/strategy_signal_explain"


def test_strategy_signal_explain_422_empty_snapshot_and_short_focus(client: TestClient) -> None:
    r = client.post(
        "/v1/llm/operator/strategy-signal-explain",
        json={"signal_context_json": {}, "focus_question_de": "ab"},
    )
    assert r.status_code == 422
