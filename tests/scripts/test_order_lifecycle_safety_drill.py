from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "order_lifecycle_safety_drill.py"


def test_drill_dry_run() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "dry-run ok" in completed.stdout


def test_drill_report_contains_scenarios(tmp_path: Path) -> None:
    out = tmp_path / "drill.md"
    subprocess.run(
        [sys.executable, str(SCRIPT), "--mode", "simulated", "--output-md", str(out)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    text = out.read_text(encoding="utf-8").lower()
    assert "successful submit" in text
    assert "unknown submit state" in text
    assert "duplicate retry attempt" in text
    assert "reduce-only exit" in text
    assert "emergency flatten simulation" in text
