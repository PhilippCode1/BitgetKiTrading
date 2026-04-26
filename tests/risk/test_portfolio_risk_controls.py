from __future__ import annotations

from shared_py.portfolio_risk_controls import (
    ExposureItem,
    PortfolioRiskLimits,
    PortfolioSnapshot,
    evaluate_portfolio_risk,
)


def _limits() -> PortfolioRiskLimits:
    return PortfolioRiskLimits(
        max_total_notional=20_000.0,
        max_margin_usage=0.4,
        max_largest_position_risk=0.03,
        max_concurrent_positions=3,
        max_pending_orders=2,
        max_pending_live_candidates=1,
        max_net_directional_exposure=15_000.0,
        max_correlation_stress=0.75,
        max_funding_concentration=0.03,
        max_family_exposure=16_000.0,
        max_total_leverage_exposure=3.0,
        max_asset_exposure=12_000.0,
        max_correlation_group_exposure=14_000.0,
        max_daily_loss=400.0,
        max_weekly_loss=1_000.0,
        max_intraday_drawdown=0.08,
        max_total_drawdown=0.18,
        max_consecutive_losses=4,
        owner_limits_required_for_private_live=True,
    )


def test_portfolio_limit_breach_blocks_opening_orders() -> None:
    snapshot = PortfolioSnapshot(
        open_positions=[ExposureItem("BTCUSDT", "futures", 12_000.0, 0.02, "long")],
        pending_orders=[ExposureItem("ETHUSDT", "futures", 12_000.0, 0.02, "long")],
        pending_live_candidates=[],
        account_equity=10_000.0,
        used_margin=6_000.0,
        snapshot_fresh=True,
        correlation_stress=0.8,
        unknown_correlation=False,
        free_margin=4_000.0,
        total_leverage_exposure=4.0,
        daily_realized_pnl=-300.0,
        daily_unrealized_pnl=-200.0,
        weekly_pnl=-1200.0,
        current_drawdown=0.09,
        max_drawdown=0.2,
        current_loss_streak=5,
        owner_limits_present=False,
    )
    result = evaluate_portfolio_risk(snapshot, _limits())
    assert result.allows_next_gate_only is False
    assert len(result.block_reasons) > 0
    assert result.opening_orders_allowed is False
    assert result.risk_state in {"unknown_blocked", "degraded", "reduce_only", "halt_new_entries"}
