"""P84: Iron Curtain lehnt Lauf ohne ENVIRONMENT=production ab."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_iron_curtain_exits_1_without_production_env() -> None:
    root = Path(__file__).resolve().parents[3]
    env = {k: v for k, v in os.environ.items() if k != "ENVIRONMENT"}
    rc = subprocess.run(
        [sys.executable, str(root / "scripts" / "release_gate.py"), "--iron-curtain"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert rc.returncode == 1
    out = f"{rc.stderr or ''} {rc.stdout or ''}"
    assert "ENVIRONMENT=production" in out


def test_onchain_sniffer_suites_sind_in_iron_curtain_pytest_pfad() -> None:
    """Jeder Fehlschlag in diesem Ordner bremst damit die Logic-Phase (P84)."""
    root = Path(__file__).resolve().parents[3]
    text = (root / "scripts" / "release_gate.py").read_text(encoding="utf-8")
    assert "services/onchain-sniffer/tests" in text
