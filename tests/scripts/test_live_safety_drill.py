from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.live_safety_drill import evidence_to_markdown, simulate_safety_drill


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "live_safety_drill.py"


def test_kill_switch_blocks_opening() -> None:
    evidence = simulate_safety_drill("simulated")
    assert evidence.kill_switch_active is True
    assert evidence.opening_order_blocked_by_kill_switch is True


def test_safety_latch_blocks_opening() -> None:
    evidence = simulate_safety_drill("simulated")
    assert evidence.safety_latch_active is True
    assert evidence.opening_order_blocked_by_safety_latch is True


def test_emergency_flatten_is_safe_reduce_only() -> None:
    evidence = simulate_safety_drill("simulated")
    assert evidence.emergency_flatten_reduce_only is True
    assert evidence.emergency_flatten_safe is True


def test_report_contains_go_no_go(tmp_path: Path) -> None:
    report = tmp_path / "live_safety_drill.md"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--mode", "simulated", "--output-md", str(report)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    text = report.read_text(encoding="utf-8")
    assert "Go/No-Go" in text
    assert "NO_GO" in text
    assert "Live-Write erlaubt" in text
    assert "live_write_allowed" in evidence_to_markdown(simulate_safety_drill("simulated"))
