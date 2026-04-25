from __future__ import annotations

from shared_py.portfolio_risk_controls import (
    ExposureItem,
    PortfolioRiskLimits,
    PortfolioSnapshot,
    evaluate_portfolio_risk,
    portfolio_risk_blocks_live,
)


def _limits() -> PortfolioRiskLimits:
    return PortfolioRiskLimits(
        max_total_notional=10_000.0,
        max_margin_usage=0.5,
        max_largest_position_risk=0.03,
        max_concurrent_positions=2,
        max_pending_orders=2,
        max_pending_live_candidates=1,
        max_net_directional_exposure=8_000.0,
        max_correlation_stress=0.7,
        max_funding_concentration=0.01,
        max_family_exposure=9_000.0,
    )


def _snapshot(**overrides: object) -> PortfolioSnapshot:
    payload = {
        "open_positions": [ExposureItem("BTCUSDT", "futures", 3000.0, 0.01, "long", 0.001, 5.0)],
        "pending_orders": [],
        "pending_live_candidates": [],
        "account_equity": 10_000.0,
        "used_margin": 1000.0,
        "snapshot_fresh": True,
        "correlation_stress": 0.3,
        "unknown_correlation": False,
    }
    payload.update(overrides)
    return PortfolioSnapshot(**payload)


def test_live_block_when_snapshot_missing() -> None:
    out = evaluate_portfolio_risk(None, _limits())
    assert portfolio_risk_blocks_live(out) is True


def test_live_block_on_high_risk_portfolio() -> None:
    snap = _snapshot(open_positions=[ExposureItem("A", "futures", 9000.0, 0.05, "long", 0.02, 30.0)])
    out = evaluate_portfolio_risk(snap, _limits())
    assert portfolio_risk_blocks_live(out) is True
    assert len(out.block_reasons) > 0
