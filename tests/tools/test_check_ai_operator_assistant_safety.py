from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_check_ai_operator_assistant_safety_ok() -> None:
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, str(root / "tools" / "check_ai_operator_assistant_safety.py"), "--strict"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
