from __future__ import annotations

from decimal import Decimal

import pytest

from market_stream.collectors.candles import (
    is_timeframe_aligned,
    parse_rest_candle,
    parse_ws_candle,
    timeframe_to_ms,
)


def test_parse_ws_candle_uses_decimal_fields() -> None:
    candle = parse_ws_candle(
        symbol="BTCUSDT",
        timeframe="1m",
        arr=[
            "1710000000000",
            "50000.1",
            "50010.2",
            "49990.3",
            "50005.4",
            "12.34",
            "567890.12",
            "567890.12",
        ],
    )

    assert candle.symbol == "BTCUSDT"
    assert candle.timeframe == "1m"
    assert candle.start_ts_ms == 1710000000000
    assert candle.o == Decimal("50000.1")
    assert candle.h == Decimal("50010.2")
    assert candle.l == Decimal("49990.3")
    assert candle.c == Decimal("50005.4")
    assert candle.base_vol == Decimal("12.34")


def test_parse_rest_candle_accepts_7_value_rows() -> None:
    candle = parse_rest_candle(
        symbol="BTCUSDT",
        timeframe="5m",
        arr=[
            1710000300000,
            "50001",
            "50020",
            "49980",
            "50010",
            "1.5",
            "75000",
        ],
    )

    assert candle.timeframe == "5m"
    assert candle.start_ts_ms == 1710000300000
    assert candle.c == Decimal("50010")
    assert candle.quote_vol == Decimal("75000")
    assert candle.usdt_vol == Decimal("75000")


def test_timeframe_alignment() -> None:
    assert timeframe_to_ms("1m") == 60_000
    assert timeframe_to_ms("4H") == 14_400_000
    assert is_timeframe_aligned(1710000000000, "1m")
    assert not is_timeframe_aligned(1710000000001, "1m")


def test_unknown_timeframe_raises() -> None:
    with pytest.raises(ValueError):
        timeframe_to_ms("2m")
