"""End-to-end Konfig-Gates: inkonsistente Modus-Flags muessen beim Settings-Boot scheitern."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "tests" / "integration" / "fixtures" / "try_load_base_settings.py"


def _base_env() -> dict[str, str]:
    db = (os.getenv("TEST_DATABASE_URL") or "").strip()
    redis = (os.getenv("TEST_REDIS_URL") or "").strip()
    if not db or not redis:
        return {}
    return {
        "APP_ENV": "test",
        "PRODUCTION": "false",
        "DATABASE_URL": db,
        "REDIS_URL": redis,
        "EXECUTION_MODE": "shadow",
        "SHADOW_TRADE_ENABLE": "true",
        "LIVE_TRADE_ENABLE": "true",
        "LIVE_BROKER_ENABLED": "true",
        "STRATEGY_EXEC_MODE": "manual",
        "RISK_HARD_GATING_ENABLED": "true",
        "RISK_REQUIRE_7X_APPROVAL": "true",
        "RISK_ALLOWED_LEVERAGE_MIN": "7",
        "RISK_ALLOWED_LEVERAGE_MAX": "75",
        "LIVE_KILL_SWITCH_ENABLED": "true",
    }


@pytest.mark.integration
def test_subprocess_rejects_live_trade_enable_under_shadow_execution() -> None:
    extra = _base_env()
    if not extra:
        pytest.skip("TEST_DATABASE_URL / TEST_REDIS_URL")

    env = os.environ.copy()
    env.update(extra)
    _pp = [str(REPO)]
    if env.get("PYTHONPATH"):
        _pp.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(_pp)
    proc = subprocess.run(
        [sys.executable, str(FIXTURE)],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
