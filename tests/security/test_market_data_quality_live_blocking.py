from __future__ import annotations

from shared_py.market_data_quality import (
    asset_data_quality_blocks_live,
    build_asset_data_quality_summary,
    validate_orderbook_freshness,
    validate_spread_sanity,
)


def test_stale_orderbook_blocks_live() -> None:
    ok, reasons = validate_orderbook_freshness(
        orderbook_present=True,
        last_orderbook_ts_ms=1_000,
        now_ts_ms=10_000,
        max_age_ms=1_000,
    )
    assert ok is False
    assert "orderbook_stale" in reasons
    assert asset_data_quality_blocks_live(quality_status="data_stale", block_reasons=reasons) is True


def test_missing_orderbook_blocks_live() -> None:
    ok, reasons = validate_orderbook_freshness(
        orderbook_present=False,
        last_orderbook_ts_ms=None,
        now_ts_ms=10_000,
        max_age_ms=1_000,
    )
    assert ok is False
    assert "orderbook_missing" in reasons
    assert asset_data_quality_blocks_live(quality_status="data_incomplete", block_reasons=reasons) is True


def test_extreme_spread_blocks_live() -> None:
    ok, reasons, warnings = validate_spread_sanity(bid=100.0, ask=104.0, max_spread_bps=20.0)
    assert ok is False
    assert "spread_extreme" in reasons
    assert warnings == []
    assert asset_data_quality_blocks_live(quality_status="data_invalid", block_reasons=reasons) is True


def test_delisted_blocks_live() -> None:
    summary = build_asset_data_quality_summary(
        symbol="ETHUSDT",
        market_family="futures",
        product_type="USDT-FUTURES",
        data_source="unit_test",
        quality_status="data_live_blocked",
        block_reasons=["asset_delisted"],
    )
    assert summary.live_impact == "LIVE_BLOCKED"
    assert summary.result == "FAIL"


def test_suspended_blocks_live() -> None:
    summary = build_asset_data_quality_summary(
        symbol="ETHUSDT",
        market_family="futures",
        product_type="USDT-FUTURES",
        data_source="unit_test",
        quality_status="data_live_blocked",
        block_reasons=["asset_suspended"],
    )
    assert summary.live_impact == "LIVE_BLOCKED"
    assert summary.result == "FAIL"


def test_unknown_blocks_live() -> None:
    summary = build_asset_data_quality_summary(
        symbol="ETHUSDT",
        market_family="futures",
        product_type="USDT-FUTURES",
        data_source="unit_test",
        quality_status="data_unknown",
        block_reasons=[],
    )
    assert summary.live_impact == "LIVE_BLOCKED"
    assert summary.result == "UNKNOWN"
