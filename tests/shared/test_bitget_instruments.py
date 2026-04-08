from __future__ import annotations

import os

import pytest

from shared_py.bitget import BitgetSettings, endpoint_profile_for


def test_endpoint_profiles_cover_spot_margin_and_futures() -> None:
    fut = endpoint_profile_for("futures")
    spot = endpoint_profile_for("spot")
    margin = endpoint_profile_for("margin", margin_account_mode="isolated")

    assert fut.public_ticker_path == "/api/v2/mix/market/symbol-price"
    assert fut.private_place_order_path == "/api/v2/mix/order/place-order"
    assert fut.private_order_history_path == "/api/v2/mix/order/orders-history"
    assert fut.private_fill_history_path == "/api/v2/mix/order/fill-history"
    assert fut.private_set_leverage_path == "/api/v2/mix/account/set-leverage"
    assert spot.public_ticker_path == "/api/v2/spot/market/tickers"
    assert spot.private_place_order_path == "/api/v2/spot/trade/place-order"
    assert spot.private_order_history_path == "/api/v2/spot/trade/history-orders"
    assert spot.private_fill_history_path == "/api/v2/spot/trade/fills"
    assert margin.private_place_order_path == "/api/v2/margin/isolated/place-order"
    assert margin.uses_spot_public_market_data is True
    assert fut.supports_shorting is True
    assert margin.supports_shorting is True
    assert spot.supports_shorting is False


def test_bitget_settings_build_instrument_identity_and_discovery_symbols(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in list(os.environ.keys()):
        if key.startswith("BITGET_"):
            monkeypatch.delenv(key, raising=False)
    settings = BitgetSettings.model_validate(
        {
            "BITGET_MARKET_FAMILY": "margin",
            "BITGET_MARGIN_ACCOUNT_MODE": "crossed",
            "BITGET_SYMBOL": "ethusdt",
            "BITGET_DISCOVERY_SYMBOLS": "BTCUSDT,ETHUSDT",
            "BITGET_DEMO_ENABLED": "false",
        }
    )
    identity = settings.instrument_identity(metadata_verified=True)

    assert identity.market_family == "margin"
    assert identity.margin_account_mode == "crossed"
    assert identity.symbol == "ETHUSDT"
    assert identity.public_ws_inst_type == "SPOT"
    assert identity.category_key == "bitget:margin:crossed"
    assert identity.canonical_instrument_id == "bitget:margin:crossed:ETHUSDT"
    assert identity.supports_shorting is True
    assert settings.discovery_symbols == ["ETHUSDT", "BTCUSDT"]
