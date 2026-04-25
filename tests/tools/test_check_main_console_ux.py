from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "check_main_console_ux.py"


def test_check_main_console_ux_strict_ok() -> None:
    proc = subprocess.run(
        [sys.executable, str(TOOL), "--strict"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ok=true" in proc.stdout


def test_check_main_console_ux_json_parseable() -> None:
    proc = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert isinstance(payload.get("ok"), bool)
    assert "issues" in payload


def test_required_navigation_modules_enforced() -> None:
    proc = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    issue_codes = {item["code"] for item in payload.get("issues", [])}
    assert "required_nav_module_missing" not in issue_codes


def test_forbidden_billing_customer_terms_not_in_main_nav() -> None:
    proc = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    issue_codes = {item["code"] for item in payload.get("issues", [])}
    assert "forbidden_term_in_main_navigation" not in issue_codes
