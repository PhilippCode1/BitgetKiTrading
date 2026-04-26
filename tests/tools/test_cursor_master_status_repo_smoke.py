"""Smoke: Master-Status-Generator laeuft ohne Dateischreiben (Dry-Run, Exit 0)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MASTER_STATUS = ROOT / "docs" / "production_10_10" / "CURSOR_MASTER_STATUS.md"


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


def test_update_cursor_master_status_alias_dry_run_exit_zero() -> None:
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "update_cursor_master_status.py"), "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "Go/No-Go" in r.stdout


def test_cursor_master_status_file_contains_required_truth_sections() -> None:
    assert MASTER_STATUS.is_file(), f"fehlt: {MASTER_STATUS}"
    text = MASTER_STATUS.read_text(encoding="utf-8")
    required_tokens = (
        "Gesamt-Score",
        "P0-Blocker",
        "P1-Blocker",
        "Verified-Kategorien",
        "Implemented-Kategorien",
        "External-Required-Kategorien",
        "## Go/No-Go",
        "local_dev",
        "paper",
        "shadow",
        "staging",
        "private_live_candidate",
        "private_live_allowed",
        "full_autonomous_live",
        "## Scores je Bereich",
        "## Offene P0-Luecken",
    )
    for token in required_tokens:
        assert token in text
