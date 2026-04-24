from __future__ import annotations

import json
import os

import pytest

from shared_py.resilience.survival_kernel import (
    RISK_VOLATILITY_CLAMP_ACTIVE,
    SurvivalKernelParams,
    SurvivalMetrics,
    adaptive_leverage_cap_from_atr_percent,
    apply_survival_signal_overrides,
    disruption_score,
    effective_atr_percent_for_volatility_clamp,
    merge_survival_truth,
    process_survival_metrics,
    survival_tick,
)


def test_disruption_extreme_triggers_survival_immediately() -> None:
    m = SurvivalMetrics(drift_z=9.0, tsfm_residual_z=2.0, ams_toxicity_0_1=0.2)
    tr = survival_tick(False, 0, m, SurvivalKernelParams())
    assert tr.score >= 6.0
    assert tr.in_survival is True
    assert tr.enter_event is True
    assert tr.execution_lock is True


def test_hysteresis_safe_exit() -> None:
    p = SurvivalKernelParams()
    m_low = SurvivalMetrics(drift_z=0.5, tsfm_residual_z=0.5, ams_toxicity_0_1=0.02)
    ins = True
    c = 0
    exited = False
    for _ in range(20):
        tr = survival_tick(ins, c, m_low, p)
        ins = tr.in_survival
        c = tr.consec_low_score_ticks
        if tr.exit_event:
            exited = True
            break
    assert exited is True
    assert ins is False


def test_apply_survival_signal_overrides_1x() -> None:
    sp = {"allowed_leverage": 25, "recommended_leverage": 20, "leverage_cap_reasons_json": ["x"]}
    out = apply_survival_signal_overrides(sp)
    assert out["allowed_leverage"] == 1
    assert out["recommended_leverage"] == 1
    assert out["execution_leverage_cap"] == 1
    assert "survival_mode_portfolio_governor_1x" in (out.get("leverage_cap_reasons_json") or [])


def test_merge_survival_truth_env_forced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BITGET_SURVIVAL_MODE", "1")
    merged = merge_survival_truth({"truth_channel_ok": True}, redis=None)
    assert merged["survival_mode_active"] is True
    assert merged["survival_execution_lock"] is True
    monkeypatch.delenv("BITGET_SURVIVAL_MODE", raising=False)


def test_process_survival_metrics_with_fake_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    store: dict[str, str] = {}

    class _FakeRedis:
        def get(self, key: str) -> str | None:
            return store.get(key)

        def set(self, key: str, value: str) -> None:
            store[key] = value

    r = _FakeRedis()
    m = SurvivalMetrics(drift_z=10.0, tsfm_residual_z=0.0, ams_toxicity_0_1=0.0)
    tr = process_survival_metrics(metrics=m, redis=r, params=SurvivalKernelParams())
    assert tr.enter_event is True
    raw = store.get("ops:survival_kernel:v1")
    assert raw is not None
    st = json.loads(raw)
    assert st["active"] is True


def test_disruption_score_matches_expected() -> None:
    m = SurvivalMetrics(drift_z=2.0, tsfm_residual_z=1.0, ams_toxicity_0_1=0.5)
    assert abs(disruption_score(m) - 5.0) < 1e-9


def test_adaptive_leverage_cap_atr_matrix_prompt_73() -> None:
    """
    DoD: ATR 0,5 % -> roher Cap 20 (min mit Live-Ramp 7), 2 % -> 5, 5 % -> 2.
    Formel: min(SYSTEM_MAX, floor(1/((p/100)*10))).
    """
    assert adaptive_leverage_cap_from_atr_percent(0.5, system_max_leverage=75) == 20
    assert adaptive_leverage_cap_from_atr_percent(2.0, system_max_leverage=75) == 5
    assert adaptive_leverage_cap_from_atr_percent(5.0, system_max_leverage=75) == 2
    # Nach typischer 7x-Ramp: min(7, roh)
    assert min(7, adaptive_leverage_cap_from_atr_percent(0.5, system_max_leverage=75)) == 7
    assert min(7, adaptive_leverage_cap_from_atr_percent(2.0, system_max_leverage=75)) == 5
    assert min(7, adaptive_leverage_cap_from_atr_percent(5.0, system_max_leverage=75)) == 2


def test_risk_volatility_clamp_bff_token() -> None:
    assert RISK_VOLATILITY_CLAMP_ACTIVE == "RISK_VOLATILITY_CLAMP_ACTIVE"


def test_effective_atr_stress_above_ema() -> None:
    # ATR 2 %, EMA 1 % -> Faktor 2, eff 4 %
    e = effective_atr_percent_for_volatility_clamp(atr_percent=2.0, atr_ema_24h_percent=1.0)
    assert abs(e - 4.0) < 1e-9
    assert (
        effective_atr_percent_for_volatility_clamp(atr_percent=1.0, atr_ema_24h_percent=2.0) == 1.0
    )
