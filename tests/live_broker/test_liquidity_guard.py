from __future__ import annotations

from decimal import Decimal

import pytest

from live_broker.execution.liquidity_guard import (
    InsufficientLiquidityError,
    verify_execution_liquidity,
)


def _thin_book() -> dict:
    """Dünnes Orderbook: in Top-5 Asks max. 0,5 BTC kumulativ -> 10 BTC nicht füllbar."""
    return {
        "ts_ms": 1_700_000_000_000,
        "bids": [
            ["100000.0", "1.0"],
            ["99990.0", "1.0"],
            ["99980.0", "1.0"],
            ["99970.0", "1.0"],
            ["99960.0", "1.0"],
        ],
        "asks": [
            ["100100.0", "0.1"],
            ["100200.0", "0.1"],
            ["100300.0", "0.1"],
            ["100400.0", "0.1"],
            ["100500.0", "0.1"],
        ],
    }


def test_small_market_buy_passes_on_thin_book() -> None:
    verify_execution_liquidity(
        "BTCUSDT",
        Decimal("0.01"),
        "buy",
        redis_url="",
        _snapshot=_thin_book(),
    )


def test_large_market_buy_rejected_on_thin_book() -> None:
    with pytest.raises(InsufficientLiquidityError, match="Blocked by Liquidity Guard"):
        verify_execution_liquidity(
            "BTCUSDT",
            Decimal("10"),
            "buy",
            redis_url="",
            _snapshot=_thin_book(),
        )


def test_slippage_too_high_blocks() -> None:
    """Auch voll gedeckte Size: wenn VWAP >50 bps weg vom Mid, blocken."""
    snap: dict = {
        "ts_ms": 1,
        "bids": [["100000.0", "20.0"], ["90000.0", "1"]],
        "asks": [
            ["200000.0", "5.0"],
            ["250000.0", "5.0"],
        ],
    }
    with pytest.raises(InsufficientLiquidityError, match="slippage"):
        verify_execution_liquidity(
            "BTCUSDT",
            Decimal("1"),
            "buy",
            redis_url="",
            max_slippage_bps=Decimal("50"),
            _snapshot=snap,
        )
