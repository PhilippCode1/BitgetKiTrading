from __future__ import annotations

from shared_py.portfolio_risk_controls import (
    ExposureItem,
    PortfolioRiskLimits,
    PortfolioSnapshot,
    evaluate_portfolio_risk,
    reduce_only_reduces_risk,
)


def test_reduce_only_allowed_after_loss_limit_breach() -> None:
    limits = PortfolioRiskLimits(
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
        max_daily_loss=400.0,
    )
    snapshot = PortfolioSnapshot(
        open_positions=[ExposureItem("BTCUSDT", "futures", 8_000.0, 0.01, "long")],
        pending_orders=[],
        pending_live_candidates=[],
        account_equity=10_000.0,
        free_margin=5_000.0,
        used_margin=5_000.0,
        snapshot_fresh=True,
        correlation_stress=0.2,
        unknown_correlation=False,
        owner_limits_present=True,
        daily_realized_pnl=-500.0,
    )
    result = evaluate_portfolio_risk(snapshot, limits)
    assert result.opening_orders_allowed is False
    assert result.reduce_only_allowed is True


def test_reduce_only_must_not_increase_risk() -> None:
    assert reduce_only_reduces_risk(
        current_position_notional=10_000.0,
        order_notional=5_000.0,
        side="short",
        position_side="long",
    )
    assert not reduce_only_reduces_risk(
        current_position_notional=10_000.0,
        order_notional=12_000.0,
        side="short",
        position_side="long",
    )
    assert not reduce_only_reduces_risk(
        current_position_notional=10_000.0,
        order_notional=5_000.0,
        side="long",
        position_side="long",
    )
