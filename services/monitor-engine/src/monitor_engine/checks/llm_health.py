from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import redis

from shared_py.eventbus.envelope import STREAM_DLQ, STREAM_LLM_FAILED

logger = logging.getLogger("monitor_engine.llm_health")


@dataclass
class LlmHealthResult:
    dlq_len: int
    llm_failed_last_id: str | None
    llm_failed_last_ts_ms: int | None
    status: str
    details: dict[str, Any]


def _last_stream_entry_ts_ms(r: redis.Redis, stream: str) -> tuple[str | None, int | None]:
    try:
        entries = r.xrevrange(stream, max="+", min="-", count=1)
    except Exception as exc:
        logger.debug("xrevrange %s: %s", stream, exc)
        return None, None
    if not entries:
        return None, None
    msg_id, fields = entries[0]
    raw = fields.get("data") or fields.get(b"data")
    if isinstance(raw, bytes):
        raw = raw.decode()
    # ingest_ts_ms aus Envelope — ohne JSON-Parse schwer; nutze ID-Zeitstempel
    ts = None
    try:
        ts = int(str(msg_id).split("-")[0])
    except (ValueError, IndexError):
        pass
    return str(msg_id), ts


def check_llm_streams(
    redis_url: str,
    *,
    warn_dlq: int,
    crit_dlq: int,
    stale_llm_ms: int,
    now_ms: int,
) -> LlmHealthResult:
    r = redis.Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    try:
        dlq_len = int(r.xlen(STREAM_DLQ))
    except Exception:
        dlq_len = 0
    last_id, last_ts = _last_stream_entry_ts_ms(r, STREAM_LLM_FAILED)

    status = "ok"
    if dlq_len >= crit_dlq:
        status = "critical"
    elif dlq_len >= warn_dlq:
        status = "warn"

    if last_ts is not None and (now_ms - last_ts) < stale_llm_ms and dlq_len >= warn_dlq:
        # viele Fehler in kurzer Zeit
        status = "critical"

    return LlmHealthResult(
        dlq_len=dlq_len,
        llm_failed_last_id=last_id,
        llm_failed_last_ts_ms=last_ts,
        status=status,
        details={"stream_dlq": STREAM_DLQ, "stream_llm_failed": STREAM_LLM_FAILED},
    )
