from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tools.check_env_10_10_safety import load_dotenv
from tools.check_staging_profile import validate_staging_profile


ROOT = Path(__file__).resolve().parents[2]


def base_env() -> dict[str, str]:
    return load_dotenv(ROOT / ".env.staging.example")


def codes(issues: list[object]) -> set[str]:
    return {getattr(issue, "code") for issue in issues}


def test_staging_template_accepts_placeholders() -> None:
    issues = validate_staging_profile(base_env(), template=True, strict_runtime=False)
    assert issues == []


def test_runtime_mode_rejects_placeholders() -> None:
    issues = validate_staging_profile(base_env(), template=False, strict_runtime=True)
    assert "placeholder_runtime_secret" in codes(issues)


def test_live_trade_enable_is_blocked() -> None:
    env = base_env()
    env["LIVE_TRADE_ENABLE"] = "true"
    issues = validate_staging_profile(env, template=True, strict_runtime=False)
    assert "live_trade_forbidden" in codes(issues)


def test_debug_true_is_blocked() -> None:
    env = base_env()
    env["DEBUG"] = "true"
    issues = validate_staging_profile(env, template=True, strict_runtime=False)
    assert "debug_forbidden" in codes(issues)


def test_missing_gateway_auth_is_blocked() -> None:
    env = base_env()
    env["GATEWAY_ENFORCE_SENSITIVE_AUTH"] = "false"
    env["API_AUTH_MODE"] = "none"
    issues = validate_staging_profile(env, template=True, strict_runtime=False)
    assert {"auth_required", "api_auth_required"}.issubset(codes(issues))


def test_localhost_is_blocked_in_strict_runtime() -> None:
    env = base_env()
    env["API_GATEWAY_URL"] = "http://localhost:8000"
    issues = validate_staging_profile(env, template=False, strict_runtime=True)
    assert "loopback_forbidden" in codes(issues)


def test_production_database_and_redis_are_blocked() -> None:
    env = base_env()
    env["DATABASE_URL"] = "postgresql://app:pw@postgres.prod.example.internal:5432/app"
    env["REDIS_URL"] = "redis://redis.production.example.internal:6379/0"
    issues = validate_staging_profile(env, template=True, strict_runtime=False)
    assert "production_datastore_forbidden" in codes(issues)


def test_smoke_dry_run_outputs_expected_checklist() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/staging_smoke.py", "--env-file", ".env.staging.example", "--dry-run"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "gateway_health: planned" in completed.stdout
    assert "live_broker_readiness: planned" in completed.stdout
    assert "bitget_read_only: skipped" in completed.stdout


def test_smoke_report_markdown_is_created(tmp_path: Path) -> None:
    report = tmp_path / "staging_smoke.md"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/staging_smoke.py",
            "--env-file",
            ".env.staging.example",
            "--dry-run",
            "--output-md",
            str(report),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "report=" in completed.stdout
    content = report.read_text(encoding="utf-8")
    assert "# Staging Smoke Report" in content
    assert "Go/No-Go" in content


def test_smoke_output_redacts_secrets(tmp_path: Path) -> None:
    env_text = (ROOT / ".env.staging.example").read_text(encoding="utf-8")
    secret = "Bearer staging-secret-token-123"
    env_text = env_text.replace(
        "DASHBOARD_GATEWAY_AUTHORIZATION=Bearer <STAGING_GATEWAY_READ_TOKEN>",
        f"DASHBOARD_GATEWAY_AUTHORIZATION={secret}",
    )
    env_file = tmp_path / "redaction.example"
    report = tmp_path / "redaction.md"
    env_file.write_text(env_text, encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/staging_smoke.py",
            "--env-file",
            str(env_file),
            "--dry-run",
            "--output-md",
            str(report),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    combined = completed.stdout + completed.stderr + report.read_text(encoding="utf-8")
    assert secret not in combined
    assert "***REDACTED***" in combined
