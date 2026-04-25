from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "private_deployment_preflight.py"


def _run(args: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_env(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_dry_run_without_network() -> None:
    proc = _run(["--dry-run"])
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["network_calls"] == 0


def test_ngrok_preview_without_auth_is_fail(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    _write_env(
        env,
        "\n".join(
            [
                "FRONTEND_URL=https://foo.ngrok-free.app",
                "APP_BASE_URL=https://foo.ngrok-free.app",
                "API_AUTH_MODE=none",
                "LIVE_TRADE_ENABLE=false",
                "SECURITY_ALLOW_EVENT_DEBUG_ROUTES=false",
                "SECURITY_ALLOW_DB_DEBUG_ROUTES=false",
                "SECURITY_ALLOW_ALERT_REPLAY_ROUTES=false",
            ]
        ),
    )
    proc = _run(["--env-file", str(env), "--mode", "local_ngrok_preview"])
    assert proc.returncode == 1
    assert "ngrok_auth_missing" in proc.stdout


def test_ngrok_preview_with_live_trade_enabled_is_fail(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    _write_env(
        env,
        "\n".join(
            [
                "FRONTEND_URL=https://foo.ngrok-free.app",
                "APP_BASE_URL=https://foo.ngrok-free.app",
                "API_AUTH_MODE=api_key",
                "LIVE_TRADE_ENABLE=true",
            ]
        ),
    )
    proc = _run(["--env-file", str(env), "--mode", "local_ngrok_preview"])
    assert proc.returncode == 1
    assert "ngrok_live_trade_enabled" in proc.stdout


def test_production_private_with_debug_true_is_fail(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    _write_env(
        env,
        "\n".join(
            [
                "FRONTEND_URL=https://dashboard.prod.example.com",
                "APP_BASE_URL=https://api.prod.example.com",
                "DEBUG=true",
                "CORS_ALLOW_ORIGINS=https://dashboard.prod.example.com",
                "API_AUTH_MODE=api_key",
                "LIVE_TRADE_ENABLE=false",
            ]
        ),
    )
    proc = _run(["--env-file", str(env), "--mode", "production_private"])
    assert proc.returncode == 1
    assert "debug_enabled_in_sensitive_mode" in proc.stdout


def test_production_private_with_localhost_url_is_fail(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    _write_env(
        env,
        "\n".join(
            [
                "FRONTEND_URL=http://localhost:3000",
                "APP_BASE_URL=http://127.0.0.1:8000",
                "DEBUG=false",
                "CORS_ALLOW_ORIGINS=http://localhost:3000",
                "API_AUTH_MODE=api_key",
            ]
        ),
    )
    proc = _run(["--env-file", str(env), "--mode", "production_private"])
    assert proc.returncode == 1
    assert "localhost_public_url_blocker" in proc.stdout


def test_cors_wildcard_sensitive_profile_is_fail(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    _write_env(
        env,
        "\n".join(
            [
                "FRONTEND_URL=https://dashboard.staging.example.com",
                "APP_BASE_URL=https://api.staging.example.com",
                "DEBUG=false",
                "CORS_ALLOW_ORIGINS=*",
                "API_AUTH_MODE=api_key",
            ]
        ),
    )
    proc = _run(["--env-file", str(env), "--mode", "staging_private"])
    assert proc.returncode == 1
    assert "cors_wildcard_sensitive_profile" in proc.stdout


def test_output_report_contains_no_secrets_and_german_mode(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    out_md = tmp_path / "report.md"
    _write_env(
        env,
        "\n".join(
            [
                "FRONTEND_URL=https://dashboard.staging.example.com",
                "APP_BASE_URL=https://api.staging.example.com",
                "DEBUG=false",
                "CORS_ALLOW_ORIGINS=https://dashboard.staging.example.com",
                "API_AUTH_MODE=api_key",
                "DASHBOARD_GATEWAY_AUTHORIZATION=Bearer SECRET_TOKEN_SHOULD_NOT_APPEAR",
            ]
        ),
    )
    proc = _run(["--env-file", str(env), "--mode", "staging_private", "--output-md", str(out_md)])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    content = out_md.read_text(encoding="utf-8")
    assert "Main-Console-Sicherheitsmodus" in content
    lowered = content.lower()
    assert "secret_token_should_not_appear" not in lowered
    assert "authorization" not in lowered
