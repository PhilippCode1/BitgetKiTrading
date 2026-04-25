from __future__ import annotations

from shared_py.portfolio_risk_controls import (
    ExposureItem,
    PortfolioRiskLimits,
    PortfolioSnapshot,
    build_portfolio_risk_summary_de,
    evaluate_portfolio_risk,
)


def _limits() -> PortfolioRiskLimits:
    return PortfolioRiskLimits(
        max_total_notional=20_000.0,
        max_margin_usage=0.6,
        max_largest_position_risk=0.03,
        max_concurrent_positions=3,
        max_pending_orders=2,
        max_pending_live_candidates=2,
        max_net_directional_exposure=12_000.0,
        max_correlation_stress=0.8,
        max_funding_concentration=0.01,
        max_family_exposure=15_000.0,
    )


def _item(symbol: str, notional: float, side: str = "long", family: str = "futures", risk_pct: float = 0.01) -> ExposureItem:
    return ExposureItem(
        symbol=symbol,
        market_family=family,
        notional=notional,
        risk_pct=risk_pct,
        side=side,  # type: ignore[arg-type]
        funding_rate_abs=0.001,
        basis_bps_abs=5.0,
    )


def _snapshot(**overrides: object) -> PortfolioSnapshot:
    payload = {
        "open_positions": [_item("BTCUSDT", 4000.0)],
        "pending_orders": [],
        "pending_live_candidates": [],
        "account_equity": 10_000.0,
        "used_margin": 2000.0,
        "snapshot_fresh": True,
        "correlation_stress": 0.4,
        "unknown_correlation": False,
    }
    payload.update(overrides)
    return PortfolioSnapshot(**payload)


def test_missing_snapshot_blocks() -> None:
    out = evaluate_portfolio_risk(None, _limits())
    assert "portfolio_snapshot_fehlt" in out.block_reasons


def test_stale_snapshot_blocks() -> None:
    out = evaluate_portfolio_risk(_snapshot(snapshot_fresh=False), _limits())
    assert "portfolio_snapshot_stale" in out.block_reasons


def test_exposure_over_limit_blocks() -> None:
    out = evaluate_portfolio_risk(_snapshot(open_positions=[_item("BTCUSDT", 50_000.0)]), _limits())
    assert "total_exposure_ueber_limit" in out.block_reasons


def test_margin_usage_over_limit_blocks() -> None:
    out = evaluate_portfolio_risk(_snapshot(used_margin=9000.0), _limits())
    assert "margin_usage_ueber_limit" in out.block_reasons


def test_largest_position_risk_over_limit_blocks() -> None:
    out = evaluate_portfolio_risk(_snapshot(open_positions=[_item("BTCUSDT", 1000.0, risk_pct=0.08)]), _limits())
    assert "largest_position_risk_ueber_limit" in out.block_reasons


def test_max_concurrent_positions_blocks() -> None:
    out = evaluate_portfolio_risk(_snapshot(open_positions=[_item("A", 1000), _item("B", 1000), _item("C", 1000), _item("D", 1000)]), _limits())
    assert "max_concurrent_positions_ueberschritten" in out.block_reasons


def test_pending_orders_increase_exposure() -> None:
    base = evaluate_portfolio_risk(_snapshot(), _limits())
    with_pending = evaluate_portfolio_risk(_snapshot(pending_orders=[_item("ETHUSDT", 3000.0)]), _limits())
    assert with_pending.total_exposure > base.total_exposure


def test_pending_candidates_increase_risk() -> None:
    out = evaluate_portfolio_risk(_snapshot(pending_live_candidates=[_item("SOLUSDT", 4000.0)]), _limits())
    assert out.pending_live_candidates_count == 1
    assert out.total_exposure >= 8000.0


def test_direction_long_limit_blocks() -> None:
    out = evaluate_portfolio_risk(_snapshot(open_positions=[_item("A", 9000), _item("B", 5000)]), _limits())
    assert "net_long_exposure_ueber_limit" in out.block_reasons


def test_direction_short_limit_blocks() -> None:
    out = evaluate_portfolio_risk(_snapshot(open_positions=[_item("A", 9000, side="short"), _item("B", 5000, side="short")]), _limits())
    assert "net_short_exposure_ueber_limit" in out.block_reasons


def test_correlation_stress_blocks() -> None:
    out = evaluate_portfolio_risk(_snapshot(correlation_stress=0.95), _limits())
    assert "correlation_stress_zu_hoch" in out.block_reasons


def test_unknown_correlation_conservative() -> None:
    out = evaluate_portfolio_risk(_snapshot(unknown_correlation=True), _limits())
    assert "correlation_unbekannt_konservativ" in out.cap_reasons
    assert "correlation_stress_zu_hoch" in out.block_reasons


def test_german_summary_reasons() -> None:
    out = evaluate_portfolio_risk(_snapshot(correlation_stress=0.95), _limits())
    summary = build_portfolio_risk_summary_de(out)
    assert "Portfolio-Risiko blockiert Live-Opening" in summary


def test_pass_is_only_next_gate_step() -> None:
    out = evaluate_portfolio_risk(_snapshot(), _limits())
    assert out.allows_next_gate_only is True
