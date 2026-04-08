from __future__ import annotations

from shared_py.shadow_live_divergence import (
    ShadowLiveThresholds,
    assess_shadow_live_divergence,
)


def test_assess_match_ok_when_paths_align() -> None:
    th = ShadowLiveThresholds()
    sp = {
        "trade_action": "allow_trade",
        "recommended_leverage": 12,
        "allowed_leverage": 12,
        "shadow_divergence_0_1": 0.05,
        "analysis_ts_ms": 1_000_000,
    }
    rd = {"trade_action": "allow_trade"}
    r = assess_shadow_live_divergence(
        shadow_decision=("shadow_recorded", "validated_shadow_candidate"),
        live_decision=("live_candidate_recorded", "validated_live_candidate"),
        signal_payload=sp,
        risk_decision=rd,
        intent_leverage=12,
        now_ms=1_000_000 + 10_000,
        exit_preview=None,
        thresholds=th,
    )
    assert r["match_ok"] is True
    assert r["hard_violations"] == []


def test_assess_hard_on_shadow_divergence_and_leverage() -> None:
    th = ShadowLiveThresholds(max_signal_shadow_divergence_0_1=0.1, max_leverage_delta=0)
    sp = {
        "trade_action": "allow_trade",
        "recommended_leverage": 10,
        "allowed_leverage": 12,
        "shadow_divergence_0_1": 0.5,
        "analysis_ts_ms": 1_000_000,
    }
    r = assess_shadow_live_divergence(
        shadow_decision=("shadow_recorded", "validated_shadow_candidate"),
        live_decision=("live_candidate_recorded", "validated_live_candidate"),
        signal_payload=sp,
        risk_decision={"trade_action": "allow_trade"},
        intent_leverage=12,
        now_ms=1_000_000 + 10_000,
        exit_preview=None,
        thresholds=th,
    )
    assert r["match_ok"] is False
    assert "signal_shadow_model_divergence_high" in r["hard_violations"]
    assert "leverage_delta_exceeds" in r["hard_violations"]


def test_assess_soft_timing_skew() -> None:
    th = ShadowLiveThresholds(max_timing_skew_ms=1000, timing_violation_hard=False)
    sp = {
        "trade_action": "allow_trade",
        "recommended_leverage": 7,
        "allowed_leverage": 10,
        "analysis_ts_ms": 1,
        "shadow_divergence_0_1": 0.0,
    }
    r = assess_shadow_live_divergence(
        shadow_decision=("shadow_recorded", "validated_shadow_candidate"),
        live_decision=("live_candidate_recorded", "validated_live_candidate"),
        signal_payload=sp,
        risk_decision={"trade_action": "allow_trade"},
        intent_leverage=7,
        now_ms=500_000,
        exit_preview=None,
        thresholds=th,
    )
    assert r["match_ok"] is True
    assert "timing_skew_exceeds_soft" in r["soft_violations"]


def test_assess_hard_shadow_blocked_live_candidate() -> None:
    th = ShadowLiveThresholds()
    r = assess_shadow_live_divergence(
        shadow_decision=("blocked", "shadow_trade_disabled"),
        live_decision=("live_candidate_recorded", "validated_live_candidate"),
        signal_payload={"trade_action": "allow_trade", "recommended_leverage": 7, "allowed_leverage": 10},
        risk_decision={"trade_action": "allow_trade"},
        intent_leverage=7,
        now_ms=1000,
        exit_preview=None,
        thresholds=th,
    )
    assert "shadow_live_shadow_blocked_live_candidate" in r["hard_violations"]
