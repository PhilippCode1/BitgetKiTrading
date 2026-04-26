from __future__ import annotations

import json

import scripts.demo_lifecycle_evidence_report as mod


def test_demo_lifecycle_never_enables_live(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(mod, "REPORTS", tmp_path)
    (tmp_path / "demo_trading_evidence_DEMO_VERIFIED.json").write_text(
        json.dumps({"result": "DEMO_VERIFIED", "checks": {"private_readonly_result": "PASS"}}),
        encoding="utf-8",
    )
    (tmp_path / "demo_reconcile_evidence_CLOSE_VERIFIED.json").write_text(
        json.dumps({"reconcile_status": "CLOSE_VERIFIED", "checks": {"detected_position_side": "long"}}),
        encoding="utf-8",
    )
    (tmp_path / "demo_reconcile_evidence_CLEAN.json").write_text(
        json.dumps({"reconcile_status": "CLEAN", "checks": {"positions_count": "0"}}),
        encoding="utf-8",
    )
    rep = mod.build_lifecycle_evidence()
    assert rep.demo_evidence_stage == "demo_lifecycle_verified"
    assert rep.live_trading_allowed is False
    assert rep.private_live_allowed is False
    assert rep.full_autonomous_live is False
