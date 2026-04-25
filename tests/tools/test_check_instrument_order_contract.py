from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "check_instrument_order_contract.py"


def test_checker_runs() -> None:
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--strict"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "check_instrument_order_contract" in completed.stdout


def test_checker_json_parseable() -> None:
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert "ok" in payload
    assert "error_count" in payload
