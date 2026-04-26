from __future__ import annotations

import json

import scripts.demo_lifecycle_evidence_report as mod


def test_demo_lifecycle_not_counted_as_live_verified(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(mod, "REPORTS", tmp_path)
    (tmp_path / "demo_trading_evidence_DEMO_VERIFIED.json").write_text(
        json.dumps({"result": "DEMO_VERIFIED", "checks": {"private_readonly_result": "PASS"}}),
        encoding="utf-8",
    )
    (tmp_path / "demo_reconcile_evidence_CLOSE_VERIFIED.json").write_text(
        json.dumps({"reconcile_status": "CLOSE_VERIFIED", "checks": {"detected_position_side": "short"}}),
        encoding="utf-8",
    )
    (tmp_path / "demo_reconcile_evidence_CLEAN.json").write_text(
        json.dumps({"reconcile_status": "CLEAN", "checks": {"positions_count": "0"}}),
        encoding="utf-8",
    )
    rep = mod.build_lifecycle_evidence()
    assert rep.lifecycle_status == "DEMO_LIFECYCLE_VERIFIED"
    assert rep.live_verified is False
    assert rep.checks["live_verified"] == "false"
