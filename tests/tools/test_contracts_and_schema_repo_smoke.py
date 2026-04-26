"""Smoke: Contract- und Schema-Gates wie in production_selfcheck (ohne vollstaendigen Selfcheck)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_check_contracts_exit_zero() -> None:
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "check_contracts.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, (r.stdout, r.stderr)


def test_check_schema_signals_fixture_exit_zero() -> None:
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "check_schema.py"),
            "--schema",
            str(
                ROOT
                / "infra"
                / "tests"
                / "schemas"
                / "signals_recent_response.schema.json"
            ),
            "--json_file",
            str(ROOT / "tests" / "fixtures" / "signals_fixture.json"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, (r.stdout, r.stderr)
