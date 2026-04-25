from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Literal

from pydantic import BaseModel, Field, field_validator

MarketFamily = Literal["spot", "margin", "futures"]
FreshnessStatus = Literal["fresh", "stale", "unknown"]


class InstrumentOrderContext(BaseModel):
    symbol: str
    market_family: MarketFamily
    product_type: str | None = None
    margin_coin: str | None = None
    margin_account_mode: str | None = None
    tick_size: str | None = None
    lot_size: str | None = None
    min_qty: str | None = None
    min_notional: str | None = None
    price_precision: int | None = None
    quantity_precision: int | None = None
    max_leverage: int | None = None
    allowed_order_types: list[str] = Field(default_factory=list)
    reduce_only_supported: bool = False
    post_only_supported: bool = False
    source_timestamp: str | None = None
    source_freshness_status: FreshnessStatus = "unknown"

    @field_validator(
        "symbol",
        "product_type",
        "margin_coin",
        "margin_account_mode",
        "tick_size",
        "lot_size",
        "min_qty",
        "min_notional",
        "source_timestamp",
        mode="before",
    )
    @classmethod
    def _normalize_text(cls, value: object) -> object:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return text.upper() if text.replace("-", "").isalnum() else text


class InstrumentOrderRequest(BaseModel):
    symbol: str
    market_family: MarketFamily
    product_type: str | None = None
    margin_coin: str | None = None
    margin_account_mode: str | None = None
    order_type: str = "limit"
    price: str
    qty: str
    reduce_only: bool = False
    requested_leverage: int | None = None

    @field_validator("symbol", "product_type", "margin_coin", "margin_account_mode", mode="before")
    @classmethod
    def _normalize_upper(cls, value: object) -> object:
        if value is None:
            return None
        return str(value).strip().upper()

    @field_validator("order_type", mode="before")
    @classmethod
    def _normalize_order_type(cls, value: object) -> str:
        return str(value or "limit").strip().lower()


@dataclass(frozen=True)
class OrderContractValidationResult:
    ok: bool
    rounded_price: str | None
    rounded_qty: str | None
    block_reasons: list[str]


def _to_decimal(value: str | None) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def round_price_to_tick(price: str, tick_size: str) -> str:
    p = Decimal(price)
    tick = Decimal(tick_size)
    rounded = (p / tick).to_integral_value(rounding=ROUND_DOWN) * tick
    return format(rounded, "f")


def round_qty_to_lot(qty: str, lot_size: str) -> str:
    q = Decimal(qty)
    lot = Decimal(lot_size)
    rounded = (q / lot).to_integral_value(rounding=ROUND_DOWN) * lot
    return format(rounded, "f")


def validate_min_qty_and_notional(*, qty: str, price: str, min_qty: str, min_notional: str) -> list[str]:
    reasons: list[str] = []
    q = _to_decimal(qty)
    p = _to_decimal(price)
    min_q = _to_decimal(min_qty)
    min_n = _to_decimal(min_notional)
    if q is None or p is None or min_q is None or min_n is None:
        reasons.append("min_pruefung_konnte_nicht_berechnet_werden")
        return reasons
    if q < min_q:
        reasons.append("min_qty_unterschritten")
    if (q * p) < min_n:
        reasons.append("min_notional_unterschritten")
    return reasons


def validate_instrument_order_contract(
    *,
    context: InstrumentOrderContext,
    request: InstrumentOrderRequest,
) -> OrderContractValidationResult:
    reasons: list[str] = []
    if request.symbol != context.symbol:
        reasons.append("symbol_mismatch")
    if context.market_family == "futures" and not context.product_type:
        reasons.append("futures_product_type_fehlt")
    if context.market_family == "futures" and not context.margin_coin:
        reasons.append("futures_margin_coin_fehlt")
    if context.market_family == "margin" and not context.margin_account_mode:
        reasons.append("margin_account_mode_fehlt")
    if context.market_family == "spot" and request.requested_leverage not in (None, 0, 1):
        reasons.append("spot_mit_futures_leverage_kontext")
    if context.source_freshness_status in {"stale", "unknown"}:
        reasons.append("instrument_metadaten_stale")
    if request.product_type and context.product_type and request.product_type != context.product_type:
        reasons.append("product_type_mismatch")
    if request.margin_coin and context.margin_coin and request.margin_coin != context.margin_coin:
        reasons.append("margin_coin_mismatch")
    if context.price_precision is None or context.quantity_precision is None:
        reasons.append("unknown_precision")
    if not context.tick_size:
        reasons.append("tick_size_fehlt")
    if not context.lot_size:
        reasons.append("lot_size_fehlt")
    if request.order_type not in {item.lower() for item in context.allowed_order_types}:
        reasons.append("order_type_nicht_erlaubt")

    rounded_price = None
    rounded_qty = None
    if context.tick_size and context.lot_size:
        rounded_price = round_price_to_tick(request.price, context.tick_size)
        rounded_qty = round_qty_to_lot(request.qty, context.lot_size)
        # Niemals risk-erhoehend aufrunden.
        if Decimal(rounded_price) > Decimal(request.price) or Decimal(rounded_qty) > Decimal(request.qty):
            reasons.append("risk_erhoehendes_rounding_verboten")
        if context.min_qty and context.min_notional:
            reasons.extend(
                validate_min_qty_and_notional(
                    qty=rounded_qty,
                    price=rounded_price,
                    min_qty=context.min_qty,
                    min_notional=context.min_notional,
                )
            )
    return OrderContractValidationResult(
        ok=len(reasons) == 0,
        rounded_price=rounded_price,
        rounded_qty=rounded_qty,
        block_reasons=list(dict.fromkeys(reasons)),
    )


def instrument_contract_blocks_live(result: OrderContractValidationResult) -> bool:
    return not result.ok


def build_instrument_contract_block_reason_de(reasons: list[str]) -> list[str]:
    mapping = {
        "symbol_mismatch": "Symbol im Auftrag passt nicht zum Instrumentkontext.",
        "futures_product_type_fehlt": "Futures-Produkt ohne ProductType ist gesperrt.",
        "futures_margin_coin_fehlt": "Futures-Produkt ohne Margin-Coin ist gesperrt.",
        "margin_account_mode_fehlt": "Margin-Produkt ohne AccountMode ist gesperrt.",
        "spot_mit_futures_leverage_kontext": "Spot-Order darf keinen Futures-Leverage-Kontext verwenden.",
        "instrument_metadaten_stale": "Instrument-Metadaten sind stale oder unbekannt.",
        "product_type_mismatch": "ProductType im Signal passt nicht zum Instrumentkontext.",
        "margin_coin_mismatch": "Margin-Coin im Signal passt nicht zum Instrumentkontext.",
        "unknown_precision": "Preis- oder Mengen-Precision ist unbekannt.",
        "tick_size_fehlt": "Tick-Size fehlt im Instrumentkontext.",
        "lot_size_fehlt": "Lot-Size fehlt im Instrumentkontext.",
        "order_type_nicht_erlaubt": "Order-Typ ist fuer dieses Instrument nicht erlaubt.",
        "risk_erhoehendes_rounding_verboten": "Rundung darf das Risiko nicht erhoehen.",
        "min_qty_unterschritten": "Mindestmenge unterschritten.",
        "min_notional_unterschritten": "Mindestnotional unterschritten.",
        "min_pruefung_konnte_nicht_berechnet_werden": "Mindestpruefung konnte nicht sicher berechnet werden.",
    }
    out: list[str] = []
    for reason in reasons:
        out.append(mapping.get(reason, f"Unbekannter Blockgrund: {reason}"))
    # Keine sensiblen Werte im Fehlerkontext.
    sanitized = [item.replace("SECRET", "***").replace("TOKEN", "***").replace("PASSWORD", "***") for item in out]
    return sanitized
