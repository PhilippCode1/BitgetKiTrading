from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.check_private_audit_forensics import analyze_private_audit_forensics


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "check_private_audit_forensics.py"


def test_checker_detects_repository_surface() -> None:
    summary = analyze_private_audit_forensics()
    assert "doc_exists" in summary
    assert "contract_exists" in summary
    assert "replay_summary_exists" in summary
    assert "issues" in summary


def test_json_output_parseable() -> None:
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    parsed = json.loads(completed.stdout)
    assert "error_count" in parsed
    assert "issues" in parsed


def test_strict_exits_clean_when_surface_complete() -> None:
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--strict"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
