from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator
from shared_py.bitget.instruments import (
    BitgetInstrumentIdentity,
    MarginAccountMode,
    MarketFamily,
    market_category_key,
    normalize_market_eligibility_flags,
)


class StrategyLifecycleStatus(str, Enum):
    promoted = "promoted"
    candidate = "candidate"
    shadow = "shadow"
    retired = "retired"


def _ensure_json_object(name: str, v: Any) -> dict[str, Any]:
    if v is None:
        return {}
    if not isinstance(v, dict):
        raise ValueError(f"{name} muss ein JSON-Objekt sein")
    return v


class StrategyScope(BaseModel):
    venue: str = "bitget"
    symbol: str = ""
    market_family: MarketFamily | None = None
    canonical_instrument_id: str | None = None
    category_key: str | None = None
    product_type: str | None = None
    margin_coin: str | None = None
    margin_account_mode: MarginAccountMode = "isolated"
    base_coin: str | None = None
    quote_coin: str | None = None
    settle_coin: str | None = None
    metadata_source: str = "strategy_registry"
    metadata_verified: bool = False
    inventory_visible: bool = False
    analytics_eligible: bool = False
    paper_shadow_eligible: bool = False
    live_execution_enabled: bool = False
    execution_disabled: bool = False
    supports_funding: bool = False
    supports_open_interest: bool = False
    supports_long_short: bool = False
    supports_shorting: bool = False
    supports_reduce_only: bool = False
    supports_leverage: bool = False
    timeframes: list[str] = Field(default_factory=list)

    @field_validator("venue", "canonical_instrument_id", "category_key", "metadata_source", mode="before")
    @classmethod
    def _text(cls, v: Any) -> Any:
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    @field_validator("symbol")
    @classmethod
    def _sym(cls, v: str) -> str:
        s = v.strip().upper()
        return s

    @field_validator("market_family", mode="before")
    @classmethod
    def _family(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip().lower()
        return s or None

    @field_validator("product_type", mode="before")
    @classmethod
    def _product_type(cls, v: Any) -> Any:
        if v is None:
            return None
        s = str(v).strip().upper()
        return s or None

    @field_validator("margin_coin", "base_coin", "quote_coin", "settle_coin", mode="before")
    @classmethod
    def _coin(cls, v: Any) -> Any:
        if v is None:
            return None
        s = str(v).strip().upper()
        return s or None

    @field_validator("margin_account_mode", mode="before")
    @classmethod
    def _margin_mode(cls, v: str) -> str:
        s = v.strip().lower()
        if not s:
            raise ValueError("margin_account_mode leer")
        return s

    def model_post_init(self, __context: Any) -> None:
        if not self.symbol:
            cid = str(self.canonical_instrument_id or "").strip()
            if cid and ":" in cid:
                object.__setattr__(self, "symbol", cid.rsplit(":", 1)[-1].strip().upper())
        if self.market_family is None:
            if self.product_type:
                object.__setattr__(self, "market_family", "futures")
            elif self.margin_account_mode not in (None, "cash"):
                object.__setattr__(self, "market_family", "margin")
            elif self.category_key:
                parts = str(self.category_key).split(":")
                if len(parts) >= 2 and parts[1] in {"spot", "margin", "futures"}:
                    object.__setattr__(self, "market_family", parts[1])
            elif self.canonical_instrument_id:
                parts = str(self.canonical_instrument_id).split(":")
                if len(parts) >= 2 and parts[1] in {"spot", "margin", "futures"}:
                    object.__setattr__(self, "market_family", parts[1])
        if self.market_family is None:
            object.__setattr__(self, "market_family", "spot")
        if self.market_family == "spot":
            object.__setattr__(self, "margin_account_mode", "cash")
        if self.market_family == "futures" and not self.product_type:
            inferred = None
            for raw_value in (self.category_key, self.canonical_instrument_id):
                parts = str(raw_value or "").split(":")
                if len(parts) >= 3 and parts[2]:
                    inferred = parts[2].strip().upper()
                    break
            if inferred:
                object.__setattr__(self, "product_type", inferred)
        supports_shorting = bool(self.supports_shorting or self.supports_long_short)
        object.__setattr__(self, "supports_shorting", supports_shorting)
        object.__setattr__(self, "supports_long_short", supports_shorting)
        inventory, analytics, paper_shadow, live_enabled, execution_off = (
            normalize_market_eligibility_flags(
                inventory_visible=self.inventory_visible,
                analytics_eligible=self.analytics_eligible,
                paper_shadow_eligible=self.paper_shadow_eligible,
                live_execution_enabled=self.live_execution_enabled,
                execution_disabled=self.execution_disabled,
            )
        )
        object.__setattr__(self, "inventory_visible", inventory)
        object.__setattr__(self, "analytics_eligible", analytics)
        object.__setattr__(self, "paper_shadow_eligible", paper_shadow)
        object.__setattr__(self, "live_execution_enabled", live_enabled)
        object.__setattr__(self, "execution_disabled", execution_off)
        if not self.category_key:
            object.__setattr__(
                self,
                "category_key",
                market_category_key(
                    venue=self.venue,
                    market_family=self.market_family,
                    product_type=self.product_type,
                    margin_account_mode=self.margin_account_mode,
                ),
            )
        if not self.symbol:
            raise ValueError("symbol leer")
        if self.market_family == "futures" and not self.product_type:
            raise ValueError("product_type leer fuer futures scope")
        if not self.canonical_instrument_id:
            product = self.product_type or self.margin_account_mode
            object.__setattr__(
                self,
                "canonical_instrument_id",
                f"{self.venue}:{self.market_family}:{product}:{self.symbol}",
            )

    def instrument_identity(self) -> BitgetInstrumentIdentity:
        return BitgetInstrumentIdentity(
            venue=self.venue,
            market_family=self.market_family,
            symbol=self.symbol,
            canonical_instrument_id=self.canonical_instrument_id,
            category_key=self.category_key,
            product_type=self.product_type,
            margin_coin=self.margin_coin,
            margin_account_mode=self.margin_account_mode,
            base_coin=self.base_coin,
            quote_coin=self.quote_coin,
            settle_coin=self.settle_coin,
            public_ws_inst_type=self.product_type if self.market_family == "futures" else "SPOT",
            private_ws_inst_type=(
                self.product_type
                if self.market_family == "futures"
                else ("MARGIN" if self.market_family == "margin" else "SPOT")
            ),
            metadata_source=self.metadata_source,
            metadata_verified=self.metadata_verified,
            inventory_visible=self.inventory_visible,
            analytics_eligible=self.analytics_eligible,
            paper_shadow_eligible=self.paper_shadow_eligible,
            live_execution_enabled=self.live_execution_enabled,
            execution_disabled=self.execution_disabled,
            supports_funding=self.supports_funding,
            supports_open_interest=self.supports_open_interest,
            supports_long_short=self.supports_long_short,
            supports_shorting=self.supports_shorting,
            supports_reduce_only=self.supports_reduce_only,
            supports_leverage=self.supports_leverage,
            uses_spot_public_market_data=self.market_family in {"spot", "margin"},
        )


class CreateStrategyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    description: str = ""
    scope: StrategyScope

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("name leer")
        return s


class AddVersionRequest(BaseModel):
    version: str = Field(..., min_length=1, max_length=64)
    definition: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    risk_profile: dict[str, Any] = Field(default_factory=dict)

    @field_validator("definition")
    @classmethod
    def _def(cls, v: Any) -> dict[str, Any]:
        return _ensure_json_object("definition", v)

    @field_validator("parameters")
    @classmethod
    def _par(cls, v: Any) -> dict[str, Any]:
        return _ensure_json_object("parameters", v)

    @field_validator("risk_profile")
    @classmethod
    def _risk(cls, v: Any) -> dict[str, Any]:
        return _ensure_json_object("risk_profile", v)


class SetStatusRequest(BaseModel):
    new_status: StrategyLifecycleStatus
    reason: str | None = None
    changed_by: str = Field(default="user", min_length=1, max_length=128)
    manual_override: bool = False


ALLOWED_TRANSITIONS: set[tuple[str, str]] = {
    ("shadow", "candidate"),
    ("candidate", "promoted"),
    ("promoted", "retired"),
    ("retired", "shadow"),
}


def transition_allowed(old: str | None, new: str) -> bool:
    if old == new:
        return False
    if old is None:
        return False
    return (old, new) in ALLOWED_TRANSITIONS


def requires_promotion_manual_override(old: str, new: str) -> bool:
    return old == "candidate" and new == "promoted"
