from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

from shared_py.bitget.ws_canonical import BitgetWsCanonicalEvent


class NormalizedEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str
    inst_type: str | None = None
    channel: str | None = None
    inst_id: str | None = None
    action: str
    exchange_ts_ms: int | None = None
    ingest_ts_ms: int = Field(default_factory=lambda: int(time.time() * 1000))
    payload: dict[str, Any]

    @classmethod
    def from_ws_message(
        cls,
        message: dict[str, Any],
        source: str = "bitget_ws_public",
    ) -> NormalizedEvent:
        arg = message.get("arg") if isinstance(message.get("arg"), dict) else {}
        return cls(
            source=source,
            inst_type=_string_or_none(arg.get("instType")),
            channel=_string_or_none(arg.get("channel")),
            inst_id=_string_or_none(arg.get("instId")),
            action=_determine_action(message),
            exchange_ts_ms=extract_exchange_ts_ms(message),
            payload=dict(message),
        )

    def to_canonical(self, *, gap_flag: bool = False) -> BitgetWsCanonicalEvent:
        return BitgetWsCanonicalEvent.from_public_parsed(
            channel=self.channel,
            inst_id=self.inst_id,
            inst_type=self.inst_type,
            action=self.action,
            exchange_ts_ms=self.exchange_ts_ms,
            ingest_ts_ms=self.ingest_ts_ms,
            gap_flag=gap_flag,
        )

    @classmethod
    def from_gapfill_payload(
        cls,
        *,
        inst_type: str,
        channel: str,
        inst_id: str,
        action: str,
        payload: dict[str, Any],
    ) -> NormalizedEvent:
        return cls(
            source="bitget_rest_gapfill",
            inst_type=inst_type,
            channel=channel,
            inst_id=inst_id,
            action=action,
            exchange_ts_ms=extract_exchange_ts_ms(payload),
            payload=payload,
        )


def extract_exchange_ts_ms(message: dict[str, Any]) -> int | None:
    direct_keys = ("ts", "timestamp", "requestTime")
    for key in direct_keys:
        candidate = _to_int(message.get(key))
        if candidate is not None:
            return candidate

    arg = message.get("arg")
    if isinstance(arg, dict):
        for key in direct_keys:
            candidate = _to_int(arg.get(key))
            if candidate is not None:
                return candidate

    data = message.get("data")
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            for key in direct_keys + ("systemTime",):
                candidate = _to_int(first.get(key))
                if candidate is not None:
                    return candidate
        if isinstance(first, list) and first:
            return _to_int(first[0])

    return None


def extract_sequence(message: dict[str, Any]) -> int | None:
    direct = _to_int(message.get("seq"))
    if direct is not None:
        return direct

    data = message.get("data")
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            return _to_int(first.get("seq"))
    return None


def _determine_action(message: dict[str, Any]) -> str:
    event_name = message.get("event")
    if isinstance(event_name, str):
        return "error" if event_name.lower() == "error" else "event"

    action = message.get("action")
    if isinstance(action, str) and action:
        return action

    if "data" in message:
        return "update"
    return "event"


def _to_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if stripped.isdigit():
            return int(stripped)
    return None


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return str(value)
