from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    ("prod", "allow", "expect_fail_msg"),
    [
        ("true", "true", "verboten"),
        ("1", "yes", "verboten"),
    ],
)
def test_migrate_demo_seeds_rejects_production_with_allow(
    prod: str, allow: str, expect_fail_msg: str
) -> None:
    env = os.environ.copy()
    env["PRODUCTION"] = prod
    env["BITGET_ALLOW_DEMO_SCHEMA_SEEDS"] = allow
    env["DATABASE_URL"] = "postgresql://u:p@127.0.0.1:59999/nope"
    r = subprocess.run(
        [sys.executable, str(REPO / "infra" / "migrate.py"), "--demo-seeds"],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 1
    assert expect_fail_msg in (r.stderr or "")


def test_migrate_demo_seeds_skips_without_allow() -> None:
    env = os.environ.copy()
    env.pop("BITGET_ALLOW_DEMO_SCHEMA_SEEDS", None)
    env["PRODUCTION"] = "false"
    env["DATABASE_URL"] = "postgresql://u:p@127.0.0.1:59999/nope"
    r = subprocess.run(
        [sys.executable, str(REPO / "infra" / "migrate.py"), "--demo-seeds"],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0
    assert "demo-seeds skipped" in (r.stdout or "")
