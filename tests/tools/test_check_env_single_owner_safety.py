from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tools.check_env_single_owner_safety import (
    STATUS_ERROR,
    STATUS_WARNING,
    load_dotenv,
    validate_env,
)


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "check_env_single_owner_safety.py"


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


def test_repository_templates_pass_single_owner_checker() -> None:
    for env_file, profile in (
        (".env.production.example", "production"),
        (".env.shadow.example", "shadow"),
        (".env.local.example", "local"),
    ):
        completed = subprocess.run(
            [
                sys.executable,
                str(TOOL),
                "--env-file",
                env_file,
                "--profile",
                profile,
                "--template",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr


def test_local_fake_provider_allowed() -> None:
    env = load_dotenv(ROOT / ".env.local.example")
    issues = validate_env(env, profile="local", template=True)
    assert not [issue for issue in issues if issue.severity == STATUS_ERROR]
    assert any(issue.code == "local_not_production_ready" and issue.severity == STATUS_WARNING for issue in issues)


def test_payment_billing_not_required_for_private_scope() -> None:
    env = _base_prod_env()
    env.pop("PAYMENT_STRIPE_SECRET_KEY", None)
    env.pop("PAYMENT_MOCK_WEBHOOK_SECRET", None)
    env.pop("COMMERCIAL_METER_SECRET", None)
    codes = _codes(env)
    assert "missing_required_key" not in codes
    assert "live_trade_requires_commercial_tenant_gates" not in codes


def test_cli_output_redacts_secret_values(tmp_path: Path) -> None:
    env = _base_prod_env()
    secret = "super-secret-password-that-must-not-print"
    env["DEBUG"] = "true"
    env["POSTGRES_PASSWORD"] = secret
    env_file = tmp_path / ".env.production"
    env_file.write_text("\n".join(f"{k}={v}" for k, v in env.items()), encoding="utf-8")
    completed = subprocess.run(
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
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert secret not in completed.stdout
    assert secret not in completed.stderr
