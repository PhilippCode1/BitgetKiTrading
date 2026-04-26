from __future__ import annotations

from shared_py.market_data_quality import (
    asset_data_quality_blocks_live,
    detect_candle_gaps,
    evaluate_market_data_quality,
    validate_candle_sequence,
    validate_funding_freshness,
    validate_ohlc_sanity,
    validate_orderbook_freshness,
    validate_spread_sanity,
)


def _candles_ok() -> list[dict]:
    return [
        {"ts_ms": 1000, "open": 10, "high": 12, "low": 9, "close": 11, "volume": 10},
        {"ts_ms": 2000, "open": 11, "high": 13, "low": 10, "close": 12, "volume": 11},
    ]


def test_good_data_quality_pass() -> None:
    candles = _candles_ok()
    assert validate_candle_sequence(candles)[0] is True
    assert detect_candle_gaps(candles, 1000)[0] is True
    assert validate_ohlc_sanity(candles)[0] is True
    assert (
        validate_orderbook_freshness(
            orderbook_present=True,
            last_orderbook_ts_ms=9_900,
            now_ts_ms=10_000,
            max_age_ms=500,
        )[0]
        is True
    )
    assert validate_spread_sanity(bid=100.0, ask=100.2, max_spread_bps=30.0)[0] is True


def test_candle_gap_fail() -> None:
    candles = [
        {"ts_ms": 1000, "open": 10, "high": 11, "low": 9, "close": 10.5, "volume": 1},
        {"ts_ms": 5000, "open": 10.5, "high": 11.5, "low": 10, "close": 11, "volume": 1},
    ]
    ok, reasons = detect_candle_gaps(candles, 1000)
    assert ok is False
    assert "candle_critical_gap" in reasons


def test_out_of_order_fail() -> None:
    candles = [
        {"ts_ms": 2000, "open": 10, "high": 12, "low": 9, "close": 11, "volume": 1},
        {"ts_ms": 1000, "open": 11, "high": 12, "low": 10, "close": 11.2, "volume": 1},
    ]
    ok, reasons = validate_candle_sequence(candles)
    assert ok is False
    assert "candle_out_of_order" in reasons


def test_funding_stale_warning_or_block() -> None:
    ok_warn, reasons_warn, warnings = validate_funding_freshness(
        market_family="futures",
        funding_last_ts_ms=1000,
        now_ts_ms=10_000,
        max_age_ms=100,
        funding_required_for_strategy=False,
    )
    assert ok_warn is True
    assert reasons_warn == []
    assert "funding_stale_warning" in warnings

    ok_block, reasons_block, warnings_block = validate_funding_freshness(
        market_family="futures",
        funding_last_ts_ms=1000,
        now_ts_ms=10_000,
        max_age_ms=100,
        funding_required_for_strategy=True,
    )
    assert ok_block is False
    assert "funding_stale" in reasons_block
    assert warnings_block == []


def test_unknown_status_fail_closed() -> None:
    assert asset_data_quality_blocks_live(quality_status="data_unknown", block_reasons=[]) is True


def test_runtime_evidence_required_for_live_allowed() -> None:
    result = evaluate_market_data_quality(
        {
            "symbol": "BTCUSDT",
            "market_family": "futures",
            "product_type": "USDT-FUTURES",
            "candles": _candles_ok(),
            "expected_candle_interval_ms": 1000,
            "orderbook_present": True,
            "last_orderbook_ts_ms": 9_900,
            "now_ts_ms": 10_000,
            "orderbook_max_age_ms": 500,
            "best_bid": 100.0,
            "best_ask": 100.1,
            "last_price": 100.05,
            "mark_price": 100.06,
            "index_price": 100.0,
            "runtime_data": False,
            "exchange_truth_checked": False,
        }
    )
    assert result.status == "not_enough_evidence"
    assert result.live_allowed is False
