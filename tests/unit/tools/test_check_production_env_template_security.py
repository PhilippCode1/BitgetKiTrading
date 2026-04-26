from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "tools" / "check_production_env_template_security.py"


def test_default_repo_templates_pass() -> None:
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, (r.stdout, r.stderr)


def test_forbidden_flag_fails(tmp_path: Path) -> None:
    bad = tmp_path / "bad.env"
    bad.write_text("DEBUG=true\n", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(bad)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 1
    assert "DEBUG" in (r.stderr or "")


def test_clean_template_passes(tmp_path: Path) -> None:
    good = tmp_path / "good.env"
    good.write_text("DEBUG=false\nAPI_AUTH_MODE=api_key\n", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(good)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, (r.stdout, r.stderr)


def test_api_auth_mode_none_fails(tmp_path: Path) -> None:
    bad = tmp_path / "noauth.env"
    bad.write_text("API_AUTH_MODE=none\n", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(bad)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 1
    assert "API_AUTH_MODE" in (r.stderr or "")


def test_bitget_demo_enabled_true_fails(tmp_path: Path) -> None:
    bad = tmp_path / "demo_on.env"
    bad.write_text("BITGET_DEMO_ENABLED=true\n", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(bad)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 1
    assert "BITGET_DEMO_ENABLED" in (r.stderr or "")


def test_dangerous_mock_substring_fails(tmp_path: Path) -> None:
    bad = tmp_path / "mock.env"
    bad.write_text("X_LEGACY_HINT=old_prod_ex_only_value\n", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(bad)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 1
    err = (r.stderr or "").lower()
    assert "prod_ex_only" in err or "mock-teilfolge" in err


def test_next_public_secret_name_fails(tmp_path: Path) -> None:
    bad = tmp_path / "public_secret.env"
    bad.write_text("NEXT_PUBLIC_OPENAI_API_KEY=placeholder\n", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(bad)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 1
    assert "NEXT_PUBLIC" in (r.stderr or "")
