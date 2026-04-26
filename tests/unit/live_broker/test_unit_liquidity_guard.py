from __future__ import annotations

from decimal import Decimal

import pytest

from live_broker.execution.liquidity_guard import (
    InsufficientLiquidityError,
    verify_execution_liquidity,
)


def test_orderbook_staleness_blocks_submit() -> None:
    snapshot = {
        "ts_ms": 1_000,
        "bids": [["100", "2"]],
        "asks": [["101", "2"]],
    }
    with pytest.raises(InsufficientLiquidityError, match="orderbook stale"):
        verify_execution_liquidity(
            "BTCUSDT",
            Decimal("0.1"),
            "buy",
            redis_url="",
            strict=True,
            now_ts_ms=30_000,
            max_orderbook_age_ms=5_000,
            _snapshot=snapshot,
        )
