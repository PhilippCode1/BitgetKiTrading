from __future__ import annotations

from shared_py.liquidity_scoring import evaluate_liquidity_gate


def _base() -> dict:
    return {
        "symbol": "BTCUSDT",
        "market_family": "futures",
        "order_type": "market",
        "requested_size": 0.2,
        "requested_notional": 12000.0,
        "best_bid": 60000.0,
        "best_ask": 60001.0,
        "bids": [{"price": 60000.0, "qty": 2.0}],
        "asks": [{"price": 60001.0, "qty": 2.0}],
        "orderbook_depth_top_10": 60000.0,
        "timestamp_age_ms": 500,
        "max_orderbook_age_ms": 5000,
        "estimated_slippage_bps": 8.0,
        "min_depth_ratio": 0.7,
        "tick_size": 0.1,
        "lot_size": 0.001,
        "min_qty": 0.001,
        "min_notional": 5.0,
        "precision": {"price": 1, "qty": 3},
        "runtime_data": True,
    }


def test_missing_orderbook_blocks_live() -> None:
    payload = _base()
    payload["bids"] = []
    payload["asks"] = []
    result = evaluate_liquidity_gate(payload)
    assert result.live_allowed is False
    assert "orderbook_fehlt" in result.reasons


def test_stale_orderbook_blocks_live() -> None:
    payload = _base()
    payload["timestamp_age_ms"] = 60_000
    result = evaluate_liquidity_gate(payload)
    assert result.live_allowed is False
    assert "orderbook_stale" in result.reasons


def test_market_order_without_slippage_gate_blocks_live() -> None:
    payload = _base()
    payload["estimated_slippage_bps"] = None
    result = evaluate_liquidity_gate(payload)
    assert result.live_allowed is False
    assert "market_order_slippage_missing" in result.reasons
