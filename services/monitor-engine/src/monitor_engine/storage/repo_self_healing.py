from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg import errors as pg_errors
from psycopg.rows import dict_row

logger = logging.getLogger("monitor_engine.repo_self_healing")

WINDOW_SEC = 3600.0
DEFAULT_MAX_RESTARTS = 3
TIMELINE_MAX = 200


@dataclass(frozen=True)
class SelfHealingStateRow:
    service_name: str
    health_phase: str
    updated_ts_epoch: float | None
    restart_events_ts: list[float]
    timeline: list[dict[str, Any]]


def _row_from_db(r: dict[str, Any]) -> SelfHealingStateRow:
    ev = r.get("restart_events_ts") or []
    if not isinstance(ev, list):
        ev = []
    tl = r.get("timeline") or []
    if not isinstance(tl, list):
        tl = []
    return SelfHealingStateRow(
        service_name=str(r["service_name"]),
        health_phase=str(r["health_phase"]),
        updated_ts_epoch=r.get("updated_ts"),
        restart_events_ts=[float(x) for x in ev],
        timeline=[t for t in tl if isinstance(t, dict)][-TIMELINE_MAX:],
    )


def prune_restart_events(events: list[float], now: float, *, window_sec: float) -> list[float]:
    w = max(1.0, float(window_sec))
    return [t for t in events if now - t < w + 0.5]


def count_allowed_restarts_in_window(
    events: list[float], now: float, *, window_sec: float, max_n: int
) -> tuple[bool, list[float]]:
    pruned = sorted(prune_restart_events(events, now, window_sec=window_sec))[-(max_n + 8) :]
    if len(pruned) >= int(max(1, max_n)):
        return False, pruned
    return True, pruned


def fetch_all_states(dsn: str) -> list[SelfHealingStateRow]:
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT
                      service_name, health_phase,
                      EXTRACT(EPOCH FROM updated_ts)::float AS updated_ts,
                      COALESCE(restart_events_ts, '[]'::jsonb) AS restart_events_ts,
                      COALESCE(timeline, '[]'::jsonb) AS timeline
                    FROM ops.self_healing_state
                    ORDER BY service_name
                    """
                )
                return [_row_from_db(d) for d in cur.fetchall()]
    except pg_errors.Error as exc:
        logger.warning("fetch_all_states failed: %s", exc)
        return []


def get_state(dsn: str, service_name: str) -> SelfHealingStateRow | None:
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT
                      service_name, health_phase,
                      EXTRACT(EPOCH FROM updated_ts)::float AS updated_ts,
                      COALESCE(restart_events_ts, '[]'::jsonb) AS restart_events_ts,
                      COALESCE(timeline, '[]'::jsonb) AS timeline
                    FROM ops.self_healing_state
                    WHERE service_name = %s
                    """,
                    (service_name,),
                )
                row = cur.fetchone()
                return _row_from_db(row) if row else None
    except pg_errors.Error as exc:
        logger.warning("get_state failed service=%s: %s", service_name, exc)
        return None


def _ensure_row(cur: Any, service_name: str) -> None:
    cur.execute(
        """
        INSERT INTO ops.self_healing_state (service_name, health_phase)
        VALUES (%s, 'healthy')
        ON CONFLICT (service_name) DO NOTHING
        """,
        (service_name,),
    )


def _append_timeline_entry(
    timeline: list[dict[str, Any]],
    *,
    event: str,
    message: str,
    details: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    ent: dict[str, Any] = {
        "ts_ms": int(time.time() * 1000),
        "event": event,
        "message": message,
    }
    if details:
        ent["details"] = details
    out = [*timeline, ent]
    return out[-TIMELINE_MAX:]


def set_phase(
    dsn: str,
    service_name: str,
    new_phase: str,
    *,
    event: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> SelfHealingStateRow | None:
    """Nur Phasenwechsel (kein Restart-Zaehler)."""
    try:
        with psycopg.connect(dsn, autocommit=True, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                _ensure_row(cur, service_name)
                cur.execute(
                    "SELECT COALESCE(timeline, '[]'::jsonb) FROM ops.self_healing_state WHERE service_name = %s",
                    (service_name,),
                )
                row = cur.fetchone()
                raw_tl = row[0] if row else []
                if isinstance(raw_tl, str):
                    raw_tl = json.loads(raw_tl)
                tl0 = [t for t in raw_tl if isinstance(t, dict)] if isinstance(raw_tl, list) else []
                new_tl = _append_timeline_entry(
                    tl0, event=event, message=message, details=details
                )
                cur.execute(
                    """
                    UPDATE ops.self_healing_state
                    SET
                      health_phase = %s,
                      timeline = %s::jsonb,
                      last_event_detail = %s::jsonb,
                      updated_ts = now()
                    WHERE service_name = %s
                    """,
                    (new_phase, json.dumps(new_tl), json.dumps({"event": event}), service_name),
                )
        return get_state(dsn, service_name)
    except Exception as exc:
        logger.warning("set_phase failed %s: %s", service_name, exc)
        return None


def try_begin_restart(
    dsn: str,
    service_name: str,
    *,
    max_restarts: int = DEFAULT_MAX_RESTARTS,
    window_sec: float = WINDOW_SEC,
    from_phase_required: str | None = "degraded",
    timeline_message: str = "RECOVERY_REQUESTED: Phase recovering (Rate-Check ok)",
    timeline_source: str = "ops_restart",
) -> tuple[bool, str, SelfHealingStateRow | None]:
    """
    Wechsel zu recovering, wenn Rate-Limit zulaesst und (optional) Phasen-Match.

    from_phase_required:
      None  -> jede Phase (Auto-Coordinator, sobald Kritisch)
      'degraded' -> manuell aus Dashboard (nur von degraded)
    """
    return _try_begin_restart_impl(
        dsn,
        service_name,
        from_phase_required,
        time.time(),
        max_restarts,
        window_sec,
        timeline_message=timeline_message,
        timeline_source=timeline_source,
    )


def _try_begin_restart_impl(
    dsn: str,
    service_name: str,
    from_phase_required: str | None,
    now: float,
    max_restarts: int,
    window_sec: float,
    *,
    timeline_message: str,
    timeline_source: str,
) -> tuple[bool, str, SelfHealingStateRow | None]:
    try:
        with psycopg.connect(dsn, autocommit=False, connect_timeout=5) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                _ensure_row(cur, service_name)
                cur.execute(
                    """
                    SELECT
                      service_name, health_phase,
                      EXTRACT(EPOCH FROM updated_ts)::float AS updated_ts,
                      COALESCE(restart_events_ts, '[]'::jsonb) AS restart_events_ts,
                      COALESCE(timeline, '[]'::jsonb) AS timeline
                    FROM ops.self_healing_state
                    WHERE service_name = %s
                    FOR UPDATE
                    """,
                    (service_name,),
                )
                row = cur.fetchone()
                if not row:
                    conn.rollback()
                    return False, "not_found", None
                st = _row_from_db(row)
                if st.health_phase == "recovering":
                    conn.rollback()
                    return (False, "already_recovering", st)
                if from_phase_required and st.health_phase != from_phase_required:
                    conn.rollback()
                    return (
                        False,
                        f"phase_mismatch:expected={from_phase_required!r} got={st.health_phase!r}",
                        st,
                    )
                allow, pruned = count_allowed_restarts_in_window(
                    st.restart_events_ts, now, window_sec=window_sec, max_n=max_restarts
                )
                if not allow:
                    conn.rollback()
                    return False, "restart_rate_limited", st
                new_restarts = [*pruned, now]
                raw_tl: Any = row.get("timeline")
                if raw_tl is None or isinstance(raw_tl, str):
                    if isinstance(raw_tl, str):
                        try:
                            raw_tl = json.loads(raw_tl)
                        except Exception:
                            raw_tl = []
                    else:
                        raw_tl = []
                assert isinstance(raw_tl, (list, tuple)) or raw_tl is None
                if not isinstance(raw_tl, list):
                    raw_tl = []
                tl0 = [t for t in raw_tl if isinstance(t, dict)]
                new_tl = _append_timeline_entry(
                    tl0,
                    event="RECOVERY_REQUESTED",
                    message=timeline_message,
                    details={"source": timeline_source},
                )
                cur.execute(
                    """
                    UPDATE ops.self_healing_state
                    SET
                      health_phase = 'recovering',
                      last_restart_ts = to_timestamp(%s::double precision),
                      restart_events_ts = %s::jsonb,
                      timeline = %s::jsonb,
                      last_event_detail = %s::jsonb,
                      updated_ts = now()
                    WHERE service_name = %s
                    """,
                    (
                        now,
                        json.dumps(new_restarts[-10:]),
                        json.dumps(new_tl),
                        json.dumps({"phase": "recovering"}),
                        service_name,
                    ),
                )
            conn.commit()
    except Exception as exc:
        logger.warning("try_begin_restart failed: %s", exc)
        return False, f"error:{str(exc)[:200]}", None
    st2 = get_state(dsn, service_name)
    return True, "ok", st2
