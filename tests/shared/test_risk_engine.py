from __future__ import annotations

from shared_py.risk_engine import (
    TradeRiskLimits,
    compute_drawdown_from_points,
    compute_margin_usage_pct,
    compute_position_risk_pct,
    compute_total_equity,
    evaluate_trade_risk,
)


def _limits() -> TradeRiskLimits:
    return TradeRiskLimits(
        min_signal_strength=65,
        min_probability=0.65,
        min_risk_score=60,
        min_expected_return_bps=5.0,
        max_expected_mae_bps=120.0,
        min_projected_rr=1.15,
        min_allowed_leverage=7,
        max_position_risk_pct=0.02,
        max_account_margin_usage=0.35,
        max_account_drawdown_pct=0.10,
        max_daily_drawdown_pct=0.04,
        max_weekly_drawdown_pct=0.08,
        max_daily_loss_usdt=1000.0,
        max_position_notional_usdt=5000.0,
        max_concurrent_positions=1,
    )


def test_evaluate_trade_risk_allows_clean_candidate() -> None:
    decision = evaluate_trade_risk(
        signal={
            "trade_action": "allow_trade",
            "decision_state": "accepted",
            "rejection_state": False,
            "signal_strength_0_100": 82,
            "take_trade_prob": 0.72,
            "risk_score_0_100": 76,
            "expected_return_bps": 18.0,
            "expected_mae_bps": 20.0,
            "expected_mfe_bps": 34.0,
            "market_regime": "trend",
            "quality_gate": {"passed": True},
            "allowed_leverage": 12,
            "recommended_leverage": 9,
        },
        limits=_limits(),
        open_positions_count=0,
        position_notional_usdt="1800",
        position_risk_pct=0.006,
        projected_margin_usage_pct=0.18,
        account_drawdown_pct=0.01,
        daily_drawdown_pct=0.0,
        weekly_drawdown_pct=0.0,
        daily_loss_usdt="0",
    )
    assert decision["trade_action"] == "allow_trade"
    assert decision["reasons_json"] == []


def test_evaluate_trade_risk_blocks_on_model_ood_alert_abstention_only() -> None:
    decision = evaluate_trade_risk(
        signal={
            "trade_action": "allow_trade",
            "decision_state": "accepted",
            "rejection_state": False,
            "signal_strength_0_100": 82,
            "take_trade_prob": 0.72,
            "risk_score_0_100": 76,
            "expected_return_bps": 18.0,
            "expected_mae_bps": 20.0,
            "expected_mfe_bps": 34.0,
            "market_regime": "trend",
            "quality_gate": {"passed": True},
            "allowed_leverage": 12,
            "recommended_leverage": 10,
            "abstention_reasons_json": ["model_ood_alert"],
        },
        limits=_limits(),
        open_positions_count=0,
        position_notional_usdt="100",
        position_risk_pct=0.001,
        projected_margin_usage_pct=0.1,
        account_drawdown_pct=0.0,
        daily_drawdown_pct=0.0,
        weekly_drawdown_pct=0.0,
        daily_loss_usdt="0",
    )
    assert decision["trade_action"] == "do_not_trade"
    assert "model_ood_alert" in decision["reasons_json"]


def test_evaluate_trade_risk_blocks_signal_market_and_leverage_failures() -> None:
    decision = evaluate_trade_risk(
        signal={
            "trade_action": "do_not_trade",
            "decision_state": "downgraded",
            "rejection_state": True,
            "signal_strength_0_100": 82,
            "take_trade_prob": 0.72,
            "risk_score_0_100": 76,
            "expected_return_bps": 18.0,
            "expected_mae_bps": 20.0,
            "expected_mfe_bps": 34.0,
            "market_regime": "shock",
            "quality_gate": {"passed": False},
            "rejection_reasons_json": ["stale_feature_data", "spread_too_wide"],
            "abstention_reasons_json": ["uncertainty_above_threshold"],
            "allowed_leverage": 6,
            "recommended_leverage": None,
        },
        limits=_limits(),
        leverage_cap_reasons_json=["hybrid_allowed_leverage_below_minimum"],
        operational_staleness_reasons=["live_snapshot_positions_stale"],
    )
    assert decision["trade_action"] == "do_not_trade"
    assert "trade_action_do_not_trade" in decision["reasons_json"]
    assert "not_accepted" in decision["reasons_json"]
    assert "rejection_active" in decision["reasons_json"]
    assert "stale_feature_data" in decision["reasons_json"]
    assert "market_regime_shock" in decision["reasons_json"]
    assert "spread_too_wide" in decision["reasons_json"]
    assert "uncertainty_above_threshold" in decision["reasons_json"]
    assert "allowed_leverage_below_minimum" in decision["reasons_json"]
    assert "live_snapshot_positions_stale" in decision["reasons_json"]


def test_evaluate_trade_risk_blocks_account_and_position_limits() -> None:
    decision = evaluate_trade_risk(
        signal={
            "trade_action": "allow_trade",
            "decision_state": "accepted",
            "rejection_state": False,
            "signal_strength_0_100": 82,
            "take_trade_prob": 0.72,
            "risk_score_0_100": 76,
            "expected_return_bps": 18.0,
            "expected_mae_bps": 20.0,
            "expected_mfe_bps": 34.0,
            "market_regime": "trend",
            "quality_gate": {"passed": True},
            "allowed_leverage": 12,
            "recommended_leverage": 9,
        },
        limits=_limits(),
        open_positions_count=1,
        position_notional_usdt="6000",
        position_risk_pct=0.03,
        projected_margin_usage_pct=0.40,
        account_drawdown_pct=0.11,
        daily_drawdown_pct=0.05,
        weekly_drawdown_pct=0.09,
        daily_loss_usdt="1200",
    )
    assert decision["trade_action"] == "do_not_trade"
    assert "max_concurrent_positions_exceeded" in decision["reasons_json"]
    assert "position_notional_limit_exceeded" in decision["reasons_json"]
    assert "position_risk_limit_exceeded" in decision["reasons_json"]
    assert "account_margin_usage_limit_exceeded" in decision["reasons_json"]
    assert "account_drawdown_limit_exceeded" in decision["reasons_json"]
    assert "daily_drawdown_limit_exceeded" in decision["reasons_json"]
    assert "weekly_drawdown_limit_exceeded" in decision["reasons_json"]
    assert "daily_loss_limit_exceeded" in decision["reasons_json"]


def test_risk_engine_helpers_compute_consistent_metrics() -> None:
    total_equity = compute_total_equity(available_equity="9700", used_margin="300")
    margin_usage_pct = compute_margin_usage_pct(
        total_equity=total_equity, used_margin="300"
    )
    position_risk_pct = compute_position_risk_pct(
        entry_price="100000",
        stop_price="99500",
        qty_base="0.02",
        account_equity=total_equity,
        fee_buffer_usdt="2",
    )
    drawdown = compute_drawdown_from_points(
        current_equity=total_equity,
        equity_points=["9800", "10150", "10000"],
    )

    assert str(total_equity) == "10000"
    assert margin_usage_pct == 0.03
    assert position_risk_pct == 0.0012
    assert drawdown["peak_equity"] == "10150"
    assert drawdown["drawdown_pct"] == 0.014778
    assert drawdown["loss_usdt"] == "150"
