from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
API_GATEWAY_SRC = REPO_ROOT / "services" / "api-gateway" / "src"
for candidate in (REPO_ROOT, API_GATEWAY_SRC):
    cs = str(candidate)
    if cs not in sys.path:
        sys.path.insert(0, cs)

pytest.importorskip("fastapi")

_MIN_GATEWAY_ENV: dict[str, str] = {
    "PRODUCTION": "false",
    "ADMIN_TOKEN": "unit_admin_token_for_tests_only________",
    "API_GATEWAY_URL": "http://127.0.0.1:8000",
    "DATABASE_URL": "postgresql://u:p@127.0.0.1:5432/db",
    "DATABASE_URL_DOCKER": "postgresql://u:p@postgres:5432/db",
    "ENCRYPTION_KEY": "unit_encryption_key_32_chars_min______",
    "GATEWAY_JWT_SECRET": "unit-test-gateway-jwt-secret-32b!",
    "INTERNAL_API_KEY": "unit_internal_api_key_min_32_chars_x",
    "JWT_SECRET": "unit_jwt_secret_minimum_32_characters_",
    "NEXT_PUBLIC_API_BASE_URL": "http://127.0.0.1:8000",
    "NEXT_PUBLIC_WS_BASE_URL": "ws://127.0.0.1:8000",
    "POSTGRES_PASSWORD": "unit_postgres_pw",
    "REDIS_URL": "redis://127.0.0.1:6379/0",
    "REDIS_URL_DOCKER": "redis://redis:6379/0",
    "SECRET_KEY": "unit_secret_key_minimum_32_characters",
}

_POLICY_ENV: dict[str, str] = {
    "APP_ENV": "local",
    "EXECUTION_MODE": "paper",
    "SHADOW_TRADE_ENABLE": "false",
    "LIVE_TRADE_ENABLE": "false",
    "LIVE_BROKER_ENABLED": "false",
    "STRATEGY_EXEC_MODE": "manual",
    "RISK_HARD_GATING_ENABLED": "true",
    "RISK_REQUIRE_7X_APPROVAL": "true",
    "RISK_ALLOWED_LEVERAGE_MIN": "7",
    "RISK_ALLOWED_LEVERAGE_MAX": "75",
    "LIVE_KILL_SWITCH_ENABLED": "true",
    "CORS_ALLOW_ORIGINS": "http://localhost:3000",
    "APP_BASE_URL": "http://localhost:8000",
    "FRONTEND_URL": "http://localhost:3000",
    "COMMERCIAL_ENABLED": "false",
}


def _clear_gateway_settings_cache() -> None:
    from config.gateway_settings import get_gateway_settings

    get_gateway_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    merged = {**_MIN_GATEWAY_ENV, **_POLICY_ENV}
    with (
        patch.dict(os.environ, merged, clear=False),
        patch("config.bootstrap.validate_required_secrets", lambda *_a, **_kw: None),
    ):
        _clear_gateway_settings_cache()
        import api_gateway.app as app_module

        importlib.reload(app_module)
        with TestClient(app_module.create_app()) as tc:
            yield tc
        _clear_gateway_settings_cache()


def test_meta_surface_public(client: TestClient) -> None:
    r = client.get("/v1/meta/surface")
    assert r.status_code == 200
    data = r.json()
    assert data["schema_version"] == "public-surface-v1"
    assert "execution" in data
    assert "commerce" in data
    assert data["endpoints"]["public_surface"] == "/v1/meta/surface"
    assert "sensitive_auth_enforced" in data["auth"]
    lt = data.get("live_terminal")
    assert isinstance(lt, dict)
    assert "sse_enabled" in lt
    assert "sse_ping_sec" in lt
    assert isinstance(lt["sse_enabled"], bool)
    assert isinstance(lt["sse_ping_sec"], int)
