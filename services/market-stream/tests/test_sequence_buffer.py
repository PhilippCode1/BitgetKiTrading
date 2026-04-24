from __future__ import annotations

import asyncio
from typing import Any

from market_stream.bitget_ws.sequence_buffer import (
    BitgetWsSequenceBuffer,
    lost_sequence_tick_count,
)


def _msg(symbol: str, ch: str, seq: int) -> dict[str, Any]:
    return {
        "arg": {"channel": ch, "instId": symbol},
        "data": [{"seq": seq}],
    }


def test_lost_sequence_tick_count_basic() -> None:
    p = {12: {}, 15: {}}
    assert lost_sequence_tick_count(10, p) == 3  # 11, 13, 14


def extract_seq(m: dict[str, Any]) -> int:
    d = m.get("data")
    if isinstance(d, list) and d and isinstance(d[0], dict):
        return int(d[0]["seq"])
    raise AssertionError(m)


def test_buffer_reorders_after_late_arrival() -> None:
    out_order: list[int] = []

    async def _run() -> None:
        async def on_timeout(_k: str, _l: int) -> None:
            return

        buf = BitgetWsSequenceBuffer(
            gap_buffer_ms=200.0,
            on_gap_timeout=on_timeout,
        )
        k = "candles1m:BTCUSDT"
        a = _msg("BTCUSDT", "candles1m", 1)
        r = await buf.feed(k, a)
        assert [extract_seq(x) for x in r] == [1]
        c = _msg("BTCUSDT", "candles1m", 3)
        r2 = await buf.feed(k, c)
        assert r2 == []
        b = _msg("BTCUSDT", "candles1m", 2)
        r3 = await buf.feed(k, b)
        for x in r3:
            out_order.append(extract_seq(x))
        assert out_order == [2, 3]
        await asyncio.sleep(0.25)

    asyncio.run(_run())


def test_buffer_timeout_fires_lost_one_skipped() -> None:
    lost_from_cb: list[int] = []

    async def _run() -> None:
        async def on_timeout(_k: str, lost: int) -> None:
            lost_from_cb.append(lost)

        buf = BitgetWsSequenceBuffer(
            gap_buffer_ms=50.0,
            on_gap_timeout=on_timeout,
        )
        k = "candles1m:BTCUSDT"
        r0 = await buf.feed(k, _msg("BTCUSDT", "candles1m", 1))
        assert [extract_seq(x) for x in r0] == [1]
        r1 = await buf.feed(k, _msg("BTCUSDT", "candles1m", 3))
        assert r1 == []
        await asyncio.sleep(0.08)
        r2 = await buf.feed(k, _msg("BTCUSDT", "candles1m", 4))
        assert r2
        assert [extract_seq(x) for x in r2] == [4]

    asyncio.run(_run())
    assert lost_from_cb == [1]
