"""Smoke: Master-Status-Generator laeuft ohne Dateischreiben (Dry-Run, Exit 0)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_cursor_master_status_dry_run_exit_zero() -> None:
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "cursor_master_status.py"), "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "NO_GO" in r.stdout or "NO_GO" in r.stderr
    assert "Gesamt-Score" in r.stdout
