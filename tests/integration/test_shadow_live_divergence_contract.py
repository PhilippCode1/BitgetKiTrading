"""Deterministische Shadow-vs-Live-Divergenz (shared_py) — Gate-Logik ohne laufenden Broker."""

from __future__ import annotations

import time

import pytest

from shared_py.shadow_live_divergence import (
    SHADOW_LIVE_DIVERGENCE_PROTOCOL_VERSION,
    ShadowLiveThresholds,
    assess_shadow_live_divergence,
)


@pytest.mark.integration
def test_divergence_hard_when_shadow_blocked_but_live_candidate() -> None:
    now_ms = int(time.time() * 1000)
    out = assess_shadow_live_divergence(
        shadow_decision=("blocked", "risk"),
        live_decision=("live_candidate_recorded", "ok"),
        signal_payload={"trade_action": "allow_trade"},
        risk_decision={"trade_action": "allow_trade"},
        intent_leverage=10,
        now_ms=now_ms,
        exit_preview=None,
        thresholds=ShadowLiveThresholds(),
    )
    assert out["protocol_version"] == SHADOW_LIVE_DIVERGENCE_PROTOCOL_VERSION
    assert out["match_ok"] is False
    assert "shadow_live_shadow_blocked_live_candidate" in out["hard_violations"]


@pytest.mark.integration
def test_divergence_soft_timing_skew_when_not_hard() -> None:
    now_ms = 1_000_000
    out = assess_shadow_live_divergence(
        shadow_decision=("shadow_recorded", "s"),
        live_decision=("shadow_recorded", "s"),
        signal_payload={
            "trade_action": "allow_trade",
            "analysis_ts_ms": 100,
        },
        risk_decision={"trade_action": "allow_trade"},
        intent_leverage=10,
        now_ms=now_ms,
        exit_preview=None,
        thresholds=ShadowLiveThresholds(
            max_timing_skew_ms=1_000,
            timing_violation_hard=False,
        ),
    )
    assert out["match_ok"] is True
    assert out["soft_violations"]
