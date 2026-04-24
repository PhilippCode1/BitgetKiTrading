from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Literal, get_args

from pydantic import BaseModel, Field, field_validator, model_validator

from shared_py.bitget.instruments import BitgetInstrumentIdentity
from shared_py.eventbus.payload_schemas import (
    PAYLOAD_SCHEMA_MAP,
    ensure_payload_matches_schema,
)
from shared_py.replay_determinism import (
    stable_stream_event_id,
    trace_implies_replay_determinism,
)

EventType = Literal[
    "market_tick",
    "market_feed_health",
    "candle_close",
    "funding_update",
    "structure_updated",
    "drawing_updated",
    "signal_created",
    "trade_opened",
    "trade_updated",
    "trade_closed",
    "funding_booked",
    "risk_alert",
    "learning_feedback",
    "strategy_registry_updated",
    "news_item_created",
    "news_scored",
    "llm_failed",
    "dlq",
    "system_alert",
    "operator_intel",
    "tsfm_signal_candidate",
    "onchain_whale_detection",
    "orderbook_inconsistency",
    "orderflow_toxicity",
    "social_sentiment_update",
    "intermarket_correlation_update",
    "regime_divergence_detected",
    "drift_event",
]


def _load_event_streams_catalog() -> dict[str, Any]:
    for base in Path(__file__).resolve().parents:
        path = base / "shared" / "contracts" / "catalog" / "event_streams.json"
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    raise FileNotFoundError(
        "shared/contracts/catalog/event_streams.json nicht gefunden (Monorepo-Root erwartet)."
    )


_CAT = _load_event_streams_catalog()
ENVELOPE_DEFAULT_SCHEMA_VERSION: str = str(_CAT["envelope_default_schema_version"])
_stream_rows: list[dict[str, str]] = list(_CAT["streams"])
EVENT_TYPE_TO_STREAM: dict[str, str] = {
    str(row["event_type"]): str(row["stream"]) for row in _stream_rows
}
EVENT_STREAMS: tuple[str, ...] = tuple(row["stream"] for row in _stream_rows)
LIVE_SSE_STREAMS: tuple[str, ...] = tuple(str(s) for s in _CAT["live_sse_streams"])

for _s in LIVE_SSE_STREAMS:
    if _s not in EVENT_STREAMS:
        raise ValueError(f"live_sse_streams enthaelt unbekannten Stream: {_s}")

if set(EVENT_TYPE_TO_STREAM.keys()) != set(get_args(EventType)):
    raise ValueError(
        "event_streams.json event_types stimmen nicht mit EventType-Literal ueberein (beides anpassen)."
    )
if set(PAYLOAD_SCHEMA_MAP.keys()) != set(get_args(EventType)):
    raise ValueError("payload_schema_map.json Keys != EventType-Literal (Katalog+Schema angleichen).")

STREAM_MARKET_TICK = EVENT_TYPE_TO_STREAM["market_tick"]
STREAM_MARKET_FEED_HEALTH = EVENT_TYPE_TO_STREAM["market_feed_health"]
STREAM_CANDLE_CLOSE = EVENT_TYPE_TO_STREAM["candle_close"]
STREAM_FUNDING_UPDATE = EVENT_TYPE_TO_STREAM["funding_update"]
STREAM_STRUCTURE_UPDATED = EVENT_TYPE_TO_STREAM["structure_updated"]
STREAM_DRAWING_UPDATED = EVENT_TYPE_TO_STREAM["drawing_updated"]
STREAM_SIGNAL_CREATED = EVENT_TYPE_TO_STREAM["signal_created"]
STREAM_TRADE_OPENED = EVENT_TYPE_TO_STREAM["trade_opened"]
STREAM_TRADE_UPDATED = EVENT_TYPE_TO_STREAM["trade_updated"]
STREAM_TRADE_CLOSED = EVENT_TYPE_TO_STREAM["trade_closed"]
STREAM_FUNDING_BOOKED = EVENT_TYPE_TO_STREAM["funding_booked"]
STREAM_RISK_ALERT = EVENT_TYPE_TO_STREAM["risk_alert"]
STREAM_LEARNING_FEEDBACK = EVENT_TYPE_TO_STREAM["learning_feedback"]
STREAM_STRATEGY_REGISTRY_UPDATED = EVENT_TYPE_TO_STREAM["strategy_registry_updated"]
STREAM_NEWS_ITEM_CREATED = EVENT_TYPE_TO_STREAM["news_item_created"]
STREAM_NEWS_SCORED = EVENT_TYPE_TO_STREAM["news_scored"]
STREAM_LLM_FAILED = EVENT_TYPE_TO_STREAM["llm_failed"]
STREAM_DLQ = EVENT_TYPE_TO_STREAM["dlq"]
STREAM_SYSTEM_ALERT = EVENT_TYPE_TO_STREAM["system_alert"]
STREAM_OPERATOR_INTEL = EVENT_TYPE_TO_STREAM["operator_intel"]
STREAM_TSFM_SIGNAL_CANDIDATE = EVENT_TYPE_TO_STREAM["tsfm_signal_candidate"]
STREAM_ONCHAIN_WHALE_DETECTION = EVENT_TYPE_TO_STREAM["onchain_whale_detection"]
STREAM_ORDERBOOK_INCONSISTENCY = EVENT_TYPE_TO_STREAM["orderbook_inconsistency"]
STREAM_ORDERFLOW_TOXICITY = EVENT_TYPE_TO_STREAM["orderflow_toxicity"]
STREAM_SOCIAL_SENTIMENT_UPDATE = EVENT_TYPE_TO_STREAM["social_sentiment_update"]
STREAM_INTERMARKET_CORRELATION_UPDATE = EVENT_TYPE_TO_STREAM["intermarket_correlation_update"]
STREAM_REGIME_DIVERGENCE_DETECTED = EVENT_TYPE_TO_STREAM["regime_divergence_detected"]
STREAM_DRIFT_EVENT = EVENT_TYPE_TO_STREAM["drift_event"]


class EventEnvelope(BaseModel):
    schema_version: str = Field(default=ENVELOPE_DEFAULT_SCHEMA_VERSION)
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType
    symbol: str | None = None
    instrument: BitgetInstrumentIdentity | None = None
    timeframe: str | None = None
    exchange_ts_ms: int | None = None
    ingest_ts_ms: int = Field(default_factory=lambda: int(time.time() * 1000))
    dedupe_key: str | None = None
    payload: dict[str, Any]
    trace: dict[str, Any] = Field(default_factory=dict)
    # Apex: Signal-to-Fill Micro-Tracking (Hops, Nanosekunden) — Katalog: event_envelope.schema.json
    apex_trace: dict[str, Any] = Field(default_factory=dict)

    @field_validator("symbol", mode="before")
    @classmethod
    def _normalize_symbol(cls, value: object) -> object:
        if value is None:
            return None
        normalized = str(value).strip().upper()
        return normalized or None

    @model_validator(mode="after")
    def _finalize_symbol(self) -> EventEnvelope:
        if self.instrument is not None and not self.symbol:
            object.__setattr__(self, "symbol", self.instrument.symbol)
        if not self.symbol:
            payload_symbol = self.payload.get("symbol") if isinstance(self.payload, dict) else None
            if isinstance(payload_symbol, str) and payload_symbol.strip():
                object.__setattr__(self, "symbol", payload_symbol.strip().upper())
        return self

    @model_validator(mode="after")
    def _apply_replay_stable_wire_fields(self) -> EventEnvelope:
        """Replay-Pfad: stabile event_id und ingest_ts_ms (Wire-/Stream-Reproduzierbarkeit)."""
        if not trace_implies_replay_determinism(self.trace):
            return self
        dk = (self.dedupe_key or "").strip()
        if not dk:
            return self
        stream = self.default_stream()
        stable_id = stable_stream_event_id(stream=stream, dedupe_key=dk)
        object.__setattr__(self, "event_id", stable_id)
        if self.exchange_ts_ms is not None:
            object.__setattr__(self, "ingest_ts_ms", int(self.exchange_ts_ms))
        return self

    @model_validator(mode="after")
    def _jsonschema_payload_fail_fast(self) -> EventEnvelope:
        ensure_payload_matches_schema(self.event_type, self.payload)
        return self

    def validate_payload(self) -> None:
        """Prüft die Payload-Instanz gegen jsonschema; wirft SchemaValidationError (Modul
        shared_py.eventbus) bei Regelverletzung.
        """
        ensure_payload_matches_schema(self.event_type, self.payload)

    def default_stream(self) -> str:
        return event_stream_for_type(self.event_type)

    def instrument_key(self) -> str:
        if self.instrument is not None:
            return self.instrument.instrument_key
        s = (self.symbol or "").strip() or "none"
        return f"bitget:unknown:unknown:{s}"

    def canonical_instrument_id(self) -> str | None:
        if self.instrument is None:
            return None
        return self.instrument.canonical_instrument_id


def event_stream_for_type(event_type: EventType) -> str:
    return EVENT_TYPE_TO_STREAM[event_type]
