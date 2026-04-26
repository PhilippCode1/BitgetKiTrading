from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.asset_governance_evidence_report import (
    REQUIRED_BLOCK_REASON_COVERAGE,
    build_report_payload,
)
from scripts.asset_preflight_evidence_report import REQUIRED_ASSET_PREFLIGHT_REASONS

REPO = Path(__file__).resolve().parents[2]


def test_payload_keeps_private_live_no_go_until_external_asset_evidence_exists() -> None:
    payload = build_report_payload()

    assert payload["private_live_decision"] == "NO_GO"
    assert payload["full_autonomous_live"] == "NO_GO"
    assert "real_bitget_asset_universe_refresh_missing" in payload["external_required"]
    assert "real_per_asset_market_data_quality_window_missing" in payload["external_required"]
    assert "real_orderbook_liquidity_slippage_window_missing" in payload["external_required"]
    assert "owner_signed_asset_risk_tier_acceptance_missing" in payload["external_required"]
    assert payload["summary"]["status"] == "implemented"
    assert payload["summary"]["decision"] == "not_enough_evidence"


def test_asset_preflight_required_reasons_are_covered() -> None:
    payload = build_report_payload()
    preflight = payload["asset_preflight"]

    assert payload["failures"] == []
    assert preflight["live_allowed_count"] == 0
    assert preflight["live_blocked_count"] == preflight["assets_checked"]
    assert set(REQUIRED_ASSET_PREFLIGHT_REASONS).issubset(
        set(preflight["covered_live_preflight_reasons"])
    )
    assert preflight["missing_required_live_preflight_reasons"] == []


def test_required_asset_block_reason_coverage_is_present() -> None:
    payload = build_report_payload()
    coverage = payload["block_reason_coverage"]

    assert set(REQUIRED_BLOCK_REASON_COVERAGE).issubset(set(coverage["covered_block_reasons"]))
    assert coverage["missing_required_block_reasons"] == []
    assert payload["asset_assertions"]["missing_assertions"] == []


def test_fixture_assets_are_fail_closed_by_governance_and_quality() -> None:
    payload = build_report_payload()
    assets = {row["symbol"]: row for row in payload["assets"]}

    assert assets["ALTUSDT"]["governance_state"] == "quarantine"
    assert assets["ALTUSDT"]["submit_allowed"] is False
    assert "state_quarantine_nicht_live_freigegeben" in assets["ALTUSDT"]["block_reasons"]
    assert "asset_tier_unknown" in assets["ALTUSDT"]["block_reasons"]
    assert assets["BTCUSDT"]["governance_state"] == "live_candidate"
    assert assets["BTCUSDT"]["submit_allowed"] is False
    assert "state_live_candidate_nicht_live_freigegeben" in assets["BTCUSDT"]["block_reasons"]
    assert "slippage_zu_hoch" in assets["BTCUSDT"]["block_reasons"]


def test_cli_writes_markdown_and_json(tmp_path: Path) -> None:
    output_md = tmp_path / "asset_governance.md"
    output_json = tmp_path / "asset_governance.json"

    proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "asset_governance_evidence_report.py"),
            "--strict",
            "--output-md",
            str(output_md),
            "--output-json",
            str(output_json),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert output_md.is_file()
    assert output_json.is_file()
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["failures"] == []
    assert payload["private_live_decision"] == "NO_GO"
