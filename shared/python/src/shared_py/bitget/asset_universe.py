from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

MarketFamily = Literal["spot", "margin", "futures", "unknown"]
ExchangeStatus = Literal["active", "suspended", "delisted", "unknown"]
GateStatus = Literal["data_ok", "data_stale", "data_quarantined", "data_unknown"]


class BitgetAssetCatalogEntry(BaseModel):
    symbol: str
    base_coin: str | None = None
    quote_coin: str | None = None
    market_family: MarketFamily = "unknown"
    product_type: str | None = None
    margin_coin: str | None = None
    status_on_exchange: ExchangeStatus = "unknown"
    chart_available: bool = False
    trading_available: bool = False
    paper_allowed: bool = False
    shadow_allowed: bool = False
    live_allowed: bool = False
    live_block_reasons: list[str] = Field(default_factory=list)
    tick_size: str | None = None
    lot_size: str | None = None
    min_qty: str | None = None
    min_notional: str | None = None
    price_precision: int | None = None
    quantity_precision: int | None = None
    funding_relevant: bool = False
    open_interest_relevant: bool = False
    last_metadata_refresh_ts: str | None = None
    metadata_source: str = "fixture"
    risk_tier: str = "RISK_TIER_UNKNOWN"
    liquidity_tier: str = "LIQUIDITY_UNKNOWN"
    data_quality_status: GateStatus = "data_unknown"
    operator_note_de: str = ""

    @field_validator("symbol", "base_coin", "quote_coin", "product_type", "margin_coin", mode="before")
    @classmethod
    def _normalize_upper(cls, value: object) -> object:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return text.upper()

    @field_validator("market_family", "status_on_exchange", "data_quality_status", mode="before")
    @classmethod
    def _normalize_lower(cls, value: object) -> object:
        if value is None:
            return value
        return str(value).strip().lower()

    @field_validator("metadata_source", "operator_note_de", mode="before")
    @classmethod
    def _normalize_text(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def with_evaluated_live_gate(self) -> "BitgetAssetCatalogEntry":
        reasons = evaluate_live_block_reasons(self)
        payload = self.model_dump(mode="json")
        payload["live_block_reasons"] = reasons
        payload["live_allowed"] = len(reasons) == 0
        return BitgetAssetCatalogEntry.model_validate(payload)


def evaluate_live_block_reasons(entry: BitgetAssetCatalogEntry) -> list[str]:
    reasons: list[str] = []
    if entry.status_on_exchange in {"delisted", "suspended", "unknown"}:
        reasons.append(f"exchange_status_{entry.status_on_exchange}")
    if entry.market_family == "futures" and not entry.product_type:
        reasons.append("futures_product_type_fehlt")
    if entry.market_family == "futures" and not entry.margin_coin:
        reasons.append("futures_margin_coin_fehlt")
    if not entry.tick_size:
        reasons.append("tick_size_fehlt")
    if not entry.lot_size:
        reasons.append("lot_size_fehlt")
    if entry.risk_tier in {"RISK_TIER_UNKNOWN", ""}:
        reasons.append("risk_tier_unbekannt")
    if entry.data_quality_status != "data_ok":
        reasons.append("datenqualitaet_nicht_ok")
    if not entry.shadow_allowed:
        reasons.append("shadow_nicht_freigegeben")
    # Default fail-closed: neue Assets bleiben blockiert, unabhaengig vom eingehenden live_allowed-Flag.
    if entry.status_on_exchange == "active" and "neu" in entry.operator_note_de.lower():
        reasons.append("neues_asset_nicht_automatisch_live")
    return list(dict.fromkeys(reasons))


def block_reasons_to_german(reasons: list[str]) -> list[str]:
    mapping = {
        "exchange_status_delisted": "Asset ist auf der Boerse delistet.",
        "exchange_status_suspended": "Asset ist auf der Boerse suspendiert.",
        "exchange_status_unknown": "Boersenstatus des Assets ist unklar.",
        "futures_product_type_fehlt": "Futures-Asset ohne ProductType ist gesperrt.",
        "futures_margin_coin_fehlt": "Futures-Asset ohne Margin-Coin ist gesperrt.",
        "tick_size_fehlt": "Tick-Size fehlt; Live-Ausfuehrung ist gesperrt.",
        "lot_size_fehlt": "Lot-Size fehlt; Live-Ausfuehrung ist gesperrt.",
        "risk_tier_unbekannt": "Risk-Tier ist unbekannt; Live bleibt blockiert.",
        "datenqualitaet_nicht_ok": "Datenqualitaet ist nicht data_ok.",
        "shadow_nicht_freigegeben": "Shadow-Modus ist nicht freigegeben.",
        "neues_asset_nicht_automatisch_live": "Neue Assets sind nie automatisch live freigegeben.",
    }
    return [mapping.get(reason, f"Unbekannter Blockgrund: {reason}") for reason in reasons]


@dataclass(frozen=True)
class AssetUniverseSummary:
    total_assets: int
    active_assets: int
    blocked_assets: int
    quarantined_assets: int
    shadow_allowed_assets: int
    live_allowed_assets: int
    market_family_counts: dict[str, int]


def summarize_asset_universe(entries: list[BitgetAssetCatalogEntry]) -> AssetUniverseSummary:
    family_counts = Counter(entry.market_family for entry in entries)
    blocked_assets = sum(1 for entry in entries if not entry.live_allowed)
    quarantined_assets = sum(
        1
        for entry in entries
        if entry.status_on_exchange in {"suspended", "delisted", "unknown"}
    )
    return AssetUniverseSummary(
        total_assets=len(entries),
        active_assets=sum(1 for entry in entries if entry.status_on_exchange == "active"),
        blocked_assets=blocked_assets,
        quarantined_assets=quarantined_assets,
        shadow_allowed_assets=sum(1 for entry in entries if entry.shadow_allowed),
        live_allowed_assets=sum(1 for entry in entries if entry.live_allowed),
        market_family_counts=dict(sorted(family_counts.items())),
    )


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()
