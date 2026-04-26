from __future__ import annotations

from typing import Any

from shared_py.bitget.instruments import BitgetInstrumentCatalogEntry

FAMILY_RUNTIME_CASES: list[dict[str, Any]] = [
    {
        "name": "spot_btcusdt",
        "symbol": "BTCUSDT",
        "market_family": "spot",
        "product_type": None,
        "margin_account_mode": "cash",
        "maker_fee_rate": "0.0010",
        "taker_fee_rate": "0.0010",
        "size_multiplier": "0.0001",
        "price_end_step": "0.01",
        "fund_interval_hours": 0,
        "max_lever": 1,
        "spread_bps": 3.0,
    },
    {
        "name": "margin_btcusdt_crossed",
        "symbol": "BTCUSDT",
        "market_family": "margin",
        "product_type": None,
        "margin_account_mode": "crossed",
        "maker_fee_rate": "0.0008",
        "taker_fee_rate": "0.0010",
        "size_multiplier": "0.0001",
        "price_end_step": "0.01",
        "fund_interval_hours": 0,
        "max_lever": 3,
        "spread_bps": 4.0,
    },
    {
        "name": "futures_btcusdt_usdt",
        "symbol": "BTCUSDT",
        "market_family": "futures",
        "product_type": "USDT-FUTURES",
        "margin_account_mode": "crossed",
        "maker_fee_rate": "0.0002",
        "taker_fee_rate": "0.0006",
        "size_multiplier": "0.001",
        "price_end_step": "0.1",
        "fund_interval_hours": 8,
        "max_lever": 50,
        "spread_bps": 1.0,
    },
    {
        "name": "futures_btcusd_coin",
        "symbol": "BTCUSD",
        "market_family": "futures",
        "product_type": "COIN-FUTURES",
        "margin_account_mode": "crossed",
        "maker_fee_rate": "0.0002",
        "taker_fee_rate": "0.0006",
        "size_multiplier": "1",
        "price_end_step": "0.5",
        "fund_interval_hours": 8,
        "max_lever": 75,
        "spread_bps": 6.0,
    },
]


def catalog_entry_for_case(case: dict[str, Any]) -> BitgetInstrumentCatalogEntry:
    return BitgetInstrumentCatalogEntry(
        market_family=case["market_family"],
        symbol=case["symbol"],
        product_type=case["product_type"],
        margin_account_mode=case["margin_account_mode"],
        public_ws_inst_type=(case["product_type"] or case["market_family"]).upper(),
        private_ws_inst_type=(case["product_type"] or case["market_family"]).upper(),
        metadata_source="tests.family_runtime_matrix",
        metadata_verified=True,
        trading_status="normal",
        trading_enabled=True,
        subscribe_enabled=True,
        quantity_step=str(case["size_multiplier"]),
        price_tick_size=str(case["price_end_step"]),
        funding_interval_hours=case["fund_interval_hours"],
        leverage_max=case["max_lever"],
        quantity_min="0.001",
        min_notional_quote="5",
    )
