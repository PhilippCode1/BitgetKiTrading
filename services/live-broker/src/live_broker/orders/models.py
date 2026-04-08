from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from shared_py.bitget import ProductType
from shared_py.bitget.instruments import MarginAccountMode, MarketFamily

OrderSourceService = Literal[
    "api-gateway",
    "signal-engine",
    "paper-broker",
    "monitor-engine",
    "manual",
    "live-broker",
]
MarginMode = Literal["isolated", "crossed"]
OrderSide = Literal["buy", "sell"]
TradeSide = Literal["open", "close"]
OrderType = Literal["limit", "market"]
OrderForce = Literal["ioc", "fok", "gtc", "post_only"]
KillSwitchScope = Literal["service", "account", "trade"]


def _normalize_decimal_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    try:
        parsed = Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(f"{field_name} muss numerisch sein") from exc
    if parsed <= 0:
        raise ValueError(f"{field_name} muss > 0 sein")
    return format(parsed, "f")


class OrderCreateRequest(BaseModel):
    internal_order_id: UUID | None = None
    source_service: OrderSourceService = "manual"
    symbol: str
    market_family: MarketFamily | None = None
    product_type: ProductType | None = None
    margin_mode: MarginMode = "isolated"
    margin_account_mode: MarginAccountMode | None = None
    margin_coin: str | None = None
    side: OrderSide
    trade_side: TradeSide | None = None
    order_type: OrderType = "limit"
    force: OrderForce | None = None
    size: str
    price: str | None = None
    reduce_only: bool = False
    preset_stop_surplus_price: str | None = None
    preset_stop_loss_price: str | None = None
    note: str = ""
    trace: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = Field(default=None, max_length=128)
    source_execution_decision_id: UUID | None = None

    @field_validator("correlation_id", mode="before")
    @classmethod
    def _strip_correlation(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            s = value.strip()
            return s or None
        return value

    @field_validator("symbol", mode="before")
    @classmethod
    def _normalize_symbol(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("product_type", mode="before")
    @classmethod
    def _normalize_product_type(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("market_family", mode="before")
    @classmethod
    def _normalize_market_family(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            return normalized or None
        return value

    @field_validator("margin_account_mode", mode="before")
    @classmethod
    def _normalize_margin_account_mode(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            return normalized or None
        return value

    @field_validator("margin_coin", mode="before")
    @classmethod
    def _normalize_margin_coin(cls, value: object) -> object:
        if value is None:
            return None
        normalized = str(value).strip().upper()
        return normalized or None

    @field_validator("trade_side", "note", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("force", mode="before")
    @classmethod
    def _normalize_force(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("size", "price", "preset_stop_surplus_price", "preset_stop_loss_price", mode="before")
    @classmethod
    def _normalize_numeric_values(cls, value: object, info) -> object:
        return _normalize_decimal_text(value, str(info.field_name))

    @field_validator("symbol")
    @classmethod
    def _validate_symbol(cls, value: str) -> str:
        if not value or "_" in value or not value.isalnum():
            raise ValueError("symbol muss Bitget-v2-konform sein")
        return value

    @model_validator(mode="after")
    def _validate_order(self) -> Self:
        if self.order_type == "limit" and self.price is None:
            raise ValueError("limit order braucht price")
        if self.order_type == "market" and self.price is not None:
            raise ValueError("market order darf kein price setzen")
        if self.order_type == "market" and self.force is not None:
            raise ValueError("force ist nur fuer limit orders erlaubt")
        if self.reduce_only and self.trade_side == "open":
            raise ValueError("reduce_only darf nicht mit trade_side=open kombiniert werden")
        return self


class ReduceOnlyOrderRequest(OrderCreateRequest):
    reduce_only: bool = True


class OrderCancelRequest(BaseModel):
    internal_order_id: UUID | None = None
    order_id: str | None = None
    client_oid: str | None = None
    symbol: str | None = None
    market_family: MarketFamily | None = None
    product_type: ProductType | None = None
    margin_coin: str | None = None
    trace: dict[str, Any] = Field(default_factory=dict)

    @field_validator("symbol", mode="before")
    @classmethod
    def _normalize_optional_symbol(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().upper()
            return normalized or None
        return value

    @field_validator("product_type", mode="before")
    @classmethod
    def _normalize_optional_product_type(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().upper()
            return normalized or None
        return value

    @field_validator("market_family", mode="before")
    @classmethod
    def _normalize_cancel_market_family(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            return normalized or None
        return value

    @field_validator("margin_coin", "order_id", "client_oid", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized.upper() if normalized and normalized.isalpha() else normalized or None
        return value

    @model_validator(mode="after")
    def _validate_identity(self) -> Self:
        if not (self.internal_order_id or self.order_id or self.client_oid):
            raise ValueError("cancel request braucht internal_order_id oder order_id oder client_oid")
        return self


class OrderReplaceRequest(BaseModel):
    internal_order_id: UUID
    new_internal_order_id: UUID | None = None
    new_size: str | None = None
    new_price: str | None = None
    new_preset_stop_surplus_price: str | None = None
    new_preset_stop_loss_price: str | None = None
    note: str = ""
    trace: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "new_size",
        "new_price",
        "new_preset_stop_surplus_price",
        "new_preset_stop_loss_price",
        mode="before",
    )
    @classmethod
    def _normalize_numeric_values(cls, value: object, info) -> object:
        return _normalize_decimal_text(value, str(info.field_name))

    @field_validator("note", mode="before")
    @classmethod
    def _normalize_note(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def _validate_replace(self) -> Self:
        if not any(
            (
                self.new_size,
                self.new_price,
                self.new_preset_stop_surplus_price,
                self.new_preset_stop_loss_price,
            )
        ):
            raise ValueError("replace request braucht mindestens eine Aenderung")
        if (self.new_size is None) != (self.new_price is None):
            raise ValueError("Bitget Modify Order verlangt newSize und newPrice gemeinsam")
        return self


class OrderQueryRequest(BaseModel):
    internal_order_id: UUID | None = None
    order_id: str | None = None
    client_oid: str | None = None
    symbol: str | None = None
    market_family: MarketFamily | None = None
    product_type: ProductType | None = None

    @field_validator("symbol", mode="before")
    @classmethod
    def _normalize_optional_symbol(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().upper()
            return normalized or None
        return value

    @field_validator("product_type", mode="before")
    @classmethod
    def _normalize_optional_product_type(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized.upper() if normalized else None
        return value

    @field_validator("market_family", mode="before")
    @classmethod
    def _normalize_query_market_family(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            return normalized or None
        return value

    @field_validator("order_id", "client_oid", mode="before")
    @classmethod
    def _normalize_optional_identity(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @model_validator(mode="after")
    def _validate_query(self) -> Self:
        if not (self.internal_order_id or self.order_id or self.client_oid):
            raise ValueError("query request braucht internal_order_id oder order_id oder client_oid")
        return self


class KillSwitchRequest(BaseModel):
    scope: KillSwitchScope
    source: str = "operator"
    reason: str
    internal_order_id: UUID | None = None
    symbol: str | None = None
    market_family: MarketFamily | None = None
    product_type: ProductType | None = None
    margin_coin: str | None = None
    note: str = ""

    @field_validator(
        "source",
        "reason",
        "note",
        "symbol",
        "margin_coin",
        mode="before",
    )
    @classmethod
    def _normalize_optional_text_fields(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized.isalpha() and normalized.upper() == normalized:
                return normalized
            if normalized.isalpha():
                return normalized
            return normalized or None
        return value

    @field_validator("product_type", mode="before")
    @classmethod
    def _normalize_product_type_for_kill_switch(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().upper()
            return normalized or None
        return value

    @field_validator("market_family", mode="before")
    @classmethod
    def _normalize_kill_switch_market_family(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            return normalized or None
        return value

    @field_validator("symbol", "margin_coin", mode="before")
    @classmethod
    def _normalize_symbol_and_margin_coin(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().upper()
            return normalized or None
        return value

    @model_validator(mode="after")
    def _validate_kill_switch_scope(self) -> Self:
        if self.scope == "trade" and self.internal_order_id is None:
            raise ValueError("trade kill switch braucht internal_order_id")
        if not self.reason:
            raise ValueError("kill switch reason darf nicht leer sein")
        return self


class EmergencyFlattenRequest(BaseModel):
    source_service: OrderSourceService = "manual"
    symbol: str | None = None
    market_family: MarketFamily | None = None
    product_type: ProductType | None = None
    margin_mode: MarginMode = "isolated"
    margin_account_mode: MarginAccountMode | None = None
    margin_coin: str | None = None
    side: OrderSide | None = None
    size: str | None = None
    internal_order_id: UUID | None = None
    cancel_open_orders: bool = True
    reason: str = "emergency_flatten"
    note: str = ""
    trace: dict[str, Any] = Field(default_factory=dict)

    @field_validator("symbol", mode="before")
    @classmethod
    def _normalize_flatten_symbol(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().upper()
            return normalized or None
        return value

    @field_validator("product_type", mode="before")
    @classmethod
    def _normalize_flatten_product_type(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().upper()
            return normalized or None
        return value

    @field_validator("market_family", mode="before")
    @classmethod
    def _normalize_flatten_market_family(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            return normalized or None
        return value

    @field_validator("margin_account_mode", mode="before")
    @classmethod
    def _normalize_flatten_margin_account_mode(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            return normalized or None
        return value

    @field_validator("margin_coin", mode="before")
    @classmethod
    def _normalize_flatten_margin_coin(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().upper()
            return normalized or None
        return value

    @field_validator("size", mode="before")
    @classmethod
    def _normalize_flatten_size(cls, value: object) -> object:
        return _normalize_decimal_text(value, "size")

    @field_validator("reason", "note", mode="before")
    @classmethod
    def _normalize_flatten_text(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @model_validator(mode="after")
    def _validate_emergency_flatten(self) -> Self:
        if not self.reason:
            raise ValueError("emergency flatten reason darf nicht leer sein")
        if (self.side is None) != (self.size is None):
            raise ValueError(
                "emergency flatten braucht side+size gemeinsam oder beides leer fuer Auto-Resolve"
            )
        if self.internal_order_id is None and not self.symbol:
            raise ValueError(
                "emergency flatten braucht symbol oder internal_order_id"
            )
        return self


class CancelAllOrdersRequest(BaseModel):
    """Operatorisches Cancel-All (REST Bitget) — auditierbar, unabhaengig vom Kill-Switch-Auto-Cancel."""

    source: str = "operator"
    reason: str
    market_family: MarketFamily | None = None
    product_type: ProductType | None = None
    margin_coin: str | None = None
    note: str = ""

    @field_validator("source", "reason", "note", mode="before")
    @classmethod
    def _strip_cancel_all_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("product_type", mode="before")
    @classmethod
    def _norm_pt(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper() or None
        return value

    @field_validator("market_family", mode="before")
    @classmethod
    def _norm_cancel_all_family(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower() or None
        return value

    @field_validator("margin_coin", mode="before")
    @classmethod
    def _norm_mc(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper() or None
        return value

    @model_validator(mode="after")
    def _need_reason(self) -> Self:
        if not self.reason:
            raise ValueError("cancel_all reason darf nicht leer sein")
        return self


class SafetyLatchReleaseRequest(BaseModel):
    source: str = "operator"
    reason: str
    note: str = ""

    @field_validator("source", "reason", "note", mode="before")
    @classmethod
    def _strip_latch(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @model_validator(mode="after")
    def _need_reason(self) -> Self:
        if not self.reason:
            raise ValueError("safety latch release reason darf nicht leer sein")
        return self
