"""
Letzte Events aus dem Redis-Eventbus (alle registrierten Streams) fuer Incident-RCA.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from redis import Redis

from shared_py.eventbus.envelope import EVENT_STREAMS

_MAX_EXC = 8_000


def sample_event_streams_union_recent(
    redis: Redis,
    *,
    stream_names: Sequence[str] | None = None,
    total_limit: int = 100,
    per_stream_cap: int | None = None,
) -> list[dict[str, Any]]:
    """
    Fasst pro Stream die neuesten Eintraege (XREVRANGE) und waehlt
    insgesamt hoechstens ``total_limit`` (global nach message_id sortiert).
    """
    if stream_names is None:
        names = list(EVENT_STREAMS)
    else:
        name_set = frozenset(EVENT_STREAMS)
        names = [str(s) for s in stream_names if s in name_set]
    nlen = max(1, len(names))
    pcap = per_stream_cap
    if pcap is None:
        pcap = max(2, (total_limit + nlen - 1) // nlen)
    merged: list[tuple[str, str, dict[str, str]]] = []
    for sn in names:
        try:
            batch = redis.xrevrange(
                name=sn,
                max="+",
                min="-",
                count=pcap,
            )
        except Exception:  # noqa: BLE001
            continue
        for eid, fields in batch or ():
            merged.append((sn, str(eid), dict(fields)))
    merged.sort(key=lambda t: t[1], reverse=True)
    out: list[dict[str, Any]] = []
    for sn, eid, fields in merged[: max(0, int(total_limit))]:
        d = (fields or {}).get("data") or ""
        ds = str(d)[:_MAX_EXC]
        env: dict[str, Any] | list[Any] | None = None
        if ds.strip():
            try:
                parsed: Any = json.loads(ds)
                if isinstance(parsed, dict | list):
                    env = parsed
            except (json.JSONDecodeError, OSError, TypeError, ValueError):
                pass
        row: dict[str, Any] = {"stream": sn, "message_id": eid}
        if isinstance(env, dict | list):
            row["envelope"] = env
        else:
            row["data_raw_excerpt"] = ds
        out.append(row)
    return out
