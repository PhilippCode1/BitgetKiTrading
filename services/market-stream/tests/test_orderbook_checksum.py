from __future__ import annotations

import pytest

from market_stream.orderbook.book import LocalOrderBook, OrderBookSequenceError
from market_stream.orderbook.checksum import _crc32_signed, build_checksum_string, verify_checksum


def test_build_checksum_string_preserves_original_formatting() -> None:
    bids = [("0.5000", "1.2500")]
    asks = [("0.5001", "2.0000")]

    checksum_string = build_checksum_string(bids, asks, levels=25)

    assert checksum_string == "0.5000:1.2500:0.5001:2.0000"


def test_verify_checksum_and_apply_snapshot_update() -> None:
    book = LocalOrderBook(max_levels=50, checksum_levels=25)
    snapshot_bids = [("100.00", "2.00"), ("99.50", "3.00")]
    snapshot_asks = [("100.50", "1.50"), ("101.00", "4.00")]
    snapshot_checksum = _crc32_signed(
        build_checksum_string(snapshot_bids, snapshot_asks, levels=25)
    )

    view = book.apply_snapshot(
        bids=snapshot_bids,
        asks=snapshot_asks,
        seq=10,
        checksum=snapshot_checksum,
        ts_ms=1_700_000_000_000,
    )

    assert view.seq == 10
    assert verify_checksum(view.bids, view.asks, expected=snapshot_checksum, levels=25)

    updated_bids = [("100.00", "2.50")]
    updated_asks = [("100.75", "1.00")]
    final_bids = [("100.00", "2.50"), ("99.50", "3.00")]
    final_asks = [("100.50", "1.50"), ("100.75", "1.00"), ("101.00", "4.00")]
    update_checksum = _crc32_signed(
        build_checksum_string(final_bids, final_asks, levels=25)
    )

    updated_view = book.apply_update(
        bids=updated_bids,
        asks=updated_asks,
        seq=11,
        checksum=update_checksum,
        ts_ms=1_700_000_000_150,
    )

    assert updated_view.seq == 11
    assert updated_view.bids[0] == ("100.00", "2.50")
    assert updated_view.asks[1] == ("100.75", "1.00")


def test_orderbook_seq_gap_marks_book_desynced() -> None:
    book = LocalOrderBook(
        max_levels=50,
        checksum_levels=25,
        require_contiguous_seq=True,
    )
    bids = [("100.00", "2.00")]
    asks = [("100.50", "1.50")]
    checksum = _crc32_signed(build_checksum_string(bids, asks, levels=25))
    book.apply_snapshot(
        bids=bids,
        asks=asks,
        seq=10,
        checksum=checksum,
        ts_ms=1_700_000_000_000,
    )

    with pytest.raises(OrderBookSequenceError):
        book.apply_update(
            bids=[("99.00", "1.00")],
            asks=[],
            seq=12,
            checksum=None,
            ts_ms=1_700_000_000_150,
        )

    assert book.desynced is True
