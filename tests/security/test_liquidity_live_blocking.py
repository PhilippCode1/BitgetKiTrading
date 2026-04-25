from __future__ import annotations

from shared_py.liquidity_scoring import build_liquidity_assessment


def test_tier5_blocks_live() -> None:
    out = build_liquidity_assessment(
        symbol="XUSDT",
        bid=1.0,
        ask=1.1,
        bids=[{"price": 1.0, "qty": 10.0}],
        asks=[{"price": 1.1, "qty": 10.0}],
        orderbook_age_ms=500,
        max_orderbook_age_ms=10_000,
        planned_qty=1.0,
        requested_notional=100.0,
        status="delisted",
    )
    assert out.live_allowed is False
    assert "liquiditaetstier_blockiert_live" in out.block_reasons


def test_tier3_requires_owner_small_size_approval() -> None:
    out = build_liquidity_assessment(
        symbol="MIDUSDT",
        bid=100.0,
        ask=100.2,
        bids=[{"price": 100.0, "qty": 50.0}, {"price": 99.9, "qty": 50.0}],
        asks=[{"price": 100.2, "qty": 50.0}, {"price": 100.3, "qty": 50.0}],
        orderbook_age_ms=500,
        max_orderbook_age_ms=10_000,
        planned_qty=2.0,
        requested_notional=900.0,
        status="active",
        owner_approved_small_size=False,
    )
    assert "tier3_ohne_owner_kleingroessenfreigabe" in out.block_reasons
