from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "reconcile_truth_drill.py"


def test_drill_dry_run() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "dry-run ok" in completed.stdout


def test_drill_report_contains_scenarios_and_no_secrets(tmp_path: Path) -> None:
    out = tmp_path / "drill.md"
    subprocess.run(
        [sys.executable, str(SCRIPT), "--mode", "simulated", "--output-md", str(out)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    text = out.read_text(encoding="utf-8")
    assert "exchange_order_missing" in text
    assert "local_order_missing" in text
    assert "position_mismatch" in text
    assert "unknown_order_state" in text
    assert "safety_latch_required" in text
    lowered = text.lower()
    assert "secret" not in lowered
    assert "token" not in lowered
    assert "password" not in lowered
