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


def _clear_gateway_settings_cache() -> None:
    from config.gateway_settings import get_gateway_settings

    get_gateway_settings.cache_clear()


def test_gateway_health_is_liveness_only() -> None:
    with (
        patch.dict(os.environ, _MIN_GATEWAY_ENV, clear=False),
        patch("config.bootstrap.validate_required_secrets", lambda *_a, **_kw: None),
    ):
        _clear_gateway_settings_cache()
        import api_gateway.app as app_module

        importlib.reload(app_module)
        c = TestClient(app_module.app)
        r = c.get("/health")
    assert r.status_code == 200
    b = r.json()
    assert b["status"] == "ok"
    assert b["role"] == "liveness"
    assert b["service"] == "api-gateway"


def test_gateway_ready_always_includes_checks_and_summary() -> None:
    with (
        patch.dict(os.environ, _MIN_GATEWAY_ENV, clear=False),
        patch("config.bootstrap.validate_required_secrets", lambda *_a, **_kw: None),
    ):
        _clear_gateway_settings_cache()
        import api_gateway.app as app_module

        importlib.reload(app_module)
        with (
            patch(
                "api_gateway.gateway_readiness_core.check_postgres",
                return_value=(True, "ok"),
            ),
            patch(
                "api_gateway.gateway_readiness_core.check_postgres_schema_for_ready",
                return_value=(True, "ok"),
            ),
            patch(
                "api_gateway.gateway_readiness_core.check_redis_url",
                return_value=(True, "ok"),
            ),
            patch.object(
                app_module,
                "append_peer_readiness_checks",
                side_effect=lambda parts, *_a, **_k: parts,
            ),
        ):
            c = TestClient(app_module.app)
            r = c.get("/ready")
    assert r.status_code == 200
    j = r.json()
    assert j["ready"] is True
    assert j["role"] == "readiness"
    assert "checks" in j
    assert "postgres" in j["checks"]
    assert j["checks"]["postgres"]["ok"] is True
    assert "summary" in j
    assert j["summary"]["core_postgres_connect"] is True
    assert j["summary"]["core_postgres_schema"] is True
    assert j["summary"]["core_redis"] is True
    assert j.get("readiness_contract_version") == 1


def test_gateway_ready_false_when_dsns_missing() -> None:
    with (
        patch.dict(os.environ, _MIN_GATEWAY_ENV, clear=False),
        patch("config.bootstrap.validate_required_secrets", lambda *_a, **_kw: None),
    ):
        _clear_gateway_settings_cache()
        import api_gateway.app as app_module

        importlib.reload(app_module)
        with (
            patch("api_gateway.gateway_readiness_core.effective_database_dsn", return_value=""),
            patch("api_gateway.gateway_readiness_core.effective_redis_url", return_value=""),
            patch.object(
                app_module,
                "append_peer_readiness_checks",
                side_effect=lambda parts, *_a, **_k: parts,
            ),
        ):
            c = TestClient(app_module.app)
            r = c.get("/ready")
    assert r.status_code == 200
    j = r.json()
    assert j["ready"] is False
    assert j["checks"]["postgres"]["ok"] is False
    assert j["checks"]["postgres_schema"]["ok"] is False
