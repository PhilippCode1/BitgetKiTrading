from __future__ import annotations

from shared_py.portfolio_risk_controls import ExposureItem, PortfolioRiskLimits, PortfolioSnapshot, evaluate_portfolio_risk


def test_owner_limits_missing_blocks_private_live_opening() -> None:
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
        owner_limits_required_for_private_live=True,
    )
    snapshot = PortfolioSnapshot(
        open_positions=[ExposureItem("BTCUSDT", "futures", 4_000.0, 0.01, "long")],
        pending_orders=[],
        pending_live_candidates=[],
        account_equity=10_000.0,
        used_margin=2_000.0,
        snapshot_fresh=True,
        correlation_stress=0.2,
        unknown_correlation=False,
        owner_limits_present=False,
    )
    result = evaluate_portfolio_risk(snapshot, limits)
    assert result.opening_orders_allowed is False
    assert "owner_limits_fehlen" in result.block_reasons
