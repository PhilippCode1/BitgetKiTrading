"""POST generate-and-store — LLM gemockt, DB-Insert gemockt."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import UUID

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


@contextmanager
def _fake_connect():
    yield MagicMock()


@patch("api_gateway.routes_ai_strategy_proposal_drafts.connect_drafts", _fake_connect)
@patch("api_gateway.routes_ai_strategy_proposal_drafts.insert_proposal_draft")
@patch("api_gateway.routes_ai_strategy_proposal_drafts.record_gateway_audit_line")
@patch("api_gateway.routes_ai_strategy_proposal_drafts.post_llm_orchestrator_json")
def test_generate_and_store_persists(
    mock_llm, _audit, mock_insert, client: TestClient
) -> None:
    did = UUID("12345678-1234-5678-1234-567812345678")
    mock_insert.return_value = did
    mock_llm.return_value = {
        "ok": True,
        "provider": "fake",
        "result": {
            "schema_version": "1.0",
            "execution_authority": "none",
            "strategy_explanation_de": "e",
            "scenario_variants_de": ["s"],
            "parameter_ideas_de": [],
            "validity_and_assumptions_de": "v",
            "risk_and_caveats_de": "r",
            "referenced_input_keys_de": [],
            "non_authoritative_note_de": "n",
            "promotion_disclaimer_de": "Kein Orderauftrag; nur Entwurf hier.",
            "suggested_execution_lane_hint": "none",
        },
    }
    r = client.post(
        "/v1/operator/ai-strategy-proposal-drafts/generate-and-store",
        json={
            "chart_context_json": {"signal_id": "abc"},
            "signal_id": "sig-1",
            "symbol": "BTCUSDT",
            "timeframe": "5m",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["draft_id"] == str(did)
    assert data["lifecycle_status"] == "draft"
    mock_llm.assert_called_once()
    mock_insert.assert_called_once()
