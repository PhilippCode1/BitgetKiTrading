from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "check_single_admin_entry_flow.py"


def test_single_admin_entry_flow_strict_ok() -> None:
    proc = subprocess.run(
        [sys.executable, str(TOOL), "--strict"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_single_admin_entry_flow_json_parseable() -> None:
    proc = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert isinstance(payload.get("ok"), bool)
    assert "issues" in payload
