from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_check_multi_asset_strategy_evidence_strict_ok() -> None:
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, str(root / "tools" / "check_multi_asset_strategy_evidence.py"), "--strict"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ok=true" in proc.stdout


def test_check_multi_asset_strategy_evidence_json_parseable() -> None:
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, str(root / "tools" / "check_multi_asset_strategy_evidence.py"), "--json"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert isinstance(payload.get("ok"), bool)
