from __future__ import annotations

import logging
import uuid
from typing import Any

from shared_py.bitget.instruments import BitgetInstrumentIdentity
from shared_py.eventbus import EventEnvelope, RedisStreamBus, STREAM_SIGNAL_CREATED
from shared_py.observability.apex_trace import finalize_apex_deltas, new_apex_trace, now_ns, set_hop
from shared_py.replay_determinism import stable_stream_event_id


def publish_signal_created(
    bus: RedisStreamBus,
    *,
    symbol: str,
    timeframe: str,
    payload: dict[str, Any],
    dedupe_key: str | None = None,
    trace: dict[str, Any] | None = None,
    logger: logging.Logger | None = None,
) -> str:
    log = logger or logging.getLogger("signal_engine.publisher")
    t_se0 = now_ns()
    eid = (
        stable_stream_event_id(stream=STREAM_SIGNAL_CREATED, dedupe_key=str(dedupe_key))
        if dedupe_key
        else str(uuid.uuid4())
    )
    instrument = None
    raw_instrument = payload.get("instrument")
    if isinstance(raw_instrument, dict):
        try:
            instrument = BitgetInstrumentIdentity.model_validate(raw_instrument)
        except Exception:
            instrument = None
    t_se1 = now_ns()
    base = new_apex_trace()
    apex = finalize_apex_deltas(set_hop(base, "signal_engine", t_se0, t_se1))
    log.info(
        "apex_signal_engine_ms signal_id=%s deltas_ms=%s",
        payload.get("signal_id"),
        (apex or {}).get("deltas_ms"),
    )
    env = EventEnvelope(
        event_id=eid,
        event_type="signal_created",
        symbol=symbol,
        instrument=instrument,
        timeframe=timeframe,
        exchange_ts_ms=payload.get("analysis_ts_ms"),
        dedupe_key=dedupe_key,
        payload=payload,
        trace=trace or {},
        apex_trace=apex,
    )
    mid = bus.publish(STREAM_SIGNAL_CREATED, env)
    log.info("published signal_created signal_id=%s", payload.get("signal_id"))
    return str(mid)
