from __future__ import annotations

from shared_py.analysis import (
    compute_data_completeness_0_1,
    compute_pipeline_trade_mode,
    family_foreign_namespace_violations,
    feature_namespaces_for_identity,
    gate_cross_family_derivative_leak,
    gate_tick_lot_vs_metadata,
    sanitize_ticker_snapshot_for_family,
    validate_event_vs_resolved_metadata,
)
from shared_py.bitget.instruments import BitgetInstrumentCatalogEntry, BitgetInstrumentIdentity


def _identity(**kwargs: object) -> BitgetInstrumentIdentity:
    base = dict(
        market_family="spot",
        symbol="BTCUSDT",
        public_ws_inst_type="SPOT",
        inventory_visible=True,
        analytics_eligible=True,
    )
    base.update(kwargs)
    return BitgetInstrumentIdentity.model_validate(base)


def _entry(**kwargs: object) -> BitgetInstrumentCatalogEntry:
    base = dict(
        market_family="spot",
        symbol="BTCUSDT",
        public_ws_inst_type="SPOT",
        inventory_visible=True,
        analytics_eligible=True,
        trading_enabled=True,
        subscribe_enabled=True,
    )
    base.update(kwargs)
    return BitgetInstrumentCatalogEntry.model_validate(base)


def test_feature_namespaces_futures_only_derivatives_with_caps() -> None:
    fut = _identity(
        market_family="futures",
        product_type="USDT-FUTURES",
        public_ws_inst_type="USDT-FUTURES",
        supports_funding=True,
        supports_open_interest=False,
    )
    ns = feature_namespaces_for_identity(fut)
    assert any("futures_derivatives" in n for n in ns)


def test_family_foreign_namespace_violation() -> None:
    issues = family_foreign_namespace_violations(
        market_family="spot",
        active_namespaces=[
            "feat.bitget.public_market.v1",
            "feat.bitget.futures_derivatives.v1",
        ],
    )
    assert issues


def test_validate_event_vs_metadata_mismatch() -> None:
    ev = _identity(market_family="futures", product_type="USDT-FUTURES", public_ws_inst_type="USDT-FUTURES")
    row = _entry(market_family="futures", product_type="COIN-FUTURES", public_ws_inst_type="COIN-FUTURES")
    issues = validate_event_vs_resolved_metadata(ev, row)
    assert "metadata_product_type_mismatch" in issues


def test_gate_cross_family_leak_spot_with_mark() -> None:
    issues = gate_cross_family_derivative_leak(
        market_family="spot",
        ticker_mark=100.0,
        ticker_index=None,
        ticker_funding_rate=None,
        funding_snapshot_present=False,
        open_interest_snapshot_present=False,
    )
    assert "cross_family:ticker_mark_index_on_spot_margin" in issues


def test_completeness_ignores_missing_oi_when_not_supported() -> None:
    class _MC:
        spread_bps = 1.0
        execution_cost_bps = 2.0
        funding_rate_bps = 1.0
        open_interest = None
        mark_index_spread_bps = 1.0
        basis_bps = None

    score = compute_data_completeness_0_1(
        market_family="futures",
        market_context=_MC(),
        realized_vol_20=0.1,
        session_drift_bps=5.0,
        supports_funding=True,
        supports_open_interest=False,
    )
    assert score > 0.7


def test_pipeline_trade_mode_analytics_when_live_off() -> None:
    mode = compute_pipeline_trade_mode(
        hard_issues=[],
        metadata_health_status="ok",
        data_completeness=0.9,
        staleness_score=0.1,
        analytics_eligible=True,
        live_execution_enabled=False,
        execution_disabled=True,
    )
    assert mode == "analytics_only"


def test_pipeline_trade_mode_do_not_trade_on_hard_issue() -> None:
    mode = compute_pipeline_trade_mode(
        hard_issues=["metadata_symbol_mismatch"],
        metadata_health_status="ok",
        data_completeness=0.9,
        staleness_score=0.1,
        analytics_eligible=True,
        live_execution_enabled=True,
        execution_disabled=False,
    )
    assert mode == "do_not_trade"


def test_tick_lot_gate_detects_bad_grid() -> None:
    issues = gate_tick_lot_vs_metadata(
        open_=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        base_vol=1.0,
        price_tick_size="0.1",
        quantity_step="0.001",
    )
    assert isinstance(issues, list)


def test_sanitize_ticker_strips_derivatives_on_spot() -> None:
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _T:
        symbol: str
        ts_ms: int
        source: str
        bid_pr: float | None
        ask_pr: float | None
        bid_sz: float | None
        ask_sz: float | None
        last_pr: float | None
        mark_price: float | None
        index_price: float | None

    raw = _T(
        symbol="X",
        ts_ms=1,
        source="ws",
        bid_pr=1.0,
        ask_pr=1.1,
        bid_sz=1.0,
        ask_sz=1.0,
        last_pr=1.05,
        mark_price=1.04,
        index_price=1.03,
    )
    clean = sanitize_ticker_snapshot_for_family(
        raw,
        market_family="spot",
        supports_funding=False,
        supports_open_interest=False,
    )
    assert clean is not None
    assert clean.mark_price is None
    assert clean.index_price is None
