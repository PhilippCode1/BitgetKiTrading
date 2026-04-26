from __future__ import annotations

from shared_py.risk_engine import TradeRiskLimits, evaluate_trade_risk


def test_risk_timeout_or_missing_response_blocks_live() -> None:
    limits = TradeRiskLimits(
        min_signal_strength=50,
        min_probability=0.5,
        min_risk_score=40,
        min_expected_return_bps=5.0,
        max_expected_mae_bps=100.0,
        min_projected_rr=0.5,
        min_allowed_leverage=7,
        max_position_risk_pct=0.02,
        max_account_margin_usage=0.5,
        max_account_drawdown_pct=0.3,
        max_daily_drawdown_pct=0.2,
        max_weekly_drawdown_pct=0.25,
        max_daily_loss_usdt=1000.0,
        max_position_notional_usdt=20_000.0,
        max_concurrent_positions=5,
    )
    out = evaluate_trade_risk(
        signal={"trade_action": "do_not_trade", "rejection_reasons_json": ["risk_timeout"]},
        limits=limits,
    )
    assert out["trade_action"] == "do_not_trade"
