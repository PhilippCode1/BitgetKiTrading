from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import uuid
from pathlib import Path

from typing import Any

REPO = Path(__file__).resolve().parents[3]
FX = REPO / "tests" / "fixtures" / "github"
SCRIPT = REPO / "tools" / "check_github_branch_protection.py"


def _load() -> Any:
    name = f"check_bp_{uuid.uuid4().hex[:8]}"
    sp = importlib.util.spec_from_file_location(name, SCRIPT)
    m = importlib.util.module_from_spec(sp)
    assert sp.loader
    sys.modules[name] = m
    sp.loader.exec_module(m)  # type: ignore[union-attr]
    return m


def _run(*args: str, jpath: Path | None = None) -> tuple[int, dict]:  # noqa: ANN001
    p: list = [sys.executable, str(SCRIPT), *args]
    if jpath is not None:
        p.extend(["--json", str(jpath)])
    r = subprocess.run(
        p,
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    if jpath is not None and jpath.is_file():
        j = json.loads(jpath.read_text(encoding="utf-8"))
    else:
        j = json.loads(r.stdout) if (r.stdout or "").strip() else {}
    return r.returncode, j


def test_offline_pass_strict_0(tmp_path: Path) -> None:
    c, j = _run(
        "--offline-fixture",
        str(FX / "branch_protection_pass.json"),
        "--strict",
        jpath=tmp_path / "j.json",
    )
    assert c == 0, (j, j.get("status"))
    assert j.get("status") == "PASS"
    assert j.get("release_approval_check_present", True) is not False
    assert not (j.get("missing_for_ci_yml") or [])


def test_offline_pass_report_md(tmp_path: Path) -> None:
    out = tmp_path / "b.md"
    c, _ = _run(
        "--offline-fixture",
        str(FX / "branch_protection_pass.json"),
        "--report-md",
        str(out),
    )
    assert c == 0
    assert "Branch-Protection" in out.read_text(encoding="utf-8")


def test_offline_fail_strict_1(tmp_path: Path) -> None:
    c, j = _run(
        "--offline-fixture",
        str(FX / "branch_protection_fail.json"),
        "--strict",
        jpath=tmp_path / "j2.json",
    )
    assert c == 1
    assert j.get("status") == "FAIL"
    assert "release-approval-gate" in (j.get("missing_for_ci_yml") or [])


def test_offline_unknown_strict_1(tmp_path: Path) -> None:
    c, j = _run(
        "--offline-fixture",
        str(FX / "branch_protection_unknown.json"),
        "--strict",
        jpath=tmp_path / "j3.json",
    )
    assert c == 1
    assert j.get("status") == "UNKNOWN"


def test_module_offline_and_noauth() -> None:
    m = _load()
    a, b = m.run("o/p", "main", FX / "branch_protection_pass.json", None)
    assert a.status == "PASS"
    assert b and "offline" in str(b)
    no = m.eval_noauth()
    assert no.status == "UNKNOWN_NO_GITHUB_AUTH"
    assert a.release_approval_check_present