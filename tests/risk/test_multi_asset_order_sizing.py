from __future__ import annotations

from shared_py.order_sizing import (
    OrderSizingInput,
    build_order_sizing_explanation_de,
    compute_order_qty_from_risk,
)


def _base(**overrides: object) -> OrderSizingInput:
    payload = {
        "symbol": "BTCUSDT",
        "market_family": "futures",
        "risk_tier": "RISK_TIER_1_MAJOR_LIQUID",
        "liquidity_tier": "TIER_1",
        "account_equity": 10_000.0,
        "equity_fresh": True,
        "available_margin": 8_000.0,
        "max_account_margin_usage": 0.5,
        "max_position_risk_pct": 0.02,
        "max_daily_loss": 500.0,
        "max_weekly_loss": 1500.0,
        "current_daily_loss": 100.0,
        "current_weekly_loss": 200.0,
        "current_drawdown": 0.08,
        "max_drawdown_limit": 0.2,
        "stop_distance_pct": 0.01,
        "expected_slippage_pct": 0.001,
        "fee_pct": 0.0005,
        "leverage_cap": 10,
        "min_qty": 0.001,
        "min_notional": 5.0,
        "qty_step": 0.001,
        "open_positions_notional": 1000.0,
        "pending_orders_notional": 500.0,
        "mode": "paper",
    }
    payload.update(overrides)
    return OrderSizingInput(**payload)


def test_missing_equity_blocks() -> None:
    out = compute_order_qty_from_risk(_base(account_equity=None))
    assert "equity_fehlt" in out.block_reasons


def test_stale_equity_blocks() -> None:
    out = compute_order_qty_from_risk(_base(equity_fresh=False))
    assert "equity_stale" in out.block_reasons


def test_missing_risk_tier_blocks() -> None:
    out = compute_order_qty_from_risk(_base(risk_tier=None))
    assert "risk_tier_fehlt" in out.block_reasons


def test_missing_liquidity_blocks() -> None:
    out = compute_order_qty_from_risk(_base(liquidity_tier=None))
    assert "liquiditaetsstatus_fehlt" in out.block_reasons


def test_margin_usage_over_limit_blocks() -> None:
    out = compute_order_qty_from_risk(_base(max_account_margin_usage=0.00001))
    assert "margin_usage_ueber_limit" in out.block_reasons


def test_position_risk_over_limit_blocks() -> None:
    out = compute_order_qty_from_risk(_base(max_position_risk_pct=0.00001))
    assert "keine_sichere_groesse_verfuegbar" in out.block_reasons or len(out.block_reasons) > 0


def test_daily_loss_limit_blocks() -> None:
    out = compute_order_qty_from_risk(_base(current_daily_loss=600.0))
    assert "daily_loss_limit_ueberschritten" in out.block_reasons


def test_weekly_loss_limit_blocks() -> None:
    out = compute_order_qty_from_risk(_base(current_weekly_loss=2000.0))
    assert "weekly_loss_limit_ueberschritten" in out.block_reasons


def test_drawdown_limit_blocks() -> None:
    out = compute_order_qty_from_risk(_base(current_drawdown=0.3))
    assert "drawdown_limit_ueberschritten" in out.block_reasons


def test_precision_rounding_cannot_increase_risk() -> None:
    out = compute_order_qty_from_risk(_base(qty_step=0.01))
    assert out.suggested_qty <= out.max_allowed_qty


def test_min_qty_and_min_notional_blocks() -> None:
    out = compute_order_qty_from_risk(_base(min_qty=5000.0, min_notional=5000.0))
    assert "min_qty_unterschritten" in out.block_reasons or "min_notional_unterschritten" in out.block_reasons


def test_tier_d_e_assets_get_zero_size() -> None:
    out = compute_order_qty_from_risk(_base(risk_tier="RISK_TIER_4_SHADOW_ONLY"))
    assert out.suggested_qty == 0.0
    assert "risk_tier_blockiert_groesse" in out.block_reasons


def test_tier_a_can_compute_but_live_is_more_conservative() -> None:
    paper = compute_order_qty_from_risk(_base(mode="paper"))
    live = compute_order_qty_from_risk(_base(mode="live"))
    assert paper.max_notional >= live.max_notional


def test_german_explanation_generated() -> None:
    out = compute_order_qty_from_risk(_base())
    text = build_order_sizing_explanation_de(out)
    assert "Vorgeschlagene Groesse" in text or "Order-Sizing blockiert" in text
