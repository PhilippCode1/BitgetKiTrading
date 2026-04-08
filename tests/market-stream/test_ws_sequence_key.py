from __future__ import annotations

from market_stream.bitget_ws.client import _sequence_tracking_key


def test_sequence_key_skips_orderbook_channels() -> None:
    assert _sequence_tracking_key({"arg": {"channel": "books", "instId": "BTCUSDT"}}) is None
    assert _sequence_tracking_key({"arg": {"channel": "books5", "instId": "BTCUSDT"}}) is None


def test_sequence_key_per_channel_inst() -> None:
    assert _sequence_tracking_key({"arg": {"channel": "trade", "instId": "BTCUSDT"}}) == "trade:BTCUSDT"
    assert _sequence_tracking_key({"arg": {"channel": "ticker", "instId": "BTCUSDT"}}) == "ticker:BTCUSDT"
