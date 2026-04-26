"""
OpenAPI-Artefakt muss mit FastAPI-Export uebereinstimmen (kein stilles Drift).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from config.required_secrets import required_env_names_for_env_file_profile

REPO_ROOT = Path(__file__).resolve().parents[3]
OPENAPI_PATH = REPO_ROOT / "shared" / "contracts" / "openapi" / "api-gateway.openapi.json"


def _openapi_test_env_value(name: str) -> str:
    u = name.upper()
    if "DATABASE_URL" in u:
        return "postgresql://u:p@localhost:5432/db"
    if "REDIS_URL" in u:
        return "redis://localhost:6379/0"
    return "ci_repeatable_secret_min_32_chars_x"


@pytest.mark.skipif(
    not (REPO_ROOT / "services" / "api-gateway" / "src").is_dir(),
    reason="api-gateway src fehlt",
)
def test_committed_openapi_matches_fastapi_export(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in required_env_names_for_env_file_profile(profile="local"):
        monkeypatch.setenv(key, _openapi_test_env_value(key))
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
    monkeypatch.setenv("COMMERCIAL_ENABLED", "false")

    sys.path.insert(0, str(REPO_ROOT / "services" / "api-gateway" / "src"))
    sys.path.insert(0, str(REPO_ROOT / "shared" / "python" / "src"))

    for mod in list(sys.modules):
        if mod == "api_gateway" or mod.startswith("api_gateway."):
            del sys.modules[mod]
    for mod in list(sys.modules):
        if mod == "prometheus_client" or mod.startswith("prometheus_client."):
            del sys.modules[mod]


    import config.gateway_settings as gw_mod

    gw_mod.get_gateway_settings.cache_clear()
    for mod in list(sys.modules):
        if mod == "api_gateway" or mod.startswith("api_gateway."):
            del sys.modules[mod]

    from api_gateway.app import app  # noqa: PLC0415

    committed = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    exported = app.openapi()
    assert exported == committed
