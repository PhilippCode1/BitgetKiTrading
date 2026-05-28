from __future__ import annotations

from shared_py.bitget.order_contract import (
    InstrumentOrderContext,
    InstrumentOrderRequest,
    build_instrument_contract_block_reason_de,
    round_price_to_tick,
    round_qty_to_lot,
    validate_instrument_order_contract,
)


def _context(**overrides: object) -> InstrumentOrderContext:
    payload: dict[str, object] = {
        "symbol": "BTCUSDT",
        "market_family": "futures",
        "product_type": "USDT-FUTURES",
        "margin_coin": "USDT",
        "margin_account_mode": "isolated",
        "tick_size": "0.1",
        "lot_size": "0.001",
        "min_qty": "0.001",
        "min_notional": "5",
        "price_precision": 1,
        "quantity_precision": 3,
        "max_leverage": 20,
        "allowed_order_types": ["limit", "market"],
        "reduce_only_supported": True,
        "post_only_supported": True,
        "source_timestamp": "2026-04-25T16:00:00+00:00",
        "source_freshness_status": "fresh",
    }
    payload.update(overrides)
    return InstrumentOrderContext.model_validate(payload)


def _request(**overrides: object) -> InstrumentOrderRequest:
    payload: dict[str, object] = {
        "symbol": "BTCUSDT",
        "market_family": "futures",
        "product_type": "USDT-FUTURES",
        "margin_coin": "USDT",
        "margin_account_mode": "isolated",
        "order_type": "limit",
        "price": "63000.17",
        "qty": "0.12349",
        "reduce_only": False,
        "requested_leverage": 5,
    }
    payload.update(overrides)
    return InstrumentOrderRequest.model_validate(payload)


def test_futures_without_product_type_blocks() -> None:
    out = validate_instrument_order_contract(
        context=_context(product_type=None), request=_request(product_type=None)
    )
    assert "futures_product_type_fehlt" in out.block_reasons


def test_futures_without_margin_coin_blocks() -> None:
    out = validate_instrument_order_contract(
        context=_context(margin_coin=None), request=_request(margin_coin=None)
    )
    assert "futures_margin_coin_fehlt" in out.block_reasons


def test_spot_with_futures_leverage_context_blocks() -> None:
    out = validate_instrument_order_contract(
        context=_context(
            market_family="spot", max_leverage=None, product_type=None, margin_coin=None
        ),
        request=_request(
            market_family="spot",
            requested_leverage=10,
            product_type=None,
            margin_coin=None,
        ),
    )
    assert "spot_mit_futures_leverage_kontext" in out.block_reasons


def test_price_rounds_to_tick() -> None:
    assert round_price_to_tick("123.47", "0.1") == "123.4"


def test_qty_rounds_to_lot() -> None:
    assert round_qty_to_lot("0.12349", "0.001") == "0.123"


def test_rounding_up_that_increases_risk_is_prevented() -> None:
    out = validate_instrument_order_contract(
        context=_context(tick_size="0.5"), request=_request(price="10.49")
    )
    assert out.rounded_price == "10.0"


def test_min_qty_below_threshold_blocks() -> None:
    out = validate_instrument_order_contract(
        context=_context(min_qty="1"), request=_request(qty="0.5")
    )
    assert "min_qty_unterschritten" in out.block_reasons


def test_min_notional_below_threshold_blocks() -> None:
    out = validate_instrument_order_contract(
        context=_context(min_notional="1000"),
        request=_request(price="10", qty="1"),
    )
    assert "min_notional_unterschritten" in out.block_reasons


def test_stale_metadata_blocks() -> None:
    out = validate_instrument_order_contract(
        context=_context(source_freshness_status="stale"), request=_request()
    )
    assert "instrument_metadaten_stale" in out.block_reasons


def test_product_type_mismatch_blocks() -> None:
    out = validate_instrument_order_contract(
        context=_context(product_type="USDT-FUTURES"),
        request=_request(product_type="COIN-FUTURES"),
    )
    assert "product_type_mismatch" in out.block_reasons


def test_margin_coin_mismatch_blocks() -> None:
    out = validate_instrument_order_contract(
        context=_context(margin_coin="USDT"), request=_request(margin_coin="USDC")
    )
    assert "margin_coin_mismatch" in out.block_reasons


def test_valid_context_preflight_passes_but_not_auto_live_trading() -> None:
    out = validate_instrument_order_contract(context=_context(), request=_request())
    assert out.ok is True


def test_german_block_reasons_generated() -> None:
    text = build_instrument_contract_block_reason_de(
        ["futures_product_type_fehlt", "min_qty_unterschritten"]
    )
    assert any("Futures-Produkt" in item for item in text)
    assert any("Mindestmenge" in item for item in text)
