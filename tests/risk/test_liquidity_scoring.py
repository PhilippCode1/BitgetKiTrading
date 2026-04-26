from __future__ import annotations

from shared_py.liquidity_scoring import (
    build_liquidity_assessment,
    build_liquidity_block_reasons_de,
    evaluate_liquidity_gate,
    recommended_max_order_notional,
)


def _levels(price: float, qty: float) -> list[dict]:
    return [{"price": price, "qty": qty}, {"price": price * 0.999, "qty": qty}]


def test_missing_orderbook_blocks() -> None:
    out = build_liquidity_assessment(
        symbol="ALTUSDT",
        bid=None,
        ask=None,
        bids=[],
        asks=[],
        orderbook_age_ms=1000,
        max_orderbook_age_ms=10_000,
        planned_qty=1.0,
        requested_notional=100.0,
        status="active",
    )
    assert out.live_allowed is False
    assert "orderbook_fehlt" in out.block_reasons


def test_stale_orderbook_blocks() -> None:
    out = build_liquidity_assessment(
        symbol="ALTUSDT",
        bid=10.0,
        ask=10.2,
        bids=_levels(10.0, 2.0),
        asks=_levels(10.2, 2.0),
        orderbook_age_ms=20_000,
        max_orderbook_age_ms=5_000,
        planned_qty=1.0,
        requested_notional=100.0,
        status="active",
    )
    assert "orderbook_stale" in out.block_reasons


def test_empty_bids_block() -> None:
    out = build_liquidity_assessment(
        symbol="ALTUSDT",
        bid=10.0,
        ask=10.1,
        bids=[],
        asks=_levels(10.1, 1.0),
        orderbook_age_ms=1000,
        max_orderbook_age_ms=5_000,
        planned_qty=1.0,
        requested_notional=100.0,
        status="active",
    )
    assert "bids_fehlen" in out.block_reasons


def test_empty_asks_block() -> None:
    out = build_liquidity_assessment(
        symbol="ALTUSDT",
        bid=10.0,
        ask=10.1,
        bids=_levels(10.0, 1.0),
        asks=[],
        orderbook_age_ms=1000,
        max_orderbook_age_ms=5_000,
        planned_qty=1.0,
        requested_notional=100.0,
        status="active",
    )
    assert "asks_fehlen" in out.block_reasons


def test_high_spread_blocks() -> None:
    out = build_liquidity_assessment(
        symbol="ALTUSDT",
        bid=10.0,
        ask=11.0,
        bids=_levels(10.0, 2.0),
        asks=_levels(11.0, 2.0),
        orderbook_age_ms=1000,
        max_orderbook_age_ms=10_000,
        planned_qty=1.0,
        requested_notional=100.0,
        status="active",
    )
    assert "spread_zu_hoch" in out.block_reasons


def test_high_vwap_slippage_blocks() -> None:
    out = build_liquidity_assessment(
        symbol="ALTUSDT",
        bid=10.0,
        ask=10.1,
        bids=[{"price": 9.0, "qty": 0.1}],
        asks=[{"price": 11.0, "qty": 0.1}],
        orderbook_age_ms=500,
        max_orderbook_age_ms=10_000,
        planned_qty=1.0,
        requested_notional=100.0,
        status="active",
    )
    assert ("slippage_zu_hoch" in out.block_reasons) or ("slippage_unbekannt" in out.block_reasons)


def test_insufficient_depth_blocks() -> None:
    out = build_liquidity_assessment(
        symbol="ALTUSDT",
        bid=10.0,
        ask=10.1,
        bids=[{"price": 10.0, "qty": 0.0}],
        asks=[{"price": 10.1, "qty": 0.0}],
        orderbook_age_ms=500,
        max_orderbook_age_ms=10_000,
        planned_qty=0.1,
        requested_notional=100.0,
        status="active",
    )
    assert "depth_unzureichend" in out.block_reasons


def test_tier1_preflight_can_pass() -> None:
    out = build_liquidity_assessment(
        symbol="BTCUSDT",
        bid=63000.0,
        ask=63000.5,
        bids=[{"price": 63000.0, "qty": 2.0}, {"price": 62999.5, "qty": 2.0}],
        asks=[{"price": 63000.5, "qty": 2.0}, {"price": 63001.0, "qty": 2.0}],
        orderbook_age_ms=500,
        max_orderbook_age_ms=10_000,
        planned_qty=0.1,
        requested_notional=1000.0,
        status="active",
        owner_approved_small_size=True,
    )
    assert out.liquidity_tier in {"TIER_1", "TIER_2"}


def test_tier4_blocks_live() -> None:
    out = build_liquidity_assessment(
        symbol="ALTUSDT",
        bid=10.0,
        ask=10.5,
        bids=[{"price": 10.0, "qty": 0.2}],
        asks=[{"price": 10.5, "qty": 0.2}],
        orderbook_age_ms=500,
        max_orderbook_age_ms=10_000,
        planned_qty=10.0,
        requested_notional=5000.0,
        status="active",
    )
    assert out.live_allowed is False
    assert "liquiditaetstier_blockiert_live" in out.block_reasons


def test_recommended_max_size_drops_when_depth_low() -> None:
    low = recommended_max_order_notional(liquidity_tier="TIER_3", depth_notional_top5=1000.0)
    high = recommended_max_order_notional(liquidity_tier="TIER_3", depth_notional_top5=20_000.0)
    assert low < high


def test_german_block_reasons_generated() -> None:
    de = build_liquidity_block_reasons_de(["spread_zu_hoch", "orderbook_stale"])
    assert any("Spread" in item for item in de)
    assert any("stale" in item.lower() for item in de)


def test_synthetic_evidence_never_live_allowed() -> None:
    result = evaluate_liquidity_gate(
        {
            "symbol": "BTCUSDT",
            "order_type": "market",
            "requested_size": 0.1,
                "requested_notional": 100.0,
            "best_bid": 60000.0,
            "best_ask": 60001.0,
            "bids": [{"price": 60000.0, "qty": 1.0}],
            "asks": [{"price": 60001.0, "qty": 1.0}],
                "orderbook_depth_top_10": 5000.0,
            "timestamp_age_ms": 500,
            "max_orderbook_age_ms": 10_000,
            "estimated_slippage_bps": 8.0,
            "min_depth_ratio": 0.5,
            "tick_size": 0.1,
            "lot_size": 0.001,
            "min_qty": 0.001,
            "min_notional": 5.0,
            "precision": {"price": 1},
            "runtime_data": False,
        }
    )
    assert result.status in {"fail", "not_enough_evidence"}
    assert result.live_allowed is False
    assert result.evidence_level == "synthetic"
