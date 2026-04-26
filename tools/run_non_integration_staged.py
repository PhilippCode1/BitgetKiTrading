#!/usr/bin/env python3
"""
Fuehrt `pytest -m "not integration"` in Teilen aus (kuerzere Laufzeiten, klarer Exit-Code).

Reihenfolge:
1) shared/python/tests
2) services/onchain-sniffer/tests
3) tests/ ausser tests/unit
4) tests/unit

Gegenueber `pytest tests shared/python/tests` (monolithisch, oft 20–40+ Min) bleibt die
Abdeckung gleich, sofern pyproject- testpaths beachtet werden (hier explizit).

Beispiel (Repo-Root; zusaetzliche Args gehen an jede Pytest-Stufe):
  python tools/run_non_integration_staged.py
  python tools/run_non_integration_staged.py -q --tb=line
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

STAGES: tuple[tuple[str, list[str]], ...] = (
    ("shared_python", ["shared/python/tests"]),
    ("onchain_sniffer", ["services/onchain-sniffer/tests"]),
    ("tests_except_unit", ["tests", "--ignore=tests/unit"]),
    ("tests_unit", ["tests/unit"]),
)


def _run_pytest(
    label: str,
    paths: list[str],
    extra: list[str],
) -> int:
    cmd = [sys.executable, "-m", "pytest", *paths, "-m", "not integration", *extra]
    print(f"run_non_integration_staged: [{label}] {' '.join(cmd)}", flush=True)
    return subprocess.call(cmd, cwd=ROOT)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        allow_abbrev=False,
    )
    _args, pytest_extra = parser.parse_known_args(argv)
    for label, spec in STAGES:
        ret = _run_pytest(label, spec, pytest_extra)
        if ret != 0:
            print(
                f"run_non_integration_staged: Stufe {label} fehlgeschlagen exit={ret}",
                file=sys.stderr,
                flush=True,
            )
            return ret
    print("run_non_integration_staged: alle Stufen OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
