from __future__ import annotations

from shared_py.market_data_quality import (
    asset_data_quality_blocks_live,
    build_asset_data_quality_summary,
    detect_candle_gaps,
    detect_duplicate_candles,
    detect_out_of_order_candles,
    validate_candle_sequence,
    validate_funding_freshness,
    validate_ohlc_sanity,
    validate_orderbook_freshness,
)


def test_perfect_candles_pass() -> None:
    candles = [
        {"ts_ms": 1, "open": 1, "high": 2, "low": 1, "close": 2, "volume": 1},
        {"ts_ms": 2, "open": 2, "high": 3, "low": 2, "close": 3, "volume": 1},
    ]
    assert validate_candle_sequence(candles)[0] is True
    assert detect_candle_gaps(candles, expected_interval_ms=1)[0] is True
    assert validate_ohlc_sanity(candles)[0] is True


def test_candle_gap_fail() -> None:
    candles = [{"ts_ms": 1}, {"ts_ms": 10}]
    ok, reasons = detect_candle_gaps(candles, expected_interval_ms=2)
    assert ok is False
    assert "candle_critical_gap" in reasons


def test_duplicate_candles_warning_or_fail() -> None:
    candles = [{"ts_ms": 1}, {"ts_ms": 1}]
    ok, reasons = detect_duplicate_candles(candles)
    assert (ok is True and "candle_duplicates_warning" in reasons) or (
        ok is False and "candle_duplicates_critical" in reasons
    )


def test_out_of_order_fail() -> None:
    ok, reasons = detect_out_of_order_candles([{"ts_ms": 2}, {"ts_ms": 1}])
    assert ok is False
    assert "candle_out_of_order" in reasons


def test_stale_orderbook_fail_for_live() -> None:
    ok, reasons = validate_orderbook_freshness(
        orderbook_present=True,
        last_orderbook_ts_ms=1000,
        now_ts_ms=10000,
        max_age_ms=1000,
    )
    assert ok is False
    assert "orderbook_stale" in reasons


def test_missing_bids_asks_fail() -> None:
    summary = build_asset_data_quality_summary(
        symbol="ETHUSDT",
        market_family="futures",
        product_type="USDT-FUTURES",
        data_source="unit",
        quality_status="data_invalid",
        block_reasons=["top_of_book_missing"],
    )
    assert summary.result == "FAIL"


def test_unrealistic_ohlc_fail() -> None:
    ok, reasons = validate_ohlc_sanity([{"ts_ms": 1, "open": 3, "high": 2, "low": 4, "close": 1, "volume": 1}])
    assert ok is False
    assert "ohlc_high_below_low" in reasons or "ohlc_range_violation" in reasons


def test_stale_funding_warning_or_fail() -> None:
    ok, reasons, warnings = validate_funding_freshness(
        market_family="futures",
        funding_last_ts_ms=1,
        now_ts_ms=10_000,
        max_age_ms=100,
        funding_required_for_strategy=False,
    )
    assert (ok is True and "funding_stale_warning" in warnings) or (
        ok is False and "funding_stale" in reasons
    )


def test_unknown_blocks_live() -> None:
    assert asset_data_quality_blocks_live(quality_status="data_unknown", block_reasons=[]) is True


def test_fail_blocks_live() -> None:
    assert asset_data_quality_blocks_live(quality_status="data_invalid", block_reasons=["x"]) is True
