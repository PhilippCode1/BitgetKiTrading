from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "check_german_ui_language.py"


def test_check_german_ui_language_strict_ok() -> None:
    proc = subprocess.run(
        [sys.executable, str(TOOL), "--strict"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_check_german_ui_language_json_parseable() -> None:
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


def test_no_forbidden_navigation_terms_reported() -> None:
    proc = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    codes = {issue["code"] for issue in payload.get("issues", [])}
    assert "forbidden_term_in_visible_nav" not in codes
    assert "forbidden_route_in_primary_nav" not in codes


def test_status_doc_present_and_complete() -> None:
    proc = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    codes = {issue["code"] for issue in payload.get("issues", [])}
    assert "required_file_missing" not in codes
    assert "status_doc_topic_missing" not in codes
