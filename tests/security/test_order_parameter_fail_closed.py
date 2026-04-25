from __future__ import annotations

from shared_py.bitget.order_contract import (
    InstrumentOrderContext,
    InstrumentOrderRequest,
    build_instrument_contract_block_reason_de,
    instrument_contract_blocks_live,
    validate_instrument_order_contract,
)


def _context() -> InstrumentOrderContext:
    return InstrumentOrderContext.model_validate(
        {
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
            "allowed_order_types": ["limit"],
            "source_freshness_status": "fresh",
        }
    )


def _request() -> InstrumentOrderRequest:
    return InstrumentOrderRequest.model_validate(
        {
            "symbol": "BTCUSDT",
            "market_family": "futures",
            "product_type": "USDT-FUTURES",
            "margin_coin": "USDT",
            "order_type": "limit",
            "price": "100",
            "qty": "0.1",
        }
    )


def test_fail_closed_on_unknown_precision() -> None:
    context = _context().model_copy(update={"price_precision": None})
    out = validate_instrument_order_contract(context=context, request=_request())
    assert instrument_contract_blocks_live(out) is True


def test_no_secrets_in_error_context() -> None:
    reasons = build_instrument_contract_block_reason_de(["SECRET_TOKEN", "PASSWORD"])
    joined = " ".join(reasons).lower()
    assert "secret" not in joined
    assert "password" not in joined
    assert "***" in " ".join(reasons)
