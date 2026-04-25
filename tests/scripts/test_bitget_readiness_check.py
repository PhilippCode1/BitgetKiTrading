from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.bitget_readiness_check import (
    build_readiness_report,
    load_dotenv,
    report_to_markdown,
)


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "bitget_readiness_check.py"


def _base_env() -> dict[str, str]:
    return {
        "PRODUCTION": "true",
        "APP_ENV": "production",
        "BITGET_DEMO_ENABLED": "false",
        "BITGET_PRODUCT_TYPE": "USDT-FUTURES",
        "BITGET_MARGIN_COIN": "USDT",
    }


def test_dry_run_makes_no_network_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    def fail_client(*_args: object, **_kwargs: object) -> httpx.Client:
        raise AssertionError("network client must not be constructed in dry-run")

    monkeypatch.setattr(httpx, "Client", fail_client)
    report = build_readiness_report(_base_env(), mode="dry-run")
    assert report.result == "PASS_WITH_WARNINGS"
    assert report.public_api_status.status == "unavailable"
    assert report.live_write_allowed is False


def test_secrets_are_redacted_in_markdown_report() -> None:
    env = _base_env()
    secret = "live-secret-value-that-must-not-print"
    env.update(
        {
            "BITGET_API_KEY": "live-key-value-that-must-not-print",
            "BITGET_API_SECRET": secret,
            "BITGET_API_PASSPHRASE": "live-passphrase-that-must-not-print",
        }
    )
    report = build_readiness_report(env, mode="dry-run")
    md = report_to_markdown(report)
    assert secret not in md
    assert "live-key-value-that-must-not-print" not in md
    assert "set_redacted" in md


def test_demo_live_key_mix_fails() -> None:
    env = _base_env()
    env.update(
        {
            "BITGET_API_KEY": "live-key",
            "BITGET_DEMO_API_KEY": "demo-key",
        }
    )
    report = build_readiness_report(env, mode="dry-run")
    assert report.result == "FAIL"
    assert "demo_live_credential_mix" in report.blockers


def test_report_contains_required_fields(tmp_path: Path) -> None:
    output = tmp_path / "bitget_readiness.md"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--env-file",
            ".env.production.example",
            "--mode",
            "dry-run",
            "--output-md",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    content = output.read_text(encoding="utf-8")
    for required in (
        "Datum/Zeit",
        "Git SHA",
        "Modus",
        "ENV-Profil",
        "Credential-Typ",
        "API-Version/Pfade",
        "Public API Status",
        "Private Read-only Status",
        "Permission Status",
        "Instrument Universe Status",
        "Rate Limit Status",
        "Ergebnis",
        "Live-Write erlaubt",
    ):
        assert required in content


def test_template_env_dry_run_loads() -> None:
    env = load_dotenv(ROOT / ".env.shadow.example")
    report = build_readiness_report(env, mode="dry-run")
    assert report.mode == "dry-run"
    assert report.live_write_allowed is False
