from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, Field

from shared_py.bitget.ws_canonical import BitgetWsCanonicalEvent

EventType = Literal["order", "fill", "position", "account", "unknown"]


class NormalizedPrivateEvent(BaseModel):
    event_type: EventType
    inst_id: str
    inst_type: str | None = None
    channel: str
    action: str = "snapshot"
    arg_json: dict[str, Any] = Field(default_factory=dict)
    ingest_ts_ms: int = Field(default_factory=lambda: int(time.time() * 1000))
    exchange_ts_ms: int
    data: list[dict[str, Any]]

    @classmethod
    def from_ws_message(cls, message: dict[str, Any]) -> NormalizedPrivateEvent:
        arg = message.get("arg", {})
        channel = arg.get("channel", "unknown")
        inst_id = arg.get("instId", arg.get("coin", "default"))
        action = str(message.get("action", "snapshot") or "snapshot")
        data = message.get("data", [])
        
        # Bitget private WS liefert manchmal 'ts' als string, manchmal integer
        ts_val = message.get("ts", int(time.time() * 1000))
        try:
            exchange_ts_ms = int(ts_val)
        except (ValueError, TypeError):
            exchange_ts_ms = int(time.time() * 1000)

        event_type: EventType = "unknown"
        if channel == "orders":
            event_type = "order"
        elif channel == "fill":
            event_type = "fill"
        elif channel == "positions":
            event_type = "position"
        elif channel == "account":
            event_type = "account"

        return cls(
            event_type=event_type,
            inst_id=inst_id,
            inst_type=arg.get("instType"),
            channel=channel,
            action=action,
            arg_json=arg if isinstance(arg, dict) else {},
            exchange_ts_ms=exchange_ts_ms,
            data=data,
        )

    def to_canonical(self, *, gap_flag: bool = False) -> BitgetWsCanonicalEvent:
        return BitgetWsCanonicalEvent.from_private_parsed(
            channel=self.channel,
            inst_id=self.inst_id,
            inst_type=self.inst_type,
            action=self.action,
            exchange_ts_ms=self.exchange_ts_ms,
            ingest_ts_ms=self.ingest_ts_ms,
            gap_flag=gap_flag,
        )
