from __future__ import annotations

from shared_py.health_warnings_display import describe_health_warning


def test_kill_switch_warning_enriched_with_count() -> None:
    ops = {
        "live_broker": {"active_kill_switch_count": 2, "safety_latch_active": False},
    }
    d = describe_health_warning("live_broker_kill_switch_active", ops_summary=ops)
    assert "2" in d["message"]


def test_safety_latch_warning_enriched() -> None:
    ops = {"live_broker": {"active_kill_switch_count": 0, "safety_latch_active": True}}
    d = describe_health_warning("live_broker_safety_latch_active", ops_summary=ops)
    assert "safety_latch" in d["message"].lower()
