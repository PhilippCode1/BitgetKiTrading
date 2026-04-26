from __future__ import annotations

from shared_py.market_data_quality import evaluate_market_data_quality


def _base() -> dict:
    return {
        "symbol": "BTCUSDT",
        "market_family": "futures",
        "product_type": "USDT-FUTURES",
        "candles": [
            {"ts_ms": 1000, "open": 10, "high": 12, "low": 9, "close": 11, "volume": 1},
            {"ts_ms": 2000, "open": 11, "high": 13, "low": 10, "close": 12, "volume": 1},
        ],
        "expected_candle_interval_ms": 1000,
        "orderbook_present": True,
        "last_orderbook_ts_ms": 1900,
        "now_ts_ms": 2000,
        "orderbook_max_age_ms": 500,
        "best_bid": 100.0,
        "best_ask": 100.2,
        "last_price": 100.1,
        "mark_price": 100.1,
        "index_price": 100.0,
        "runtime_data": True,
        "exchange_truth_checked": True,
    }


def test_negative_price_blocks_live() -> None:
    payload = _base()
    payload["last_price"] = -1.0
    result = evaluate_market_data_quality(payload)
    assert result.live_allowed is False
    assert "last_price_non_positive" in result.reasons


def test_bid_ask_crossed_blocks_live() -> None:
    payload = _base()
    payload["best_bid"] = 101.0
    payload["best_ask"] = 100.0
    result = evaluate_market_data_quality(payload)
    assert result.live_allowed is False
    assert "bid_gt_ask" in result.reasons or "top_of_book_crossed" in result.reasons


def test_missing_candles_blocks_live() -> None:
    payload = _base()
    payload["candles"] = []
    result = evaluate_market_data_quality(payload)
    assert result.live_allowed is False
    assert "candles_missing" in result.reasons


def test_provider_unavailable_blocks_live() -> None:
    payload = _base()
    payload["provider_unavailable"] = True
    result = evaluate_market_data_quality(payload)
    assert result.live_allowed is False
    assert "provider_or_cache_unavailable" in result.reasons

