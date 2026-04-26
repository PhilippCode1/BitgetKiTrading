from __future__ import annotations

from shared_py.market_data_quality import (
    asset_data_quality_blocks_live,
    build_asset_data_quality_summary,
    evaluate_market_data_quality,
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


def test_missing_exchange_truth_is_not_enough_evidence() -> None:
    result = evaluate_market_data_quality(
        {
            "symbol": "ETHUSDT",
            "market_family": "futures",
            "product_type": "USDT-FUTURES",
            "candles": [
                {"ts_ms": 1000, "open": 10, "high": 12, "low": 9, "close": 11, "volume": 1},
                {"ts_ms": 2000, "open": 11, "high": 13, "low": 10, "close": 12, "volume": 1},
            ],
            "expected_candle_interval_ms": 1000,
            "orderbook_present": True,
            "last_orderbook_ts_ms": 1950,
            "now_ts_ms": 2000,
            "orderbook_max_age_ms": 500,
            "best_bid": 100.0,
            "best_ask": 100.1,
            "last_price": 100.05,
            "mark_price": 100.06,
            "index_price": 100.0,
            "runtime_data": True,
            "exchange_truth_checked": False,
        }
    )
    assert result.status == "not_enough_evidence"
    assert result.live_allowed is False
