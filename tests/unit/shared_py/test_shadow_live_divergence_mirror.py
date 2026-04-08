"""Unit-Evidenz: Shadow→Live-Spiegel (assess_shadow_live_divergence), deterministisch."""

from __future__ import annotations

import pytest

from shared_py.shadow_live_divergence import (
    ShadowLiveThresholds,
    SHADOW_LIVE_DIVERGENCE_PROTOCOL_VERSION,
    assess_shadow_live_divergence,
)


def _base_signal(**overrides: object) -> dict:
    base = {
        "trade_action": "allow_trade",
        "analysis_ts_ms": 1_700_000_000_000,
        "recommended_leverage": 5,
        "allowed_leverage": 10,
        "shadow_divergence_0_1": 0.05,
    }
    base.update(overrides)
    return base


def _base_risk(**overrides: object) -> dict:
    r = {"trade_action": "allow_trade"}
    r.update(overrides)
    return r


def test_match_ok_when_paths_and_dimensions_align() -> None:
    out = assess_shadow_live_divergence(
        shadow_decision=("live_candidate_recorded", "ok"),
        live_decision=("live_candidate_recorded", "ok"),
        signal_payload=_base_signal(),
        risk_decision=_base_risk(),
        intent_leverage=5,
        now_ms=1_700_000_000_000,
        exit_preview=None,
        thresholds=ShadowLiveThresholds(),
    )
    assert out["protocol_version"] == SHADOW_LIVE_DIVERGENCE_PROTOCOL_VERSION
    assert out["match_ok"] is True
    assert out["hard_violations"] == []
    assert out["soft_violations"] == []


def test_hard_shadow_blocked_but_live_candidate() -> None:
    out = assess_shadow_live_divergence(
        shadow_decision=("blocked", "risk"),
        live_decision=("live_candidate_recorded", "x"),
        signal_payload=_base_signal(),
        risk_decision=_base_risk(),
        intent_leverage=5,
        now_ms=1_700_000_000_000,
        exit_preview=None,
        thresholds=ShadowLiveThresholds(),
    )
    assert out["match_ok"] is False
    assert "shadow_live_shadow_blocked_live_candidate" in out["hard_violations"]


def test_hard_signal_risk_trade_action_mismatch() -> None:
    out = assess_shadow_live_divergence(
        shadow_decision=("blocked", "x"),
        live_decision=("blocked", "y"),
        signal_payload=_base_signal(trade_action="allow_trade"),
        risk_decision=_base_risk(trade_action="no_trade"),
        intent_leverage=5,
        now_ms=1_700_000_000_000,
        exit_preview=None,
        thresholds=ShadowLiveThresholds(),
    )
    assert "signal_risk_trade_action_mismatch" in out["hard_violations"]


def test_hard_intent_leverage_exceeds_allowed() -> None:
    out = assess_shadow_live_divergence(
        shadow_decision=("blocked", "x"),
        live_decision=("blocked", "y"),
        signal_payload=_base_signal(allowed_leverage=3),
        risk_decision=_base_risk(),
        intent_leverage=8,
        now_ms=1_700_000_000_000,
        exit_preview=None,
        thresholds=ShadowLiveThresholds(),
    )
    assert "intent_leverage_exceeds_signal_allowed" in out["hard_violations"]


def test_hard_leverage_delta_exceeds_threshold() -> None:
    out = assess_shadow_live_divergence(
        shadow_decision=("blocked", "x"),
        live_decision=("blocked", "y"),
        signal_payload=_base_signal(recommended_leverage=1),
        risk_decision=_base_risk(),
        intent_leverage=5,
        now_ms=1_700_000_000_000,
        exit_preview=None,
        thresholds=ShadowLiveThresholds(max_leverage_delta=2),
    )
    assert "leverage_delta_exceeds" in out["hard_violations"]


def test_hard_shadow_model_divergence_high() -> None:
    out = assess_shadow_live_divergence(
        shadow_decision=("blocked", "x"),
        live_decision=("blocked", "y"),
        signal_payload=_base_signal(shadow_divergence_0_1=0.5),
        risk_decision=_base_risk(),
        intent_leverage=5,
        now_ms=1_700_000_000_000,
        exit_preview=None,
        thresholds=ShadowLiveThresholds(max_signal_shadow_divergence_0_1=0.2),
    )
    assert "signal_shadow_model_divergence_high" in out["hard_violations"]


@pytest.mark.parametrize(
    ("timing_hard", "expect_hard", "expect_soft"),
    [
        (False, False, True),
        (True, True, False),
    ],
)
def test_timing_skew_soft_vs_hard(
    timing_hard: bool, expect_hard: bool, expect_soft: bool
) -> None:
    th = ShadowLiveThresholds(
        max_timing_skew_ms=60_000, timing_violation_hard=timing_hard
    )
    out = assess_shadow_live_divergence(
        shadow_decision=("blocked", "x"),
        live_decision=("blocked", "y"),
        signal_payload=_base_signal(analysis_ts_ms=1_700_000_000_000),
        risk_decision=_base_risk(),
        intent_leverage=5,
        now_ms=1_700_000_000_000 + 120_000,
        exit_preview=None,
        thresholds=th,
    )
    assert ("timing_skew_exceeds_hard" in out["hard_violations"]) is expect_hard
    assert ("timing_skew_exceeds_soft" in out["soft_violations"]) is expect_soft


def test_slippage_from_signal_payload_and_hard_cap() -> None:
    out = assess_shadow_live_divergence(
        shadow_decision=("blocked", "x"),
        live_decision=("blocked", "y"),
        signal_payload=_base_signal(slippage_bps_entry=99.0),
        risk_decision=_base_risk(),
        intent_leverage=5,
        now_ms=1_700_000_000_000,
        exit_preview=None,
        thresholds=ShadowLiveThresholds(max_slippage_expectation_bps=10.0),
    )
    assert out["dimensions"]["estimated_slippage_bps"] == 99.0
    assert "slippage_expectation_exceeds_cap" in out["hard_violations"]


def test_slippage_from_exit_preview_stop_plan() -> None:
    preview = {
        "stop_plan": {
            "execution": {"estimated_slippage_bps": 12.5},
        }
    }
    out = assess_shadow_live_divergence(
        shadow_decision=("blocked", "x"),
        live_decision=("blocked", "y"),
        signal_payload=_base_signal(),
        risk_decision=_base_risk(),
        intent_leverage=5,
        now_ms=1_700_000_000_000,
        exit_preview=preview,
        thresholds=ShadowLiveThresholds(max_slippage_expectation_bps=10.0),
    )
    assert out["dimensions"]["estimated_slippage_bps"] == 12.5
    assert "slippage_expectation_exceeds_cap" in out["hard_violations"]
