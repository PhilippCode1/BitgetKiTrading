from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.check_market_data_quality import analyze_market_data_quality


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "check_market_data_quality.py"


def test_tool_runs_and_returns_structure() -> None:
    summary = analyze_market_data_quality()
    assert "ok" in summary
    assert "issues" in summary
    assert "error_count" in summary


def test_json_output_is_parseable() -> None:
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    parsed = json.loads(completed.stdout)
    assert "doc_exists" in parsed
    assert "script_exists" in parsed
    assert "fixture_exists" in parsed
    assert "issues" in parsed
