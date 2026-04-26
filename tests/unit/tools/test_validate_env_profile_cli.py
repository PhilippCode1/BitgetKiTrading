from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "filename,profile,expect_fail",
    [
        (".env.production", "local", True),
        (".env.shadow", "local", True),
        (".env.local", "local", False),
    ],
)
def test_profile_matches_env_filename(
    tmp_path: Path, filename: str, profile: str, expect_fail: bool
) -> None:
    p = tmp_path / filename
    p.write_text("POSTGRES_PASSWORD=x\n", encoding="utf-8")
    cmd = [
        sys.executable,
        str(REPO / "tools" / "validate_env_profile.py"),
        "--env-file",
        str(p),
        "--profile",
        profile,
    ]
    r = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, check=False)
    if expect_fail:
        assert r.returncode == 1
        assert "widerspricht" in (r.stderr or "")
    else:
        # fehlt noch fast alles — erwarte Fehler wegen Platzhaltern, nicht wegen Namens-Mismatch
        assert "widerspricht" not in (r.stderr or "")


@pytest.mark.parametrize(
    "env_file,profile",
    [
        (".env.shadow.example", "shadow"),
        (".env.production.example", "production"),
    ],
)
def test_repository_templates_support_template_flag(env_file: str, profile: str) -> None:
    cmd = [
        sys.executable,
        str(REPO / "tools" / "validate_env_profile.py"),
        "--env-file",
        env_file,
        "--profile",
        profile,
        "--template",
    ]
    r = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "OK validate_env_profile" in r.stdout


def test_shadow_template_requires_fail_closed_live_submit_gates(tmp_path: Path) -> None:
    env_text = (REPO / ".env.shadow.example").read_text(encoding="utf-8")
    env_text = env_text.replace(
        "LIVE_ENABLE_PRE_FLIGHT_LIQUIDITY_GUARD=true",
        "LIVE_ENABLE_PRE_FLIGHT_LIQUIDITY_GUARD=false",
    )
    env_file = tmp_path / ".env.shadow"
    env_file.write_text(env_text, encoding="utf-8")
    cmd = [
        sys.executable,
        str(REPO / "tools" / "validate_env_profile.py"),
        "--env-file",
        str(env_file),
        "--profile",
        "shadow",
        "--template",
    ]
    r = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, check=False)
    assert r.returncode == 1
    assert "LIVE_ENABLE_PRE_FLIGHT_LIQUIDITY_GUARD=true Pflicht" in r.stderr


def test_production_template_requires_exchange_truth_submit_gate(tmp_path: Path) -> None:
    env_text = (REPO / ".env.production.example").read_text(encoding="utf-8")
    env_text = env_text.replace(
        "LIVE_BROKER_BLOCK_LIVE_WITHOUT_EXCHANGE_TRUTH=true",
        "LIVE_BROKER_BLOCK_LIVE_WITHOUT_EXCHANGE_TRUTH=false",
    )
    env_file = tmp_path / ".env.production"
    env_file.write_text(env_text, encoding="utf-8")
    cmd = [
        sys.executable,
        str(REPO / "tools" / "validate_env_profile.py"),
        "--env-file",
        str(env_file),
        "--profile",
        "production",
        "--template",
    ]
    r = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, check=False)
    assert r.returncode == 1
    assert "LIVE_BROKER_BLOCK_LIVE_WITHOUT_EXCHANGE_TRUTH=true Pflicht" in r.stderr
