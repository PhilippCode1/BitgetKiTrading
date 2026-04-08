"""Contract-Parity: tools/check_contracts.py muss im CI-Grünzustand exit 0 liefern."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_check_contracts_script_exits_zero() -> None:
    script = REPO_ROOT / "tools" / "check_contracts.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, (
        f"check_contracts failed rc={proc.returncode}\n"
        f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    )
    assert "check_contracts: OK" in proc.stdout
