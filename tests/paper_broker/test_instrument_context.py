from __future__ import annotations

from paper_broker.engine.instrument_context import (
    execution_context_for_position,
    instrument_hints_from_signal,
)


def test_instrument_hints_from_signal_extracts() -> None:
    h = instrument_hints_from_signal(
        {
            "market_family": "MARGIN",
            "product_type": "USDT",
            "canonical_instrument_id": "bitget:margin:FOO",
            "margin_account_mode": "ISOLATED",
        }
    )
    assert h["market_family"] == "margin"
    assert h["product_type"] == "USDT"
    assert "FOO" in h["canonical_instrument_id"]


def test_execution_context_merges_catalog() -> None:
    ctx = execution_context_for_position(
        {"market_family": "futures"},
        catalog_entry_dict={
            "symbol": "BTCUSDT",
            "canonical_instrument_id": "c1",
            "market_family": "futures",
            "product_type": "USDT-FUTURES",
            "trading_status": "normal",
        },
    )
    assert ctx["canonical_instrument_id"] == "c1"
    assert ctx["product_type"] == "USDT-FUTURES"
