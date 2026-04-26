"""Smoke: zentrale Merge-/Release-Skripte laufen im echten Repo ohne Exit 1 (kein Netzwerk)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_check_release_approval_gates_repo_exit_zero() -> None:
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "check_release_approval_gates.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, (r.stdout, r.stderr)


def test_release_sanity_checks_repo_exit_zero() -> None:
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "release_sanity_checks.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, (r.stdout, r.stderr)
