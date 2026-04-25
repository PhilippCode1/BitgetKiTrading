from __future__ import annotations

from shared_py.order_sizing import OrderSizingInput, compute_order_qty_from_risk, order_sizing_blocks_live


def _input(**overrides: object) -> OrderSizingInput:
    base = {
        "symbol": "ALTUSDT",
        "market_family": "futures",
        "risk_tier": "RISK_TIER_3_ELEVATED_RISK",
        "liquidity_tier": "TIER_3",
        "account_equity": 3000.0,
        "equity_fresh": True,
        "available_margin": 1000.0,
        "max_account_margin_usage": 0.3,
        "max_position_risk_pct": 0.01,
        "max_daily_loss": 100.0,
        "max_weekly_loss": 300.0,
        "current_daily_loss": 10.0,
        "current_weekly_loss": 10.0,
        "current_drawdown": 0.05,
        "max_drawdown_limit": 0.2,
        "stop_distance_pct": 0.02,
        "expected_slippage_pct": 0.005,
        "fee_pct": 0.001,
        "leverage_cap": 4,
        "min_qty": 1.0,
        "min_notional": 20.0,
        "qty_step": 1.0,
        "open_positions_notional": 0.0,
        "pending_orders_notional": 0.0,
        "mode": "live",
    }
    base.update(overrides)
    return OrderSizingInput(**base)


def test_live_blocks_when_limits_exceeded() -> None:
    out = compute_order_qty_from_risk(_input(current_daily_loss=200.0))
    assert order_sizing_blocks_live(out) is True
    assert "daily_loss_limit_ueberschritten" in out.block_reasons


def test_live_blocks_for_unsafe_size_context() -> None:
    out = compute_order_qty_from_risk(_input(risk_tier=None))
    assert order_sizing_blocks_live(out) is True
    assert "risk_tier_fehlt" in out.block_reasons
