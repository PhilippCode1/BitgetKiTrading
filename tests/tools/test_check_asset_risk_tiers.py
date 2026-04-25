from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.check_asset_risk_tiers import analyze_asset_risk_tiers

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "check_asset_risk_tiers.py"


def test_tool_runs_and_returns_structure() -> None:
    summary = analyze_asset_risk_tiers()
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
    assert "risk_tier_logic_exists" in parsed
    assert "risk_governor_exists" in parsed
    assert "issues" in parsed
