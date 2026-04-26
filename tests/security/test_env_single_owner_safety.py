from __future__ import annotations

from tools.check_env_single_owner_safety import STATUS_ERROR, validate_env


def _base_prod_env() -> dict[str, str]:
    return {
        "PRODUCTION": "true",
        "APP_ENV": "production",
        "DEBUG": "false",
        "EXECUTION_MODE": "shadow",
        "LIVE_TRADE_ENABLE": "false",
        "LIVE_BROKER_ENABLED": "true",
        "LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN": "true",
        "REQUIRE_SHADOW_MATCH_BEFORE_LIVE": "true",
        "LIVE_REQUIRE_EXCHANGE_HEALTH": "true",
        "LIVE_REQUIRE_ASSET_ELIGIBILITY": "true",
        "RISK_HARD_GATING_ENABLED": "true",
        "LIVE_KILL_SWITCH_ENABLED": "true",
        "GATEWAY_MANUAL_ACTION_REQUIRED": "true",
        "LLM_USE_FAKE_PROVIDER": "false",
        "NEWS_FIXTURE_MODE": "false",
        "BITGET_DEMO_ENABLED": "false",
        "BITGET_RELAX_CREDENTIAL_ISOLATION": "false",
        "POSTGRES_PASSWORD": "runtime-postgres-password",
        "DATABASE_URL": "postgresql://app:runtime-postgres-password@db.prod.internal:5432/app",
        "REDIS_URL": "redis://redis.prod.internal:6379/0",
        "JWT_SECRET": "runtime-jwt-secret-value",
        "SECRET_KEY": "runtime-secret-key-value",
        "ADMIN_TOKEN": "runtime-admin-token-value",
        "ENCRYPTION_KEY": "runtime-encryption-key-value",
        "INTERNAL_API_KEY": "runtime-internal-api-key",
        "GATEWAY_JWT_SECRET": "runtime-gateway-jwt-secret",
    }


def _codes(env: dict[str, str], *, profile: str = "production") -> set[str]:
    return {
        issue.code
        for issue in validate_env(env, profile=profile, strict_runtime=True)
        if issue.severity == STATUS_ERROR
    }


def test_production_debug_true_fails() -> None:
    env = _base_prod_env()
    env["DEBUG"] = "true"
    assert "production_forbidden_true" in _codes(env)


def test_production_fake_provider_fails() -> None:
    env = _base_prod_env()
    env["LLM_USE_FAKE_PROVIDER"] = "true"
    assert "production_forbidden_true" in _codes(env)


def test_production_bitget_demo_fails() -> None:
    env = _base_prod_env()
    env["BITGET_DEMO_ENABLED"] = "true"
    assert "production_forbidden_true" in _codes(env)


def test_live_trade_without_live_execution_mode_fails() -> None:
    env = _base_prod_env()
    env["LIVE_TRADE_ENABLE"] = "true"
    assert "live_trade_requires_live_execution_mode" in _codes(env)


def test_live_trade_without_asset_gates_fails() -> None:
    env = _base_prod_env()
    env.update({"EXECUTION_MODE": "live", "LIVE_TRADE_ENABLE": "true"})
    env.pop("LIVE_REQUIRE_ASSET_ELIGIBILITY")
    assert "live_trade_requires_asset_eligibility" in _codes(env)


def test_shadow_live_trade_fails() -> None:
    env = _base_prod_env()
    env["APP_ENV"] = "shadow"
    env["EXECUTION_MODE"] = "shadow"
    env["LIVE_TRADE_ENABLE"] = "true"
    assert "shadow_live_trade_enabled" in _codes(env, profile="shadow")


def test_next_public_openai_key_fails() -> None:
    env = _base_prod_env()
    env["NEXT_PUBLIC_OPENAI_API_KEY"] = "redacted"
    assert "browser_secret_key_name" in _codes(env)


def test_next_public_bitget_secret_fails() -> None:
    env = _base_prod_env()
    env["NEXT_PUBLIC_BITGET_API_SECRET"] = "redacted"
    assert "browser_secret_key_name" in _codes(env)


def test_runtime_placeholder_secret_fails() -> None:
    env = _base_prod_env()
    env["INTERNAL_API_KEY"] = "<SET_ME>"
    assert "placeholder_runtime_secret" in _codes(env)


def test_demo_live_key_mix_fails() -> None:
    env = _base_prod_env()
    env["BITGET_API_KEY"] = "live-key-reference"
    env["BITGET_DEMO_API_KEY"] = "demo-key-reference"
    assert "bitget_demo_live_key_mix" in _codes(env)
