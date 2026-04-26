"""Smoke: Alert-Routing-Verifier --strict laeuft auf dem echten Repo (ohne Netzwerk)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_verify_alert_routing_strict_repo_exit_zero() -> None:
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "verify_alert_routing.py"), "--strict"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, (r.stdout, r.stderr)
