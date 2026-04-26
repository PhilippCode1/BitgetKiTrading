from __future__ import annotations

from shared_py.portfolio_risk_controls import ExposureItem, PortfolioRiskLimits, PortfolioSnapshot, evaluate_portfolio_risk


def test_global_halt_blocks_opening_orders() -> None:
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
    )
    snapshot = PortfolioSnapshot(
        open_positions=[ExposureItem("BTCUSDT", "futures", 4_000.0, 0.01, "long")],
        pending_orders=[],
        pending_live_candidates=[],
        account_equity=10_000.0,
        free_margin=8_000.0,
        used_margin=2_000.0,
        snapshot_fresh=True,
        correlation_stress=0.2,
        unknown_correlation=False,
        owner_limits_present=True,
        global_halt_active=True,
    )
    result = evaluate_portfolio_risk(snapshot, limits)
    assert result.opening_orders_allowed is False
    assert result.risk_state == "global_halt"
