from __future__ import annotations

from shared_py.portfolio_risk_controls import ExposureItem, PortfolioRiskLimits, PortfolioSnapshot, evaluate_portfolio_risk


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
        max_asset_exposure=12_000.0,
        max_total_leverage_exposure=3.0,
        max_correlation_group_exposure=13_000.0,
        max_daily_loss=400.0,
        max_weekly_loss=1_000.0,
        max_intraday_drawdown=0.08,
        max_total_drawdown=0.18,
        max_consecutive_losses=4,
    )


def _base_snapshot() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        open_positions=[ExposureItem("BTCUSDT", "futures", 10_000.0, 0.02, "long")],
        pending_orders=[],
        pending_live_candidates=[],
        account_equity=10_000.0,
        free_margin=7_000.0,
        used_margin=3_000.0,
        snapshot_fresh=True,
        correlation_stress=0.4,
        unknown_correlation=False,
        total_leverage_exposure=2.0,
        exposure_by_asset={"BTCUSDT": 10_000.0},
        exposure_by_market_family={"futures": 10_000.0},
        exposure_by_correlation_group={"majors": 10_000.0},
        owner_limits_present=True,
    )


def test_daily_loss_weekly_loss_drawdown_and_exposure_block_opening() -> None:
    base = _base_snapshot()
    daily = PortfolioSnapshot(**{**base.__dict__, "daily_realized_pnl": -500.0})
    weekly = PortfolioSnapshot(**{**base.__dict__, "weekly_pnl": -2000.0})
    drawdown = PortfolioSnapshot(**{**base.__dict__, "current_drawdown": 0.11})
    exposure = PortfolioSnapshot(**{**base.__dict__, "total_leverage_exposure": 4.2})
    for snapshot in (daily, weekly, drawdown, exposure):
        result = evaluate_portfolio_risk(snapshot, _limits())
        assert result.opening_orders_allowed is False
        assert result.block_reasons
