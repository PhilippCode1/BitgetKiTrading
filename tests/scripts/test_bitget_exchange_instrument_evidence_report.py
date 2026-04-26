from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.bitget_exchange_instrument_evidence_report import (
    REQUIRED_ASSET_UNIVERSE_BLOCK_REASONS,
    REQUIRED_INSTRUMENT_BLOCK_REASONS,
    REQUIRED_LIVE_PREFLIGHT_REASONS,
    assess_external_evidence,
    build_external_evidence_template,
    build_report_payload,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "bitget_exchange_instrument_evidence_report.py"


def _verified_external_payload() -> dict[str, object]:
    payload = build_external_evidence_template()
    payload.update(
        {
            "status": "verified",
            "environment": "staging-shadow",
            "git_sha": "abc1234",
            "reviewed_at": "2026-04-26T00:00:00Z",
            "reviewed_by": "external-security-review",
        }
    )
    payload["key_permissions"] = {
        "read_permission": True,
        "trade_permission": True,
        "withdrawal_permission": False,
        "ip_allowlist_enabled": True,
        "account_protection_enabled": True,
        "api_version": "v2",
        "evidence_reference": "evidence://bitget/key-permissions",
    }
    payload["readonly_discovery"] = {
        "public_time_checked": True,
        "server_time_skew_ms": 123,
        "public_instruments_checked": True,
        "private_readonly_checked": True,
        "write_endpoints_called": False,
        "rate_limit_observed": False,
        "report_uri": "evidence://bitget/readonly-discovery",
    }
    payload["instrument_metadata"] = {
        "asset_universe_checked": True,
        "instrument_count": 42,
        "all_symbols_v2_format": True,
        "product_type_margin_coin_checked": True,
        "precision_tick_lot_min_qty_checked": True,
        "unknown_or_delisted_assets_block_live": True,
        "metadata_fresh": True,
        "report_uri": "evidence://bitget/instruments",
    }
    payload["safety"] = {
        "secrets_redacted": True,
        "real_orders_possible": False,
        "owner_signoff": True,
    }
    return payload


def test_report_keeps_live_no_go_and_covers_required_internal_reasons() -> None:
    payload = build_report_payload()

    assert payload["private_live_decision"] == "NO_GO"
    assert payload["full_autonomous_live"] == "NO_GO"
    assert payload["readiness_dry_run"]["live_write_allowed"] is False
    assert payload["external_evidence_assessment"]["status"] == "FAIL"
    assert payload["live_allowed_fixture_assets"] == []
    assert payload["missing_instrument_block_reasons"] == []
    assert payload["missing_asset_universe_block_reasons"] == []
    assert payload["missing_live_preflight_reasons"] == []
    assert set(REQUIRED_INSTRUMENT_BLOCK_REASONS).issubset(payload["covered_instrument_block_reasons"])
    assert set(REQUIRED_ASSET_UNIVERSE_BLOCK_REASONS).issubset(payload["asset_universe_reasons"])
    assert set(REQUIRED_LIVE_PREFLIGHT_REASONS).issubset(payload["covered_live_preflight_reasons"])


def test_instrument_scenarios_block_submit_through_preflight() -> None:
    payload = build_report_payload()

    assert all(row["is_live_allowed"] is False for row in payload["instrument_scenarios"])
    assert any("missing_product_type_for_futures" in row["block_reasons"] for row in payload["instrument_scenarios"])
    assert any("tier_4_shadow_only" in row["block_reasons"] for row in payload["instrument_scenarios"])
    assert any("missing_owner_approval" in row["block_reasons"] for row in payload["instrument_scenarios"])
    assert any(
        row["preflight"]["submit_allowed"] is False
        and "instrument_contract_missing" in row["preflight"]["blocking_reasons"]
        for row in payload["instrument_scenarios"]
    )


def test_external_template_fails_until_real_bitget_evidence_exists() -> None:
    assessment = assess_external_evidence(build_external_evidence_template())

    assert assessment["status"] == "FAIL"
    assert assessment["external_required"] is True
    assert "external_status_nicht_verified" in assessment["failures"]
    assert "key_permissions_ip_allowlist_enabled_nicht_belegt" in assessment["failures"]
    assert "readonly_discovery_public_time_checked_nicht_belegt" in assessment["failures"]
    assert "instrument_metadata_asset_universe_checked_nicht_belegt" in assessment["failures"]


def test_external_verified_payload_passes_without_live_writes_or_secrets() -> None:
    assessment = assess_external_evidence(_verified_external_payload())

    assert assessment["status"] == "PASS"
    assert assessment["external_required"] is False
    assert assessment["failures"] == []


def test_external_evidence_rejects_write_calls_and_secret_surfaces() -> None:
    payload = _verified_external_payload()
    payload["readonly_discovery"]["write_endpoints_called"] = True  # type: ignore[index]
    payload["api_key"] = "real-looking-value"

    assessment = assess_external_evidence(payload)

    assert assessment["status"] == "FAIL"
    assert "readonly_discovery_darf_keine_write_endpoints_aufrufen" in assessment["failures"]
    assert any("api_key" in item for item in assessment["failures"])


def test_cli_writes_report_and_template(tmp_path: Path) -> None:
    out_md = tmp_path / "bitget_exchange_instrument.md"
    out_json = tmp_path / "bitget_exchange_instrument.json"
    template = tmp_path / "template.json"

    template_proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--write-template", str(template)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert template_proc.returncode == 0
    assert json.loads(template.read_text(encoding="utf-8"))["schema_version"] == 1

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--strict",
            "--output-md",
            str(out_md),
            "--output-json",
            str(out_json),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "# Bitget Exchange Instrument Evidence Report" in out_md.read_text(encoding="utf-8")
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["missing_live_preflight_reasons"] == []
