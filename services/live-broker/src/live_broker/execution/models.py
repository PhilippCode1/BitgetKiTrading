from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from shared_py.bitget.instruments import MarginAccountMode, MarketFamily
from shared_py.signal_contracts import SignalDirection

IntentSource = Literal[
    "api-gateway",
    "signal-engine",
    "paper-broker",
    "monitor-engine",
    "manual",
    "live-broker",
]
RequestedRuntimeMode = Literal["shadow", "live"]
OrderType = Literal["market", "limit"]


def _normalize_optional_str(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _validate_positive_decimal(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{field_name} muss numerisch sein") from exc
    if parsed <= 0:
        raise ValueError(f"{field_name} muss > 0 sein")
    return format(parsed, "f")


class ExecutionIntentRequest(BaseModel):
    source_service: IntentSource = "api-gateway"
    signal_id: str | None = None
    symbol: str
    market_family: MarketFamily | None = None
    margin_account_mode: MarginAccountMode | None = None
    timeframe: str | None = None
    direction: SignalDirection = "neutral"
    requested_runtime_mode: RequestedRuntimeMode = "shadow"
    leverage: int | None = None
    approved_7x: bool = False
    qty_base: str | None = None
    order_type: OrderType = "market"
    entry_price: str | None = None
    stop_loss: str | None = None
    take_profit: str | None = None
    note: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    trace: dict[str, Any] = Field(default_factory=dict)

    @field_validator("symbol", mode="before")
    @classmethod
    def _normalize_symbol(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("timeframe", "signal_id", "note", mode="before")
    @classmethod
    def _normalize_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
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

    @field_validator("timeframe", "signal_id", mode="after")
    @classmethod
    def _empty_text_to_none(cls, value: str | None) -> str | None:
        return _normalize_optional_str(value)

    @field_validator("direction", mode="before")
    @classmethod
    def _normalize_direction(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("requested_runtime_mode", mode="before")
    @classmethod
    def _normalize_runtime_mode(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("order_type", mode="before")
    @classmethod
    def _normalize_order_type(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("leverage")
    @classmethod
    def _validate_leverage(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value < 7 or value > 75:
            raise ValueError("leverage muss im Bereich 7..75 liegen")
        return value

    @field_validator(
        "qty_base",
        "entry_price",
        "stop_loss",
        "take_profit",
        mode="before",
    )
    @classmethod
    def _normalize_numeric_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        if value is None:
            return None
        return str(value)

    @field_validator("qty_base")
    @classmethod
    def _validate_qty(cls, value: str | None) -> str | None:
        return _validate_positive_decimal(value, "qty_base")

    @field_validator("entry_price")
    @classmethod
    def _validate_entry_price(cls, value: str | None) -> str | None:
        return _validate_positive_decimal(value, "entry_price")

    @field_validator("stop_loss")
    @classmethod
    def _validate_stop_loss(cls, value: str | None) -> str | None:
        return _validate_positive_decimal(value, "stop_loss")

    @field_validator("take_profit")
    @classmethod
    def _validate_take_profit(cls, value: str | None) -> str | None:
        return _validate_positive_decimal(value, "take_profit")

    @field_validator("symbol")
    @classmethod
    def _validate_symbol(cls, value: str) -> str:
        if not value or "_" in value or not value.isalnum():
            raise ValueError("symbol muss Bitget-v2-konform sein")
        return value

    @field_validator("note")
    @classmethod
    def _truncate_note(cls, value: str) -> str:
        return value[:500]

    @field_validator("payload", "trace")
    @classmethod
    def _ensure_dict(cls, value: dict[str, Any]) -> dict[str, Any]:
        return dict(value)

    def model_post_init(self, __context: Any) -> None:
        if self.order_type == "limit" and self.entry_price is None:
            raise ValueError("limit orders brauchen entry_price")


OperatorReleaseSource = Literal["internal-api", "telegram_operator"]


class OperatorReleasePostBody(BaseModel):
    """Optionale Audit-Metadaten fuer operator_release (z. B. Telegram-Zweistufen-Flow)."""

    source: OperatorReleaseSource = "internal-api"
    audit: dict[str, Any] = Field(default_factory=dict)

    @field_validator("audit")
    @classmethod
    def _audit_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 40:
            raise ValueError("audit darf hoechstens 40 Keys haben")
        return value
