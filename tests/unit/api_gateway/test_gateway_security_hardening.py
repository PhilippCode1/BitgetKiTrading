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
    s = str(candidate)
    if s not in sys.path:
        sys.path.insert(0, s)


def _clear_gateway_settings_cache() -> None:
    from config.gateway_settings import get_gateway_settings

    get_gateway_settings.cache_clear()


def _gateway_app_reload_env(**overrides: str) -> dict[str, str]:
    """Vollstaendige local-Pflicht-ENV fuer importlib.reload(api_gateway.app) (wie OpenAPI-Export-Test)."""
    from config.required_secrets import required_env_names_for_env_file_profile

    def _val(name: str) -> str:
        u = name.upper()
        if "DATABASE_URL" in u:
            return "postgresql://u:p@localhost:5432/db"
        if "REDIS_URL" in u:
            return "redis://localhost:6379/0"
        return "ci_repeatable_secret_min_32_chars_x"

    env = {k: _val(k) for k in required_env_names_for_env_file_profile(profile="local")}
    env.setdefault("PRODUCTION", "false")
    env.setdefault("APP_ENV", "local")
    env.setdefault("EXECUTION_MODE", "paper")
    env.setdefault("BITGET_DEMO_ENABLED", "false")
    env.setdefault("SHADOW_TRADE_ENABLE", "false")
    env.setdefault("LIVE_TRADE_ENABLE", "false")
    env.setdefault("LIVE_BROKER_ENABLED", "false")
    env.setdefault("STRATEGY_EXEC_MODE", "manual")
    env.setdefault("RISK_HARD_GATING_ENABLED", "true")
    env.setdefault("RISK_REQUIRE_7X_APPROVAL", "true")
    env.setdefault("RISK_ALLOWED_LEVERAGE_MIN", "7")
    env.setdefault("RISK_ALLOWED_LEVERAGE_MAX", "75")
    env.setdefault("LIVE_KILL_SWITCH_ENABLED", "true")
    env.setdefault("CORS_ALLOW_ORIGINS", "http://localhost:3000")
    env.setdefault("APP_BASE_URL", "http://localhost:8000")
    env.setdefault("FRONTEND_URL", "http://localhost:3000")
    env.setdefault("COMMERCIAL_ENABLED", "false")
    env.update(overrides)
    return env


def test_allow_anonymous_safety_mutations_off_under_sensitive_auth() -> None:
    """Shadow-Profile: kein anonymes Umgehen trotz PRODUCTION=false."""
    with patch.dict(
        os.environ,
        {
            "GATEWAY_ENFORCE_SENSITIVE_AUTH": "true",
            "GATEWAY_JWT_SECRET": "unit-test-gateway-jwt-secret-32b!",
            "GATEWAY_ALLOW_ANONYMOUS_SAFETY_MUTATIONS": "true",
            "PRODUCTION": "false",
            "DATABASE_URL": "postgresql://u:p@localhost:5432/db",
            "REDIS_URL": "redis://localhost:6379/0",
        },
        clear=False,
    ):
        _clear_gateway_settings_cache()
        from config.gateway_settings import GatewaySettings

        gs = GatewaySettings()
        assert gs.sensitive_auth_enforced()
        assert not gs.allow_anonymous_safety_mutations_effective()


def test_live_broker_safety_post_unauthorized_without_credentials() -> None:
    import api_gateway.rate_limit as rl

    rl._rl_redis = None
    with patch.dict(
        os.environ,
        _gateway_app_reload_env(
            GATEWAY_ENFORCE_SENSITIVE_AUTH="true",
            GATEWAY_JWT_SECRET="unit-test-gateway-jwt-secret-32b!",
            GATEWAY_ALLOW_ANONYMOUS_SAFETY_MUTATIONS="false",
            GATEWAY_MANUAL_ACTION_REQUIRED="false",
        ),
        clear=False,
    ):
        _clear_gateway_settings_cache()
        import api_gateway.app as app_module

        importlib.reload(app_module)
        client = TestClient(app_module.create_app())
        r = client.post("/v1/live-broker/safety/orders/cancel-all", json={})
        assert r.status_code == 401
    _clear_gateway_settings_cache()


def test_commerce_internal_usage_rejects_wrong_meter_secret() -> None:
    import api_gateway.rate_limit as rl

    rl._rl_redis = None
    with patch.dict(
        os.environ,
        _gateway_app_reload_env(
            GATEWAY_ENFORCE_SENSITIVE_AUTH="true",
            GATEWAY_JWT_SECRET="unit-test-gateway-jwt-secret-32b!",
            COMMERCIAL_ENABLED="true",
            COMMERCIAL_METER_SECRET="commercial-meter-secret-32chars-min!",
        ),
        clear=False,
    ):
        _clear_gateway_settings_cache()
        import api_gateway.app as app_module

        importlib.reload(app_module)
        client = TestClient(app_module.create_app())
        r = client.post(
            "/v1/commerce/internal/usage",
            json={
                "tenant_id": "default",
                "event_type": "llm_tokens",
                "quantity": 1.0,
                "unit": "tokens",
            },
            headers={"X-Commercial-Meter-Secret": "wrong"},
        )
        assert r.status_code == 401
    _clear_gateway_settings_cache()


@pytest.mark.security
def test_live_sse_stream_rejects_unauthenticated_when_sensitive_enforced() -> None:
    """SSE-Endpunkt: keine anonyme Session bei erzwungenem Sensitive-Auth."""
    import api_gateway.rate_limit as rl

    rl._rl_redis = None
    with patch.dict(
        os.environ,
        _gateway_app_reload_env(
            GATEWAY_ENFORCE_SENSITIVE_AUTH="true",
            GATEWAY_JWT_SECRET="unit-test-gateway-jwt-secret-32b!",
            LIVE_SSE_ENABLED="true",
            GATEWAY_SSE_SIGNING_SECRET="",
            DASHBOARD_DEFAULT_SYMBOL="BTCUSDT",
        ),
        clear=False,
    ):
        _clear_gateway_settings_cache()
        import api_gateway.app as app_module

        importlib.reload(app_module)
        client = TestClient(app_module.create_app())
        r = client.get("/v1/live/stream")
        assert r.status_code == 401
        body = r.json()
        assert body.get("detail", {}).get("code") == "LIVE_STREAM_AUTH_REQUIRED"
    _clear_gateway_settings_cache()
