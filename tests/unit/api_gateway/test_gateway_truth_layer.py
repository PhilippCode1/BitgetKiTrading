from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
API_GATEWAY_SRC = REPO_ROOT / "services" / "api-gateway" / "src"
for candidate in (REPO_ROOT, API_GATEWAY_SRC):
    cs = str(candidate)
    if cs not in sys.path:
        sys.path.insert(0, cs)

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


pytest.importorskip("fastapi")

from api_gateway.gateway_readiness_core import (
    gateway_readiness_core_parts_raw,
    gateway_readiness_core_snapshot,
)
from api_gateway.routes_system_health import _normalize_probe_payload
from api_gateway.system_health_truth_layer import compute_aggregate_status
from shared_py.observability import merge_ready_details


def test_normalize_probe_accepts_dict_style_checks() -> None:
    """Worker-/Gateway-/ready mit checks als { name: { ok, detail } } wie API-Gateway."""
    out = _normalize_probe_payload(
        {
            "ready": False,
            "checks": {"redis": {"ok": False, "detail": "timeout"}},
        }
    )
    assert out.get("ready") is False
    assert out.get("status") == "error"
    assert any("redis:timeout" in x for x in (out.get("failed_checks") or []))


def test_core_snapshot_matches_merge_ready_details() -> None:
    """Kern-Checks in System-Health = merge_ready_details(Kern) wie bei /ready ohne Peers."""
    with (
        patch.dict(os.environ, _MIN_GATEWAY_ENV, clear=False),
        patch("config.bootstrap.validate_required_secrets", lambda *_a, **_kw: None),
        patch(
            "api_gateway.gateway_readiness_core.check_postgres",
            return_value=(True, "ok"),
        ),
        patch(
            "api_gateway.gateway_readiness_core.check_postgres_schema_for_ready",
            return_value=(True, "ok"),
        ),
        patch(
            "api_gateway.gateway_readiness_core.check_redis_url_readiness",
            return_value=(True, "ok"),
        ),
    ):
        _clear_gateway_settings_cache()
        parts = gateway_readiness_core_parts_raw()
        ok, checks = merge_ready_details(parts)
        snap = gateway_readiness_core_snapshot()
        assert snap["core_ok"] is ok
        assert snap["checks"] == checks


def test_aggregate_red_when_core_not_ok() -> None:
    a = compute_aggregate_status(
        readiness_core_ok=False,
        warnings=[],
        services=[{"name": "x", "configured": True, "status": "ok"}],
    )
    assert a["level"] == "red"
    assert "readiness_core_failed" in a["primary_reason_codes"]


def test_aggregate_green_when_core_ok_no_warnings() -> None:
    a = compute_aggregate_status(
        readiness_core_ok=True,
        warnings=[],
        services=[
            {"name": "api-gateway", "configured": True, "status": "ok"},
            {"name": "signal-engine", "configured": False, "status": "not_configured"},
        ],
    )
    assert a["level"] == "green"
    assert a["primary_reason_codes"] == []


def test_aggregate_degraded_on_warnings() -> None:
    a = compute_aggregate_status(
        readiness_core_ok=True,
        warnings=["stale_signals"],
        services=[{"name": "api-gateway", "configured": True, "status": "ok"}],
    )
    assert a["level"] == "degraded"
    assert "stale_signals" in a["primary_reason_codes"]


def test_aggregate_degraded_on_service_probe_error() -> None:
    a = compute_aggregate_status(
        readiness_core_ok=True,
        warnings=[],
        services=[{"name": "signal-engine", "configured": True, "status": "error"}],
    )
    assert a["level"] == "degraded"
    assert any(c.startswith("services_probe:") for c in a["primary_reason_codes"])
