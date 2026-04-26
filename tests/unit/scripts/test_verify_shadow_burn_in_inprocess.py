from __future__ import annotations

import importlib.util
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]


def _load():
    p = REPO / "scripts" / "verify_shadow_burn_in.py"
    n = f"v_sbu_{uuid.uuid4().hex[:8]}"
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s)
    assert s and s.loader
    s.loader.exec_module(m)  # type: ignore[union-attr]
    return m


def test_verdict_pass() -> None:
    m = _load()
    r: list[tuple[str, bool, str, Any]] = [
        ("a", True, "ok", {}),
        ("b", True, "x", None),
    ]
    assert m._verdict_from_results(r) == "PASS"


def test_verdict_no_evidence_wins() -> None:
    m = _load()
    r: list[tuple[str, bool, str, Any]] = [
        ("a", True, "ok", {}),
        ("b", False, "NO_EVIDENCE: fehlt Tabelle", {}),
    ]
    assert m._verdict_from_results(r) == "NO_EVIDENCE"


def test_verdict_fail() -> None:
    m = _load()
    r: list[tuple[str, bool, str, Any]] = [
        ("a", True, "ok", {}),
        ("b", False, "reconcile bricht", {}),
    ]
    assert m._verdict_from_results(r) == "FAIL"


def test_reconcile_too_much_fail_fixture() -> None:
    m = _load()
    since = datetime(2024, 1, 1, tzinfo=UTC)
    until = since + timedelta(hours=72)

    class R:
        def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
            self._rows = rows

        def fetchall(self) -> list[dict[str, Any]] | None:
            return self._rows

    class Conn:
        def __init__(self) -> None:
            self.got_group = False

        def execute(self, _q: str, _p: object | None = None) -> R:  # noqa: ANN201
            self.got_group = "GROUP BY status" in _q
            if self.got_group:
                return R(
                    [
                        {"status": "fail", "c": 90},
                        {"status": "ok", "c": 10},
                    ]
                )
            return R([])

    c = Conn()
    with patch.object(m, "_safe_table", return_value=True):
        ok, msg, _ex = m._check_reconcile_not_chronic_fail(c, since, until, True, 0.2)
    assert ok is False
    assert "Reconcile" in msg


def test_reconcile_no_rows_strict_missing_data_fixture() -> None:
    m = _load()
    since = datetime(2024, 1, 1, tzinfo=UTC)
    until = since + timedelta(hours=1)

    class R:
        def fetchall(self) -> list[dict[str, Any]]:
            return []

    class Conn:
        def execute(self, _q: str, _p: object | None = None) -> R:
            return R()

    with patch.object(m, "_safe_table", return_value=True):
        ok, msg, _ = m._check_reconcile_not_chronic_fail(
            Conn(), since, until, True, 0.2
        )
    assert ok is False
    assert "NO_EVIDENCE" in msg


def test_window_coverage_fail_short_runtime_fixture() -> None:
    m = _load()
    since = datetime(2024, 1, 1, tzinfo=UTC)
    until = since + timedelta(hours=72)

    class R:
        def fetchone(self) -> dict[str, Any]:
            return {
                "n": 30,
                "tmin": since + timedelta(hours=60),
                "tmax": since + timedelta(hours=62),
            }

    class Conn:
        def execute(self, _q: str, _p: object | None = None) -> R:
            return R()

    with patch.object(m, "_safe_table", return_value=True):
        ok, msg, ex = m._check_time_and_decision_volume(
            Conn(), since, until, True, 3, 0.95
        )
    assert ok is False
    assert "NO_EVIDENCE" in msg
    assert ex["decisions_in_window"] == 30


def test_window_coverage_pass_72h_fixture() -> None:
    m = _load()
    since = datetime(2024, 1, 1, tzinfo=UTC)
    until = since + timedelta(hours=72)

    class R:
        def fetchone(self) -> dict[str, Any]:
            return {
                "n": 120,
                "tmin": since + timedelta(minutes=10),
                "tmax": until - timedelta(minutes=5),
            }

    class Conn:
        def execute(self, _q: str, _p: object | None = None) -> R:
            return R()

    with patch.object(m, "_safe_table", return_value=True):
        ok, msg, ex = m._check_time_and_decision_volume(
            Conn(), since, until, True, 10, 0.95
        )
    assert ok is True
    assert "Entscheidungs-Flow" in msg
    assert ex["decisions_in_window"] == 120


def test_operator_release_gates_missing_fields_strict() -> None:
    m = _load()
    since = datetime(2024, 1, 1, tzinfo=UTC)
    until = since + timedelta(hours=72)

    class R:
        def fetchone(self) -> dict[str, Any]:
            return {"details_json": {"execution_controls": {"require_shadow_match_before_live": True}}}

    class Conn:
        def execute(self, _q: str, _p: object | None = None) -> R:
            return R()

    with patch.object(m, "_safe_table", return_value=True):
        ok, msg, ex = m._check_operator_release_gates_enabled(Conn(), since, until, True)
    assert ok is False
    assert "NO_EVIDENCE" in msg
    assert ex["require_shadow_match_before_live"] is True


def test_operator_release_gates_all_true_pass() -> None:
    m = _load()
    since = datetime(2024, 1, 1, tzinfo=UTC)
    until = since + timedelta(hours=72)

    class R:
        def fetchone(self) -> dict[str, Any]:
            return {
                "details_json": {
                    "execution_controls": {
                        "live_require_execution_binding": True,
                        "live_require_operator_release_for_live_open": True,
                        "require_shadow_match_before_live": True,
                    }
                }
            }

    class Conn:
        def execute(self, _q: str, _p: object | None = None) -> R:
            return R()

    with patch.object(m, "_safe_table", return_value=True):
        ok, msg, _ = m._check_operator_release_gates_enabled(Conn(), since, until, True)
    assert ok is True
    assert "Gates sind aktiv" in msg


def test_read_env_dsn(tmp_path: Path) -> None:
    m = _load()
    p = tmp_path / "e"
    p.write_text("DATABASE_URL=postgresql://u:pw@h:1/dbname\n", encoding="utf-8")
    d = m._read_env_dsn(p, "DATABASE_URL")
    assert d and "h:1" in d and "dbname" in d
