from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED_SRC = ROOT / "shared" / "python" / "src"
if SHARED_SRC.is_dir() and str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from shared_py.meta_trade_decision import (
    MetaTradeThresholds,
    resolve_meta_trade_lane,
    shrink_calibrated_take_trade_probability,
    validate_meta_trade_lane,
)


def test_shrink_pulls_extremes_toward_half_on_ood_and_uncertainty() -> None:
    p, reasons = shrink_calibrated_take_trade_probability(
        0.9,
        ood_score_0_1=0.5,
        ood_alert=False,
        model_uncertainty_0_1=0.5,
        ood_shrink_factor=0.5,
        uncertainty_shrink_weight=0.4,
    )
    assert p is not None
    assert p < 0.9
    assert p > 0.5
    assert "meta_prob_shrink_ood_score" in reasons
    assert "meta_prob_shrink_uncertainty" in reasons


def test_shrink_returns_none_when_prob_missing() -> None:
    assert shrink_calibrated_take_trade_probability(
        None,
        ood_score_0_1=None,
        ood_alert=False,
        model_uncertainty_0_1=None,
    ) == (None, [])


def test_lane_do_not_trade_when_hybrid_blocked() -> None:
    th = MetaTradeThresholds(hybrid_min_take_trade_prob=0.58)
    lane, reasons = resolve_meta_trade_lane(
        hybrid_would_allow=False,
        safety_or_model_blocked=False,
        take_trade_prob_adjusted=0.8,
        market_regime="trend",
        model_ood_alert=False,
        model_ood_score_0_1=None,
        model_uncertainty_0_1=0.1,
        risk_score_0_100=60.0,
        structure_score_0_100=70.0,
        history_score_0_100=60.0,
        source_snapshot_json={"quality_gate": {"passed": True}},
        thresholds=th,
    )
    assert lane == "do_not_trade"
    assert "meta_lane_hybrid_blocked" in reasons


def test_lane_shadow_on_stress_regime() -> None:
    th = MetaTradeThresholds(hybrid_min_take_trade_prob=0.58)
    lane, reasons = resolve_meta_trade_lane(
        hybrid_would_allow=True,
        safety_or_model_blocked=False,
        take_trade_prob_adjusted=0.85,
        market_regime="shock",
        model_ood_alert=False,
        model_ood_score_0_1=None,
        model_uncertainty_0_1=0.1,
        risk_score_0_100=70.0,
        structure_score_0_100=70.0,
        history_score_0_100=70.0,
        source_snapshot_json={"quality_gate": {"passed": True}},
        thresholds=th,
    )
    assert lane == "shadow_only"
    assert "meta_lane_shadow_stress_regime" in reasons


def test_lane_paper_on_low_risk_score() -> None:
    th = MetaTradeThresholds(hybrid_min_take_trade_prob=0.58)
    lane, reasons = resolve_meta_trade_lane(
        hybrid_would_allow=True,
        safety_or_model_blocked=False,
        take_trade_prob_adjusted=0.85,
        market_regime="trend",
        model_ood_alert=False,
        model_ood_score_0_1=None,
        model_uncertainty_0_1=0.1,
        risk_score_0_100=40.0,
        structure_score_0_100=70.0,
        history_score_0_100=70.0,
        source_snapshot_json={"quality_gate": {"passed": True}},
        thresholds=th,
    )
    assert lane == "paper_only"
    assert "meta_lane_paper_risk_score" in reasons


def test_lane_live_candidate_when_clean() -> None:
    th = MetaTradeThresholds(hybrid_min_take_trade_prob=0.58)
    lane, reasons = resolve_meta_trade_lane(
        hybrid_would_allow=True,
        safety_or_model_blocked=False,
        take_trade_prob_adjusted=0.72,
        market_regime="trend",
        model_ood_alert=False,
        model_ood_score_0_1=None,
        model_uncertainty_0_1=0.2,
        risk_score_0_100=60.0,
        structure_score_0_100=70.0,
        history_score_0_100=60.0,
        source_snapshot_json={"quality_gate": {"passed": True}},
        thresholds=th,
    )
    assert lane == "candidate_for_live"
    assert "meta_lane_live_candidate_clean" in reasons


def test_validate_meta_trade_lane() -> None:
    assert validate_meta_trade_lane(None) == "valid"
    assert validate_meta_trade_lane("paper_only") == "valid"
    assert validate_meta_trade_lane("invalid_lane") == "invalid"
