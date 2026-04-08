from __future__ import annotations

import hashlib
import logging
from typing import Any

from shared_py.eventbus import EventEnvelope, RedisStreamBus, STREAM_LLM_FAILED

logger = logging.getLogger("llm_orchestrator.events")


def _symbol_from_trace(trace: dict[str, Any] | None) -> str:
    if not isinstance(trace, dict):
        return "GLOBAL"
    instrument = trace.get("instrument")
    if isinstance(instrument, dict):
        symbol = str(instrument.get("symbol") or "").strip().upper()
        if symbol:
            return symbol
    symbol = str(trace.get("symbol") or "").strip().upper()
    return symbol or "GLOBAL"


def publish_llm_failed(
    bus: RedisStreamBus,
    *,
    schema_hash: str,
    input_hash: str,
    error: str,
    providers_tried: list[str],
    trace: dict[str, Any] | None = None,
) -> str:
    dedupe_raw = f"{schema_hash}:{input_hash}:{error[:200]}"
    dedupe_key = hashlib.sha256(dedupe_raw.encode("utf-8")).hexdigest()[:48]
    env = EventEnvelope(
        event_type="llm_failed",
        symbol=_symbol_from_trace(trace),
        timeframe=None,
        exchange_ts_ms=None,
        dedupe_key=dedupe_key,
        payload={
            "schema_hash": schema_hash,
            "input_hash": input_hash,
            "error": error[:2000],
            "providers_tried": providers_tried,
        },
        trace=trace or {"source": "llm-orchestrator"},
    )
    mid = bus.publish(STREAM_LLM_FAILED, env)
    logger.warning("llm_failed event published id=%s", mid)
    return str(mid)
