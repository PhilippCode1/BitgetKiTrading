"""
Gemeinsames, schema-stabiles WebSocket-Ereignis-Envelope fuer Bitget v2 (public + private).

Dient Observability, Health und spaetere Aggregation — nicht fuer Hot-Path-Publishing erforderlich.
"""

from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, Field

BitgetWsDomain = Literal[
    "ticker",
    "candles",
    "orderbook",
    "trades",
    "order",
    "fill",
    "position",
    "account",
    "unknown",
]

BitgetWsPlane = Literal["public", "private"]


def infer_ws_domain(*, plane: BitgetWsPlane, channel: str) -> BitgetWsDomain:
    ch = (channel or "").strip().lower()
    if plane == "private":
        if ch == "orders":
            return "order"
        if ch == "fill":
            return "fill"
        if ch == "positions":
            return "position"
        if ch == "account":
            return "account"
        return "unknown"
    if ch in ("ticker", "tickers"):
        return "ticker"
    if ch.startswith("candle") or ch == "candles":
        return "candles"
    if ch.startswith("books") or ch == "books" or ch == "books5":
        return "orderbook"
    if ch in ("trade", "trades"):
        return "trades"
    return "unknown"


class BitgetWsCanonicalEvent(BaseModel):
    """Einheitliche Sicht auf ein Bitget-WS-Datenpush-Event (nach Parse)."""

    schema_version: int = 1
    plane: BitgetWsPlane
    channel: str
    inst_id: str = ""
    inst_type: str | None = None
    action: str = "update"
    domain: BitgetWsDomain = "unknown"
    exchange_ts_ms: int | None = None
    ingest_ts_ms: int = Field(default_factory=lambda: int(time.time() * 1000))
    gap_flag: bool = False

    @classmethod
    def from_public_parsed(
        cls,
        *,
        channel: str | None,
        inst_id: str | None,
        inst_type: str | None,
        action: str,
        exchange_ts_ms: int | None,
        ingest_ts_ms: int,
        gap_flag: bool = False,
    ) -> BitgetWsCanonicalEvent:
        ch = (channel or "unknown").strip() or "unknown"
        iid = (inst_id or "").strip() or ""
        dom = infer_ws_domain(plane="public", channel=ch)
        return cls(
            plane="public",
            channel=ch,
            inst_id=iid,
            inst_type=inst_type,
            action=action or "update",
            domain=dom,
            exchange_ts_ms=exchange_ts_ms,
            ingest_ts_ms=ingest_ts_ms,
            gap_flag=gap_flag,
        )

    @classmethod
    def from_private_parsed(
        cls,
        *,
        channel: str,
        inst_id: str,
        inst_type: str | None,
        action: str,
        exchange_ts_ms: int,
        ingest_ts_ms: int,
        gap_flag: bool = False,
    ) -> BitgetWsCanonicalEvent:
        ch = (channel or "unknown").strip() or "unknown"
        iid = (inst_id or "").strip() or "default"
        dom = infer_ws_domain(plane="private", channel=ch)
        return cls(
            plane="private",
            channel=ch,
            inst_id=iid,
            inst_type=inst_type,
            action=action or "snapshot",
            domain=dom,
            exchange_ts_ms=exchange_ts_ms,
            ingest_ts_ms=ingest_ts_ms,
            gap_flag=gap_flag,
        )

    def approx_latency_ms(self) -> int | None:
        if self.exchange_ts_ms is None:
            return None
        d = self.ingest_ts_ms - int(self.exchange_ts_ms)
        if d < 0 or d > 120_000:
            return None
        return int(d)


def canonical_from_raw_public_message(
    message: dict[str, Any],
    *,
    ingest_ts_ms: int,
    gap_flag: bool = False,
) -> BitgetWsCanonicalEvent:
    """Parse arg + action aus Rohtext-JSON (wie von Bitget WS)."""
    arg = message.get("arg") if isinstance(message.get("arg"), dict) else {}
    ch = arg.get("channel")
    inst = arg.get("instId")
    it = arg.get("instType")
    action = str(message.get("action") or "update")
    ex_ts: int | None = None
    for key in ("ts", "timestamp"):
        v = message.get(key)
        if v is not None:
            try:
                ex_ts = int(v)
                break
            except (TypeError, ValueError):
                pass
    return BitgetWsCanonicalEvent.from_public_parsed(
        channel=str(ch) if ch is not None else None,
        inst_id=str(inst) if inst is not None else None,
        inst_type=str(it) if isinstance(it, str) else None,
        action=action,
        exchange_ts_ms=ex_ts,
        ingest_ts_ms=ingest_ts_ms,
        gap_flag=gap_flag,
    )
