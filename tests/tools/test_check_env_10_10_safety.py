from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tools.check_env_10_10_safety import (
    STATUS_ERROR,
    STATUS_WARNING,
    load_dotenv,
    validate_env,
)


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "check_env_10_10_safety.py"


def _base_prod_env() -> dict[str, str]:
    env = {
        "PRODUCTION": "true",
        "APP_ENV": "production",
        "DEBUG": "false",
        "EXECUTION_MODE": "shadow",
        "LIVE_TRADE_ENABLE": "false",
        "LIVE_BROKER_ENABLED": "true",
        "LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN": "true",
        "REQUIRE_SHADOW_MATCH_BEFORE_LIVE": "true",
        "LIVE_REQUIRE_EXCHANGE_HEALTH": "true",
        "RISK_HARD_GATING_ENABLED": "true",
        "LIVE_KILL_SWITCH_ENABLED": "true",
        "LLM_USE_FAKE_PROVIDER": "false",
        "NEWS_FIXTURE_MODE": "false",
        "BITGET_DEMO_ENABLED": "false",
        "POSTGRES_PASSWORD": "runtime-postgres-password",
        "DATABASE_URL": "postgresql://app:runtime-postgres-password@db.prod.internal:5432/app",
        "DATABASE_URL_DOCKER": "postgresql://app:runtime-postgres-password@db.prod.internal:5432/app",
        "REDIS_URL": "redis://:runtime-redis-password@redis.prod.internal:6379/0",
        "REDIS_URL_DOCKER": "redis://:runtime-redis-password@redis.prod.internal:6379/0",
        "JWT_SECRET": "runtime-jwt-secret-value",
        "SECRET_KEY": "runtime-secret-key-value",
        "ADMIN_TOKEN": "runtime-admin-token-value",
        "ENCRYPTION_KEY": "runtime-encryption-key-value",
        "INTERNAL_API_KEY": "runtime-internal-api-key",
        "GATEWAY_JWT_SECRET": "runtime-gateway-jwt-secret",
        "API_GATEWAY_URL": "https://gateway.prod.internal",
        "NEXT_PUBLIC_API_BASE_URL": "https://gateway.example.com",
        "NEXT_PUBLIC_WS_BASE_URL": "wss://gateway.example.com",
        "DASHBOARD_GATEWAY_AUTHORIZATION": "Bearer runtime-dashboard-jwt",
        "APEX_AUDIT_LEDGER_ED25519_SEED_HEX": "runtime-audit-seed-hex",
    }
    return env


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


def test_production_fake_llm_fails() -> None:
    env = _base_prod_env()
    env["LLM_USE_FAKE_PROVIDER"] = "true"
    assert "production_forbidden_true" in _codes(env)


def test_production_bitget_demo_fails() -> None:
    env = _base_prod_env()
    env["BITGET_DEMO_ENABLED"] = "true"
    assert "production_forbidden_true" in _codes(env)


def test_live_trade_without_operator_release_fails() -> None:
    env = _base_prod_env()
    env.update(
        {
            "EXECUTION_MODE": "live",
            "LIVE_TRADE_ENABLE": "true",
            "LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN": "false",
            "COMMERCIAL_ENABLED": "true",
            "COMMERCIAL_ENTITLEMENT_ENFORCE": "true",
            "COMMERCIAL_REQUIRE_CONTRACT_FOR_LIVE": "true",
            "LIVE_SAFETY_LATCH_ON_DUPLICATE_RECOVERY_FAIL": "true",
        }
    )
    assert "live_trade_requires_operator_release" in _codes(env)


def test_live_trade_without_shadow_match_fails() -> None:
    env = _base_prod_env()
    env.update(
        {
            "EXECUTION_MODE": "live",
            "LIVE_TRADE_ENABLE": "true",
            "REQUIRE_SHADOW_MATCH_BEFORE_LIVE": "false",
            "COMMERCIAL_ENABLED": "true",
            "COMMERCIAL_ENTITLEMENT_ENFORCE": "true",
            "COMMERCIAL_REQUIRE_CONTRACT_FOR_LIVE": "true",
            "LIVE_SAFETY_LATCH_ON_DUPLICATE_RECOVERY_FAIL": "true",
        }
    )
    assert "live_trade_requires_shadow_match" in _codes(env)


def test_shadow_with_live_trade_fails() -> None:
    env = _base_prod_env()
    env["APP_ENV"] = "shadow"
    env["EXECUTION_MODE"] = "shadow"
    env["LIVE_TRADE_ENABLE"] = "true"
    assert "shadow_live_trade_enabled" in _codes(env, profile="shadow")


def test_next_public_openai_key_fails() -> None:
    env = _base_prod_env()
    env["NEXT_PUBLIC_OPENAI_API_KEY"] = "not-printed"
    assert "browser_secret_key_name" in _codes(env)


def test_runtime_placeholder_secret_detected() -> None:
    env = _base_prod_env()
    env["JWT_SECRET"] = "YOUR_API_KEY_HERE"
    assert "placeholder_required_secret" in _codes(env)


def test_local_fake_provider_allowed_but_warns() -> None:
    env = load_dotenv(ROOT / ".env.local.example")
    issues = validate_env(env, profile="local", template=True)
    assert not [i for i in issues if i.severity == STATUS_ERROR]
    assert any(
        i.code == "local_not_production_ready" and i.severity == STATUS_WARNING
        for i in issues
    )


def test_demo_and_live_bitget_keys_must_not_mix() -> None:
    env = _base_prod_env()
    env["BITGET_API_KEY"] = "live-key-reference"
    env["BITGET_DEMO_API_KEY"] = "demo-key-reference"
    assert "bitget_demo_live_key_mix" in _codes(env)


def test_missing_required_field_reported() -> None:
    env = _base_prod_env()
    env.pop("DATABASE_URL")
    assert "missing_required_key" in _codes(env)


def test_password_values_are_redacted_in_cli_errors(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.production"
    env = _base_prod_env()
    env["DEBUG"] = "true"
    env["POSTGRES_PASSWORD"] = "super-secret-password-that-must-not-print"
    env_file.write_text("\n".join(f"{k}={v}" for k, v in env.items()), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--env-file",
            str(env_file),
            "--profile",
            "production",
            "--strict-runtime",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert "super-secret-password-that-must-not-print" not in result.stdout
    assert "super-secret-password-that-must-not-print" not in result.stderr


def test_repository_production_template_passes() -> None:
    env = load_dotenv(ROOT / ".env.production.example")
    issues = validate_env(env, profile="production", template=True)
    assert not [i for i in issues if i.severity == STATUS_ERROR]
