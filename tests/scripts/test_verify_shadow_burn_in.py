from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.verify_shadow_burn_in import _fixture_verdict


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "verify_shadow_burn_in.py"


def test_less_than_72h_fails() -> None:
    verdict, blockers, _warnings = _fixture_verdict({"hours_observed": 12})
    assert verdict == "FAIL"
    assert "burn_in_less_than_72h" in blockers


def test_p0_incident_fails() -> None:
    verdict, blockers, _warnings = _fixture_verdict({"hours_observed": 72, "p0_incidents": 1})
    assert verdict == "FAIL"
    assert "p0_incident_present" in blockers


def test_reconcile_fail_fails() -> None:
    verdict, blockers, _warnings = _fixture_verdict({"hours_observed": 72, "reconcile_failures": 1})
    assert verdict == "FAIL"
    assert "reconcile_failures_present" in blockers


def test_good_fixture_passes() -> None:
    verdict, blockers, warnings = _fixture_verdict(
        {
            "hours_observed": 72,
            "multi_asset_data_quality_failures": 0,
            "reconcile_failures": 0,
            "p0_incidents": 0,
            "unexplained_no_trade_reasons": 0,
        }
    )
    assert verdict == "PASS"
    assert blockers == []
    assert warnings == []


def test_report_contains_required_fields(tmp_path: Path) -> None:
    report = tmp_path / "shadow_burn_in.md"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input-json",
            "tests/fixtures/shadow_burn_in_sample.json",
            "--output-md",
            str(report),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    text = report.read_text(encoding="utf-8")
    assert "Shadow Burn-in Evidence" in text
    assert "Multi-Asset-Datenqualitaet" in text
    assert "Reconcile Failures" in text
    assert "P0 Incidents" in text
