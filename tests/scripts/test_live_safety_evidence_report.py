from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.live_safety_evidence_report import REQUIRED_SAFETY_BLOCKERS, build_report_payload

REPO = Path(__file__).resolve().parents[2]


def test_payload_keeps_private_live_no_go_until_external_drill_exists() -> None:
    payload = build_report_payload()

    assert payload["private_live_decision"] == "NO_GO"
    assert payload["full_autonomous_live"] == "NO_GO"
    assert "real_staging_shadow_kill_switch_drill_missing" in payload["external_required"]
    assert "real_staging_shadow_safety_latch_drill_missing" in payload["external_required"]
    assert "real_emergency_flatten_reduce_only_drill_missing" in payload["external_required"]
    assert "owner_signed_live_safety_acceptance_missing" in payload["external_required"]


def test_external_template_must_fail_closed_and_cover_required_blockers() -> None:
    payload = build_report_payload()

    assert payload["failures"] == []
    assert payload["external_template"]["status"] == "FAIL"
    assert set(REQUIRED_SAFETY_BLOCKERS).issubset(set(payload["external_template"]["blockers"]))
    assert payload["external_template"]["missing_required_blockers"] == []
    assert payload["external_template"]["secret_surface_issues"] == []


def test_simulation_blocks_live_and_opening_orders() -> None:
    payload = build_report_payload()
    simulation = payload["simulation"]

    assert simulation["go_no_go"] == "NO_GO"
    assert simulation["live_write_allowed"] is False
    assert simulation["opening_order_blocked_by_kill_switch"] is True
    assert simulation["opening_order_blocked_by_safety_latch"] is True
    assert simulation["emergency_flatten_safe"] is True


def test_main_console_and_emergency_flatten_cases_are_fail_closed() -> None:
    payload = build_report_payload()

    assert all(case["blocked"] is True for case in payload["main_console_cases"])
    cases = {case["id"]: case for case in payload["emergency_flatten_cases"]}
    assert cases["valid_reduce_only"]["safe"] is True
    assert cases["not_reduce_only"]["safe"] is False
    assert cases["would_increase_exposure"]["safe"] is False
    assert cases["missing_position_truth"]["safe"] is False


def test_cli_writes_markdown_and_json(tmp_path: Path) -> None:
    output_md = tmp_path / "live_safety.md"
    output_json = tmp_path / "live_safety.json"

    proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "live_safety_evidence_report.py"),
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
