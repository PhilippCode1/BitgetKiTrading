"""
Apex Core: Signal-to-Fill-Latenz-Mikro-Tracking (Nanosekunden, Service-Hops).

Struktur ``apex_trace`` (EventEnvelope + DB app.apex_latency_audit):
- ``trace_id``: Korrelation
- ``hops``: pro Service { t_enter_ns, t_exit_ns } (Austritt optional bis Hop abgeschlossen)
- ``deltas_ms``: Paar-Differenzen entlang APEX_HOP_ORDER (nur vorhandene Hops)
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Final

logger = logging.getLogger("shared_py.observability.apex_trace")

# Reihenfolge fuer Delta-Kette (institutioneller Hotpath; api_gateway optional)
APEX_HOP_ORDER: Final[tuple[str, ...]] = (
    "signal_engine",
    "message_queue",
    "api_gateway",
    "live_broker",
    "bitget",
)


def now_ns() -> int:
    return time.time_ns()


def new_apex_trace(*, trace_id: str | None = None) -> dict[str, Any]:
    tid = (trace_id or str(uuid.uuid4())).strip() or str(uuid.uuid4())
    return {"trace_id": tid, "hops": {}, "deltas_ms": {}}


def _ensure(apex: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(apex, dict):
        return new_apex_trace()
    out = dict(apex)
    if "hops" not in out or not isinstance(out["hops"], dict):
        out["hops"] = {}
    if "deltas_ms" not in out or not isinstance(out["deltas_ms"], dict):
        out["deltas_ms"] = {}
    if not (out.get("trace_id") or ""):
        out["trace_id"] = str(uuid.uuid4())
    return out


def set_hop(
    apex: dict[str, Any] | None,
    name: str,
    t_enter_ns: int,
    t_exit_ns: int | None = None,
) -> dict[str, Any]:
    out = _ensure(apex)
    h = dict(out["hops"])
    entry: dict[str, int] = {"t_enter_ns": int(t_enter_ns)}
    if t_exit_ns is not None:
        entry["t_exit_ns"] = int(t_exit_ns)
    h[str(name).strip() or "unknown"] = entry
    out["hops"] = h
    return out


def close_hop(apex: dict[str, Any] | None, name: str, t_exit_ns: int) -> dict[str, Any]:
    out = _ensure(apex)
    h = dict(out["hops"])
    key = str(name).strip()
    cur = h.get(key)
    if not isinstance(cur, dict):
        cur = {}
    cur["t_exit_ns"] = int(t_exit_ns)
    h[key] = cur
    out["hops"] = h
    return out


def finalize_apex_deltas(apex: dict[str, Any] | None) -> dict[str, Any]:
    """
    Setzt ``deltas_ms[prev->name]`` (Kettenabstand) und ``{name}_self_ms`` (Wandzeit im Hop).
    """
    out = _ensure(apex)
    hops: dict[str, Any] = out.get("hops") or {}
    if not isinstance(hops, dict):
        hops = {}
    dm: dict[str, float] = {}
    prev_point: int | None = None
    prev_name: str | None = None
    for name in APEX_HOP_ORDER:
        hop = hops.get(name)
        if not isinstance(hop, dict):
            continue
        t_in = hop.get("t_enter_ns")
        t_out = hop.get("t_exit_ns")
        if t_in is None:
            continue
        t_in_i = int(t_in)
        t_out_i = int(t_out) if t_out is not None else None
        if prev_point is not None and prev_name is not None:
            k = f"{prev_name}->{name}"
            try:
                dm[k] = round((t_in_i - prev_point) / 1_000_000.0, 6)
            except Exception:
                dm[k] = 0.0
        if t_out_i is not None:
            try:
                dm[f"{name}_self_ms"] = round((t_out_i - t_in_i) / 1_000_000.0, 6)
            except Exception:
                dm[f"{name}_self_ms"] = 0.0
            prev_point = t_out_i
        else:
            prev_point = t_in_i
        prev_name = name
    out["deltas_ms"] = dm
    return out


def log_apex_chain_ms(apex: dict[str, Any] | None, *, stage: str) -> None:
    fin = finalize_apex_deltas(apex)
    hops = fin.get("hops") or {}
    dm = fin.get("deltas_ms") or {}
    logger.info(
        "apex_chain_ms stage=%s trace_id=%s hop_count=%s deltas_ms=%s",
        stage,
        fin.get("trace_id"),
        len(hops) if isinstance(hops, dict) else 0,
        dm,
    )


def merge_gateway_response_apex(
    body: Any,
    *,
    t_gw0_ns: int,
    t_gw1_ns: int,
) -> Any:
    """Fuer api-gateway: dict-Response mit apex_trace erweitern/mergen."""
    if not isinstance(body, dict):
        return body
    raw = body.get("apex_trace")
    base: dict[str, Any] = raw if isinstance(raw, dict) else {}
    merged = set_hop(base, "api_gateway", t_gw0_ns, t_gw1_ns)
    merged = finalize_apex_deltas(merged)
    return {**body, "apex_trace": merged}
