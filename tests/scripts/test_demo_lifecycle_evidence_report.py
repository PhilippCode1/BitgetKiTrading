from __future__ import annotations

import json
from pathlib import Path

import scripts.demo_lifecycle_evidence_report as mod


def _write(path, payload) -> None:  # type: ignore[no-untyped-def]
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_lifecycle_detects_full_verified(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(mod, "REPORTS", tmp_path)
    _write(
        tmp_path / "demo_trading_evidence_DEMO_VERIFIED.json",
        {"result": "DEMO_VERIFIED", "checks": {"private_readonly_result": "PASS"}},
    )
    _write(
        tmp_path / "demo_reconcile_evidence_CLOSE_VERIFIED.json",
        {"reconcile_status": "CLOSE_VERIFIED", "checks": {"detected_position_side": "long"}},
    )
    _write(
        tmp_path / "demo_reconcile_evidence_CLEAN.json",
        {"reconcile_status": "CLEAN", "checks": {"positions_count": "0"}},
    )
    rep = mod.build_lifecycle_evidence()
    assert rep.lifecycle_status == "DEMO_LIFECYCLE_VERIFIED"
    assert rep.demo_evidence_stage == "demo_lifecycle_verified"
    assert rep.private_live_allowed is False


def test_lifecycle_not_enough_evidence_when_close_missing(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(mod, "REPORTS", tmp_path)
    _write(
        tmp_path / "demo_trading_evidence_DEMO_VERIFIED.json",
        {"result": "DEMO_VERIFIED", "checks": {"private_readonly_result": "PASS"}},
    )
    _write(
        tmp_path / "demo_reconcile_evidence_CLEAN.json",
        {"reconcile_status": "CLEAN", "checks": {"positions_count": "0"}},
    )
    rep = mod.build_lifecycle_evidence()
    assert rep.lifecycle_status in ("NOT_ENOUGH_EVIDENCE", "DEMO_PARTIAL")
    assert rep.checks["demo_close_verified"] == "false"


def test_lifecycle_not_enough_evidence_when_clean_missing(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(mod, "REPORTS", tmp_path)
    _write(
        tmp_path / "demo_trading_evidence_DEMO_VERIFIED.json",
        {"result": "DEMO_VERIFIED", "checks": {"private_readonly_result": "PASS"}},
    )
    _write(
        tmp_path / "demo_reconcile_evidence_CLOSE_VERIFIED.json",
        {"reconcile_status": "CLOSE_VERIFIED", "checks": {"detected_position_side": "long"}},
    )
    rep = mod.build_lifecycle_evidence()
    assert rep.lifecycle_status in ("NOT_ENOUGH_EVIDENCE", "DEMO_PARTIAL")
    assert rep.checks["final_reconcile_clean"] == "false"


def test_lifecycle_report_contains_no_secret(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(mod, "REPORTS", tmp_path)
    _write(
        tmp_path / "demo_trading_evidence_DEMO_VERIFIED.json",
        {"result": "DEMO_VERIFIED", "checks": {"private_readonly_result": "PASS", "token": "set_redacted"}},
    )
    rep = mod.build_lifecycle_evidence()
    md = mod.to_markdown(rep)
    assert "demo-secret" not in md


def test_lifecycle_verified_when_trading_archive_missing_but_close_and_clean_history_present(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(mod, "REPORTS", tmp_path)
    _write(
        tmp_path / "demo_trading_evidence.json",
        {"result": "DEMO_READY", "checks": {"private_readonly_result": "PASS"}},
    )
    _write(
        tmp_path / "demo_reconcile_evidence_CLOSE_VERIFIED.json",
        {"reconcile_status": "CLOSE_VERIFIED", "checks": {"detected_position_side": "long"}},
    )
    _write(
        tmp_path / "demo_reconcile_evidence_CLEAN.json",
        {
            "reconcile_status": "CLEAN",
            "checks": {
                "positions_count": "0",
                "open_orders_count": "0",
                "order_history_count": "2",
                "live_trading_allowed": "false",
                "private_live_allowed": "false",
            },
        },
    )
    rep = mod.build_lifecycle_evidence()
    assert rep.lifecycle_status == "DEMO_LIFECYCLE_VERIFIED"
    assert rep.private_live_allowed is False
    assert rep.live_verified is False
    assert rep.checks["demo_trading_archive_missing"] == "true"
    assert rep.checks["demo_order_verified_source"] == "inferred_from_close_verified_and_clean_history"


def test_cli_json_output_works(tmp_path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(mod, "REPORTS", tmp_path)
    _write(
        tmp_path / "demo_reconcile_evidence_CLOSE_VERIFIED.json",
        {"reconcile_status": "CLOSE_VERIFIED", "checks": {"detected_position_side": "short"}},
    )
    _write(
        tmp_path / "demo_reconcile_evidence_CLEAN.json",
        {
            "reconcile_status": "CLEAN",
            "checks": {
                "positions_count": "0",
                "open_orders_count": "0",
                "order_history_count": "2",
                "live_trading_allowed": "false",
                "private_live_allowed": "false",
            },
        },
    )
    out_md = tmp_path / "out.md"
    out_json = tmp_path / "out.json"
    rc = mod.main(["--output-md", str(out_md), "--output-json", str(out_json), "--json"])
    captured = capsys.readouterr()
    assert rc == 0
    parsed = json.loads(captured.out)
    assert parsed["lifecycle_status"] == "DEMO_LIFECYCLE_VERIFIED"
    assert Path(out_json).exists()
