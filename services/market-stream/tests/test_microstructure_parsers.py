from __future__ import annotations

from decimal import Decimal

from market_stream.collectors.ticker import _parse_ws_ticker_payload
from market_stream.collectors.trades import parse_trade_record


def test_parse_trade_record_from_dict_payload() -> None:
    trade = parse_trade_record(
        "BTCUSDT",
        {
            "tradeId": "123456",
            "ts": "1700000000000",
            "price": "68123.4",
            "size": "0.015",
            "side": "buy",
        },
    )

    assert trade.symbol == "BTCUSDT"
    assert trade.trade_id == "123456"
    assert trade.ts_ms == 1_700_000_000_000
    assert trade.price == Decimal("68123.4")
    assert trade.size == Decimal("0.015")
    assert trade.side == "buy"


def test_parse_ws_ticker_payload_maps_core_fields() -> None:
    ts_ms, updates = _parse_ws_ticker_payload(
        {
            "ts": "1700000000123",
            "lastPr": "68168.0",
            "bidPr": "68167.9",
            "askPr": "68168.1",
            "bidSz": "1.20",
            "askSz": "0.95",
            "markPrice": "68168.2",
            "indexPrice": "68170.5",
            "fundingRate": "-0.000044",
            "nextFundingTime": "1700006400000",
            "holdingAmount": "28679.976",
            "baseVolume": "10.5",
            "quoteVolume": "715764.0",
        }
    )

    assert ts_ms == 1_700_000_000_123
    assert updates["last_pr"] == Decimal("68168.0")
    assert updates["bid_pr"] == Decimal("68167.9")
    assert updates["ask_pr"] == Decimal("68168.1")
    assert updates["mark_price"] == Decimal("68168.2")
    assert updates["index_price"] == Decimal("68170.5")
    assert updates["funding_rate"] == Decimal("-0.000044")
    assert updates["next_funding_time_ms"] == 1_700_006_400_000
    assert updates["holding_amount"] == Decimal("28679.976")
