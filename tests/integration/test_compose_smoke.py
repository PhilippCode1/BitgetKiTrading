"""Wrapper um integration_compose_smoke.sh bei RUN_COMPOSE_SMOKE=1."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "integration_compose_smoke.sh"


@pytest.mark.compose_smoke
@pytest.mark.slow
@pytest.mark.integration
def test_compose_stack_smoke_via_healthcheck_script() -> None:
    if os.getenv("RUN_COMPOSE_SMOKE", "").strip() != "1":
        pytest.skip("RUN_COMPOSE_SMOKE=1 und laufender Compose-Stack erforderlich")
    if not SCRIPT.is_file():
        pytest.fail("scripts/integration_compose_smoke.sh fehlt")
    env = os.environ.copy()
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout or "")
        sys.stderr.write(proc.stderr or "")
        pytest.fail(f"compose smoke exit {proc.returncode}")
