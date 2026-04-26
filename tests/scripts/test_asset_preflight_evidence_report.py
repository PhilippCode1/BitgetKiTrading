from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.asset_preflight_evidence_report import build_report_payload


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "asset_preflight_evidence_report.py"


def test_payload_blocks_fixture_assets_fail_closed() -> None:
    payload = build_report_payload()
    assert payload["assets_checked"] == 2
    assert payload["private_live_decision"] == "NO_GO"
    assert payload["live_allowed_count"] == 0
    assert payload["missing_required_live_preflight_reasons"] == []
    assert "asset_not_live_allowed" in payload["covered_live_preflight_reasons"]
    assert "data_quality_not_pass" in payload["covered_live_preflight_reasons"]
    assert "liquidity_not_pass" in payload["covered_live_preflight_reasons"]
    assert "slippage_too_high" in payload["covered_live_preflight_reasons"]
    assert "risk_tier_not_live_allowed" in payload["covered_live_preflight_reasons"]
    assert "order_sizing_not_safe" in payload["covered_live_preflight_reasons"]
    assert "strategy_evidence_missing_or_invalid" in payload["covered_live_preflight_reasons"]
    by_symbol = {row["symbol"]: row for row in payload["assets"]}
    assert by_symbol["BTCUSDT"]["live_preflight_status"] == "LIVE_BLOCKED"
    assert by_symbol["BTCUSDT"]["submit_allowed"] is False
    assert "state_live_candidate_nicht_live_freigegeben" in by_symbol["BTCUSDT"]["block_reasons"]
    assert "asset_not_live_allowed" in by_symbol["BTCUSDT"]["live_preflight_blocking_reasons"]
    assert "slippage_too_high" in by_symbol["BTCUSDT"]["live_preflight_blocking_reasons"]
    assert by_symbol["ALTUSDT"]["live_preflight_status"] == "LIVE_BLOCKED"
    assert by_symbol["ALTUSDT"]["submit_allowed"] is False
    assert "asset_tier_unknown" in by_symbol["ALTUSDT"]["block_reasons"]
    assert "data_quality_not_pass" in by_symbol["ALTUSDT"]["live_preflight_blocking_reasons"]
    assert "risk_tier_not_live_allowed" in by_symbol["ALTUSDT"]["live_preflight_blocking_reasons"]


def test_cli_writes_markdown_and_json(tmp_path: Path) -> None:
    out_md = tmp_path / "asset_preflight.md"
    out_json = tmp_path / "asset_preflight.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--output-md",
            str(out_md),
            "--output-json",
            str(out_json),
            "--strict",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "asset_preflight_evidence_report" in completed.stdout
    content = out_md.read_text(encoding="utf-8")
    assert "# Asset Preflight Evidence Report" in content
    assert "Private-Live-Entscheidung: `NO_GO`" in content
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["live_blocked_count"] == payload["assets_checked"]
    assert not payload["live_allowed_assets"]
    assert payload["missing_required_live_preflight_reasons"] == []
    assert "Live-Broker-Preflight-Coverage" in content
