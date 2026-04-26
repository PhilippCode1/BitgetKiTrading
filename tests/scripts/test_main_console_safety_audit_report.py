from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.main_console_safety_audit_report import build_report_payload

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "main_console_safety_audit_report.py"


def test_payload_keeps_private_live_no_go_and_orders_impossible() -> None:
    payload = build_report_payload()
    assert payload["private_live_decision"] == "NO_GO"
    assert payload["full_autonomous_live"] == "NO_GO"
    assert payload["blocking_failures"] == []
    assert payload["missing_visible_gates"] == []
    assert payload["secret_safe"] is True
    for row in payload["scenarios"]:
        assert row["private_live_allowed"] == "NO_GO"
        assert row["real_orders_possible"] is False
        assert row["blocked_by_safety_center"] is True
        assert row["blocking_reasons"]
        assert row["audit_valid"] is True
        assert "Live bleibt verboten" in row["reason_text_de"] or "gesperrt" in row["reason_text_de"]


def test_payload_covers_required_operator_visible_gates() -> None:
    payload = build_report_payload()
    by_id = {row["id"]: row for row in payload["scenarios"]}
    assert "reconcile_status_blocks_live" in by_id["reconcile_unknown"]["blocking_reasons"]
    assert "exchange_truth_blocks_live" in by_id["exchange_truth_missing"]["blocking_reasons"]
    assert "kill_switch_blocks_live" in by_id["kill_switch_active"]["blocking_reasons"]
    assert "safety_latch_blocks_live" in by_id["safety_latch_active"]["blocking_reasons"]
    assert "backend_unavailable_blocks_live" in by_id["backend_unavailable"]["blocking_reasons"]
    assert all("Entscheidung fuer ALL: do_not_trade" in row["forensic_summary_de"] for row in payload["scenarios"])


def test_cli_writes_markdown_and_json(tmp_path: Path) -> None:
    out_md = tmp_path / "main_console_safety_audit.md"
    out_json = tmp_path / "main_console_safety_audit.json"
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
    assert "main_console_safety_audit_report" in completed.stdout
    assert "# Main Console Safety / Audit Evidence Report" in out_md.read_text(encoding="utf-8")
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["scenario_count"] == 5
    assert payload["audit_valid_count"] == 5
    assert payload["blocking_failures"] == []
