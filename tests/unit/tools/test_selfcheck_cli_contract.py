"""
Contract-Smoke: Selfcheck-CLIs ohne DB — verhindert Regression (Ruff am Selfcheck, Skip-Texte).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def no_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)


def test_modul_mate_selfcheck_without_db_ok(no_database_url: object) -> None:
    script = _ROOT / "tools" / "modul_mate_selfcheck.py"
    r = subprocess.run(
        [sys.executable, str(script)],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, (r.stdout, r.stderr)
    out = r.stdout + r.stderr
    assert "OK: Migration 604 + migrate.py vorhanden" in out
    assert "shared_py importierbar" in out
    assert "SKIP: DATABASE_URL nicht gesetzt" in out


@pytest.mark.parametrize(
    "rel_path",
    [
        "tools/production_selfcheck.py",
        "tools/modul_mate_selfcheck.py",
    ],
)
def test_selfcheck_tools_ruff_clean(rel_path: str) -> None:
    """Selfcheck darf nicht an eigenen Ruff-Verstößen scheitern."""
    r = subprocess.run(
        [sys.executable, "-m", "ruff", "check", rel_path],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr or r.stdout
