from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.risk_execution_evidence_report import build_report_payload

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "risk_execution_evidence_report.py"


def test_payload_covers_required_live_preflight_reasons() -> None:
    payload = build_report_payload()
    assert payload["private_live_decision"] == "NO_GO"
    assert payload["missing_required_live_preflight_reasons"] == []
    covered = set(payload["covered_live_preflight_reasons"])
    assert "portfolio_risk_not_safe" in covered
    assert "reconcile_not_ok" in covered
    assert "unknown_order_state_active" in covered
    assert "idempotency_key_missing" in covered
    assert "safety_latch_active" in covered


def test_portfolio_order_and_reconcile_scenarios_block_live() -> None:
    payload = build_report_payload()
    assert all(row["preflight"]["submit_allowed"] is False for row in payload["portfolio_scenarios"])
    assert any("portfolio_snapshot_fehlt" in row["block_reasons"] for row in payload["portfolio_scenarios"])
    assert any("duplicate_client_order_id" in row["block_reasons"] for row in payload["order_idempotency_scenarios"])
    assert any(row["new_state"] == "unknown_submit_state" for row in payload["order_idempotency_scenarios"])
    assert any("unknown_order_state" in row["block_reasons"] for row in payload["reconcile_scenarios"])
    assert any(row["safety_latch_required"] is True for row in payload["reconcile_scenarios"])


def test_cli_writes_markdown_and_json(tmp_path: Path) -> None:
    out_md = tmp_path / "risk_execution.md"
    out_json = tmp_path / "risk_execution.json"
    completed = subprocess.run(
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
    assert completed.returncode == 0
    assert "risk_execution_evidence_report" in completed.stdout
    assert "# Risk Execution Evidence Report" in out_md.read_text(encoding="utf-8")
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["missing_required_live_preflight_reasons"] == []
    assert payload["scenario_counts"]["portfolio"] >= 3
    assert payload["scenario_counts"]["order_idempotency"] >= 6
    assert payload["scenario_counts"]["reconcile"] >= 9
