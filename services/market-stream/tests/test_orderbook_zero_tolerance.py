from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from market_stream.orderbook.book import LocalOrderBook, OrderBookChecksumError
from market_stream.orderbook.checksum import (
    _crc32_signed,
    build_checksum_string,
    compute_bitget_orderbook_crc32,
)


def test_interleaved_string_matches_cascade_style() -> None:
    b = [("0.1", "1.0"), ("0.0", "2.0")]
    a = [("0.2", "3.0")]
    s = build_checksum_string(b, a, levels=3)
    assert s == "0.1:1.0:0.2:3.0:0.0:2.0"
    c1 = _crc32_signed(s)
    c2 = compute_bitget_orderbook_crc32(b, a, levels=3)
    assert c1 == c2


def test_manipulated_wire_checksum_raises_and_desyncs() -> None:
    """Falsches WS-checksum: lokaler CRC != Draht -> Desync."""
    book = LocalOrderBook(max_levels=50, checksum_levels=25)
    bids0 = [("100.0", "2.0")]
    asks0 = [("100.5", "1.5")]
    sc = _crc32_signed(build_checksum_string(bids0, asks0, levels=25))
    book.apply_snapshot(
        bids=bids0,
        asks=asks0,
        seq=10,
        checksum=sc,
        ts_ms=1_700_000_000_000,
    )
    with pytest.raises(OrderBookChecksumError):
        book.apply_update(
            bids=[],
            asks=[("100.5", "0.0")],  # entfernt Ask, Buch aendert sich
            seq=11,
            checksum=1_111_111_111,  # bewusst falsch (kein echter Draht)
            ts_ms=1_700_000_000_001,
        )
    assert book.desynced
    assert "mismatch" in (book.desync_reason or "")


def test_cascade_crc_parity_apex() -> None:
    try:
        from apex_core import orderbook_crc32_signed  # type: ignore[import-not-found]
    except ImportError:
        return
    b = [("1", "2")]
    a = [("3", "4")]
    s = build_checksum_string(b, a, levels=5)
    pyv = _crc32_signed(s)
    native = int(orderbook_crc32_signed(s))
    assert native == pyv


def test_rebuild_from_rest_restores_book() -> None:
    from shared_py.bitget import BitgetSettings

    from market_stream.collectors.orderbook import OrderbookCollector

    async def _run() -> None:
        settings = BitgetSettings(
            market_family="futures",
            product_type="USDT-FUTURES",
            symbol="BTCUSDT",
        )
        repo = MagicMock()
        repo.connect = AsyncMock()
        repo.insert_snapshot = AsyncMock(return_value=True)
        repo.close = AsyncMock()
        slippage = MagicMock()
        slippage.connect = AsyncMock()
        slippage.close = AsyncMock()
        slippage.publish = AsyncMock(return_value="0-0")
        slippage.set_json = AsyncMock(return_value=True)
        c = OrderbookCollector(
            bitget_settings=settings,
            orderbook_repo=repo,
            slippage_sink=slippage,
            max_levels=50,
            checksum_levels=25,
            resync_on_mismatch=True,
            slippage_sizes_usdt=[1_000],
        )
        ok = await c.rebuild_from_rest_payload(
            {
                "bids": [["100.0", "1.0"]],
                "asks": [["100.1", "2.0"]],
                "ts": "1_800_000_000_000",
            }
        )
        assert ok is True
        assert c._book.desynced is False
        assert c._orderbook_repo.insert_snapshot.called

    asyncio.run(_run())


def test_resync_log_message() -> None:
    """Beweis-String im Runtime-Pfad (app): siehe _resync_orderbook."""
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / "src" / "market_stream" / "app.py"
    text = p.read_text(encoding="utf-8")
    assert "Desynchronized - Rebuilding" in text
    assert "fetch_resync_orderbook_json" in text
    assert "market:locked:" in text
