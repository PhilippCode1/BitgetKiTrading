from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "check_asset_governance.py"


def test_checker_detects_required_files() -> None:
    completed = subprocess.run(
        [sys.executable, str(TOOL)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "check_asset_governance" in completed.stdout


def test_checker_json_parseable() -> None:
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    parsed = json.loads(completed.stdout)
    assert "ok" in parsed
    assert "doc_exists" in parsed
    assert "script_exists" in parsed
