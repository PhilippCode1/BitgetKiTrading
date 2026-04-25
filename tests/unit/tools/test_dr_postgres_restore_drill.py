from __future__ import annotations

import importlib.util
import subprocess
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "tools" / "dr_postgres_restore_drill.py"


def _load_mod():
    name = f"drp_{uuid.uuid4().hex[:8]}"
    s = importlib.util.spec_from_file_location(name, TOOL)
    m = importlib.util.module_from_spec(s)
    assert s and s.loader
    sys.modules[name] = m
    s.loader.exec_module(m)  # type: ignore[union-attr]
    return m


def test_redact_dsn() -> None:
    m = _load_mod()
    x = m._redact_dsn("postgresql://u:secret@host:5432/db")
    assert "***" in x
    assert "secret" not in x


def test_read_env_dsn(tmp_path: Path) -> None:
    m = _load_mod()
    p = tmp_path / "e"
    p.write_text("DATABASE_URL=postgresql://a:b@h:1/x\n", encoding="utf-8")
    d = m._read_env_dsn(p, False)
    assert d and "h:1" in d


def test_read_env_test_first(tmp_path: Path) -> None:
    m = _load_mod()
    p = tmp_path / "e2"
    p.write_text("TEST_DATABASE_URL=postgresql://t:tp@h:1/testdb\n", encoding="utf-8")
    d2 = m._read_env_dsn(p, True)
    assert d2 and "testdb" in d2


def test_exit_codes() -> None:
    m = _load_mod()
    assert m._exit("PASS") == 0
    assert m._exit("DRYRUN_OK") == 0
    assert m._exit("FAIL") == 1


def test_render_md_contains_status() -> None:
    m = _load_mod()
    r = m.DrillResult(
        status="FAIL",
        message="m",
        schema_name="s1",
        dsn_sanitized="p",
        git_sha="abc",
        rto_sec=1.0,
        rpo_model_sec=0.1,
        total_sec=2.0,
        before_sha256="a",
        after_sha256="b",
        checksums_match=False,
        rto_gate_ok=True,
        rpo_gate_ok=True,
        require_rto_sec=9.0,
        require_rpo_sec=0.1,
        dry_run=False,
        details="d",
    )
    t = m.render_md(r)
    assert "FAIL" in t
    assert "Postgres DR" in t


def test_run_drill_missing_tool() -> None:
    m = _load_mod()
    a = REPO / "artifacts" / "drill_ut_missing"
    with (
        patch.object(m, "_check_tools", return_value=["pg_dump"]),
        patch.object(m, "_git_sha", return_value="g"),
    ):
        r = m.run_drill("postgresql://a:b@h:1/d", a, False, None, None)
    assert r.status == "MISSING_TOOL"
    assert "pg_dump" in (r.tool_check or [])


def test_cli_dry_no_dsn(tmp_path: Path) -> None:
    env = {
        k: v
        for k, v in __import__("os").environ.items()
        if "DATABASE" not in k
        and k != "TEST_DATABASE_URL"
    }
    out = tmp_path / "dr.md"
    r = subprocess.run(  # noqa: S603
        [sys.executable, str(TOOL), "--dry-run", "--output-md", str(out), "--artifact-dir", str(tmp_path / "a")],  # noqa: E501
        cwd=REPO,
        capture_output=True,
        text=True,
        env=env,
    )
    # Ohne pg_dump/psql: MISSING_TOOL/Exit 1; mit Tools: DRYRUN_OK/0 — beides produziert den Bericht.
    assert r.returncode in (0, 1)
    assert out.is_file()
    t = out.read_text(encoding="utf-8", errors="replace")
    assert "Status" in t
    assert "DRYRUN_OK" in t or "MISSING_TOOL" in t
