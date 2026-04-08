from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import redis

logger = logging.getLogger("monitor_engine.redis_streams")


def parse_stream_id_ms(stream_id: str | None) -> int | None:
    """Redis Stream ID: <ms>-<seq>."""
    if not stream_id or stream_id in ("0-0", "0"):
        return None
    try:
        return int(str(stream_id).split("-", 1)[0])
    except (ValueError, IndexError):
        return None


def compute_heuristic_lag(
    *,
    redis_lag: int | None,
    last_generated_id: str | None,
    last_delivered_id: str | None,
) -> int | None:
    """
    Wenn Redis `lag` fehlt (NULL): Differenz der Zeitstempel-Teile der IDs als grobe Heuristik.
    """
    if redis_lag is not None:
        return int(redis_lag)
    g = parse_stream_id_ms(last_generated_id)
    d = parse_stream_id_ms(last_delivered_id)
    if g is None or d is None:
        return None
    return max(0, g - d)


@dataclass
class StreamGroupCheckResult:
    stream: str
    group_name: str
    pending_count: int
    lag: int | None
    last_generated_id: str | None
    last_delivered_id: str | None
    status: str
    details: dict[str, Any]


def _xinfo_stream_meta(r: redis.Redis, stream: str) -> dict[str, Any]:
    try:
        raw = r.xinfo_stream(stream)
        if isinstance(raw, dict):
            return raw
        # redis-py kann Liste liefern
        return dict(zip(raw[::2], raw[1::2]))  # type: ignore[arg-type]
    except Exception as exc:
        logger.debug("xinfo_stream %s: %s", stream, exc)
        return {}


def _xinfo_groups(r: redis.Redis, stream: str) -> list[dict[str, Any]]:
    try:
        raw = r.execute_command("XINFO", "GROUPS", stream)
    except Exception as exc:
        logger.debug("xinfo_groups %s: %s", stream, exc)
        return []
    groups: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            groups.append(item)
        elif isinstance(item, (list, tuple)):
            d: dict[str, Any] = {}
            it = iter(item)
            for k in it:
                d[str(k)] = next(it, None)
            groups.append(d)
    return groups


def _group_entry(groups: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for g in groups:
        gn = g.get("name") or g.get(b"name")
        if isinstance(gn, bytes):
            gn = gn.decode()
        if gn == name:
            return g
    return None


def _pending_summary(r: redis.Redis, stream: str, group: str) -> int:
    try:
        pend = r.execute_command("XPENDING", stream, group)
    except Exception as exc:
        logger.debug("xpending %s %s: %s", stream, group, exc)
        return 0
    if isinstance(pend, (list, tuple)) and pend:
        try:
            return int(pend[0])
        except (TypeError, ValueError):
            return 0
    return 0


def _coerce_lag(val: Any) -> int | None:
    if val is None:
        return None
    if isinstance(val, bytes):
        val = val.decode()
    try:
        if val == "":
            return None
        return int(val)
    except (TypeError, ValueError):
        return None


def check_stream_groups(
    redis_url: str,
    streams: list[str],
    group_names: list[str],
    *,
    thresh_pending: int,
    thresh_lag: int,
) -> list[StreamGroupCheckResult]:
    r = redis.Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    results: list[StreamGroupCheckResult] = []
    for stream in streams:
        meta = _xinfo_stream_meta(r, stream)
        last_gen = meta.get("last-generated-id") or meta.get("last_generated_id")
        if isinstance(last_gen, bytes):
            last_gen = last_gen.decode()
        groups = _xinfo_groups(r, stream)
        for gname in group_names:
            ge = _group_entry(groups, gname)
            if ge is None:
                continue
            pending = _pending_summary(r, stream, gname)
            raw_lag = _coerce_lag(ge.get("lag"))
            last_del = ge.get("last-delivered-id") or ge.get("last_delivered_id")
            if isinstance(last_del, bytes):
                last_del = last_del.decode()
            lag = compute_heuristic_lag(
                redis_lag=raw_lag,
                last_generated_id=str(last_gen) if last_gen else None,
                last_delivered_id=str(last_del) if last_del else None,
            )
            status = "ok"
            if pending > thresh_pending or (lag is not None and lag > thresh_lag):
                status = "degraded"
            if pending > thresh_pending * 5 or (lag is not None and lag > thresh_lag * 5):
                status = "fail"
            results.append(
                StreamGroupCheckResult(
                    stream=stream,
                    group_name=gname,
                    pending_count=pending,
                    lag=lag,
                    last_generated_id=str(last_gen) if last_gen else None,
                    last_delivered_id=str(last_del) if last_del else None,
                    status=status,
                    details={
                        "stream_length": meta.get("length"),
                        "raw_redis_lag": raw_lag,
                    },
                )
            )
    return results


def stream_length(r: redis.Redis, stream: str) -> int:
    try:
        return int(r.xlen(stream))
    except Exception:
        return 0
