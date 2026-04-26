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
    assert "Evidence" in (r.stdout + r.stderr) or "release-approval" in (r.stdout + r.stderr)


def test_release_sanity_checks_repo_exit_zero() -> None:
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "release_sanity_checks.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, (r.stdout, r.stderr)


def test_generated_status_reports_do_not_claim_marketing_10_of_10() -> None:
    for rel in (
        "docs/production_10_10/production_readiness_scorecard.md",
        "docs/production_10_10/CURSOR_MASTER_STATUS.md",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8").lower()
        lines = [line.strip() for line in text.splitlines() if "10/10 erreicht" in line]
        for line in lines:
            assert any(
                marker in line
                for marker in ("nicht", "duerfen", "verbot", "forbidden", "no_go")
            ), f"Unerlaubte 10/10-Behauptung in {rel}: {line}"
