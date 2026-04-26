from __future__ import annotations

from scripts.final_go_no_go_report import build_payload


def test_full_autonomous_live_requires_long_real_history() -> None:
    payload = build_payload()
    assert payload["mode_decisions"]["full_autonomous_live"] == "NO"
    assert payload["full_autonomous_live_score"] <= 2
