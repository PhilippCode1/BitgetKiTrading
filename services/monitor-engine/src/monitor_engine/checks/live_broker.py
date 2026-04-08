from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

from monitor_engine.checks.services_http import ServiceCheckResult

_KILL_SWITCH_STATE_EVENT_TYPES = ("arm", "release")
_KILL_SWITCH_HARD_SCOPES = {"service", "account"}


def build_live_broker_service_checks(
    snapshot: dict[str, Any],
    *,
    now_ms: int,
    reconcile_stale_ms: int,
    kill_switch_age_ms: int,
) -> list[ServiceCheckResult]:
    latest_reconcile = snapshot.get("latest_reconcile")
    active_kill_switches = snapshot.get("active_kill_switches") or []
    critical_audits = snapshot.get("critical_audits") or []
    order_status_counts = snapshot.get("order_status_counts") or {}
    last_fill_created_ts = snapshot.get("last_fill_created_ts")
    last_fill_age_ms = (
        _age_ms(last_fill_created_ts, now_ms=now_ms)
        if last_fill_created_ts is not None
        else None
    )

    reconcile_status = "fail"
    reconcile_details: dict[str, Any] = {
        "latest_status": None,
        "latest_reconcile_created_ts": None,
        "latest_reconcile_age_ms": None,
        "latest_reconcile_drift_total": 0,
        "order_status_counts": order_status_counts,
        "last_fill_created_ts": _iso(last_fill_created_ts),
        "last_fill_age_ms": last_fill_age_ms,
    }
    if isinstance(latest_reconcile, dict):
        latest_status = str(latest_reconcile.get("status") or "").strip().lower() or None
        created_ts = latest_reconcile.get("created_ts")
        age_ms = _age_ms(created_ts, now_ms=now_ms)
        details_json = _coerce_json_dict(latest_reconcile.get("details_json"))
        drift = _coerce_json_dict(details_json.get("drift"))
        drift_total = int(drift.get("total_count") or 0)
        reconcile_details.update(
            {
                "latest_status": latest_status,
                "latest_reconcile_created_ts": _iso(created_ts),
                "latest_reconcile_age_ms": age_ms,
                "latest_reconcile_drift_total": drift_total,
            }
        )
        if age_ms is not None and age_ms > reconcile_stale_ms:
            reconcile_status = "fail"
        elif latest_status == "fail":
            reconcile_status = "fail"
        elif latest_status and latest_status != "ok":
            reconcile_status = "degraded"
        else:
            reconcile_status = "ok"

    kill_switch_count = len(active_kill_switches)
    kill_switch_status = "ok"
    kill_switch_details: dict[str, Any] = {
        "active_kill_switch_count": kill_switch_count,
        "active_kill_switches": [
            {
                "scope": item.get("scope"),
                "scope_key": item.get("scope_key"),
                "reason": item.get("reason"),
                "source": item.get("source"),
                "created_ts": _iso(item.get("created_ts")),
            }
            for item in active_kill_switches[:10]
            if isinstance(item, dict)
        ],
    }
    if kill_switch_count:
        max_age_ms = max(
            (_age_ms(item.get("created_ts"), now_ms=now_ms) or 0)
            for item in active_kill_switches
            if isinstance(item, dict)
        )
        kill_switch_details["max_active_kill_switch_age_ms"] = max_age_ms
        scopes = {
            str(item.get("scope") or "")
            for item in active_kill_switches
            if isinstance(item, dict)
        }
        if scopes & _KILL_SWITCH_HARD_SCOPES:
            kill_switch_status = "fail"
        elif max_age_ms > kill_switch_age_ms:
            kill_switch_status = "fail"
        else:
            kill_switch_status = "degraded"

    audit_status = "ok" if not critical_audits else "fail"
    audit_details: dict[str, Any] = {
        "critical_audit_count": len(critical_audits),
        "recent_critical_audits": [
            {
                "category": item.get("category"),
                "action": item.get("action"),
                "scope": item.get("scope"),
                "scope_key": item.get("scope_key"),
                "symbol": item.get("symbol"),
                "created_ts": _iso(item.get("created_ts")),
            }
            for item in critical_audits[:10]
            if isinstance(item, dict)
        ],
    }

    shadow_live = snapshot.get("shadow_live_stats") or {}
    gate_blocks_24h = int(shadow_live.get("gate_blocks_24h") or 0)
    match_failures_24h = int(shadow_live.get("match_failures_24h") or 0)
    require_shadow = False
    if isinstance(latest_reconcile, dict):
        details_json = _coerce_json_dict(latest_reconcile.get("details_json"))
        ec = _coerce_json_dict(details_json.get("execution_controls"))
        require_shadow = bool(ec.get("require_shadow_match_before_live"))

    shadow_live_status = "ok"
    shadow_live_details: dict[str, Any] = {
        "require_shadow_match_before_live": require_shadow,
        "gate_blocks_24h": gate_blocks_24h,
        "match_failures_24h": match_failures_24h,
    }
    if require_shadow and gate_blocks_24h >= 1:
        shadow_live_status = "degraded"
    elif require_shadow and match_failures_24h >= 3:
        shadow_live_status = "degraded"

    safety_latch_active = bool(snapshot.get("safety_latch_active"))
    safety_latch_status = "fail" if safety_latch_active else "ok"
    safety_latch_details: dict[str, Any] = {
        "safety_latch_active": safety_latch_active,
        "note": "Live-Fire blockiert bis operatorisches POST /live-broker/safety/safety-latch/release",
    }

    return [
        ServiceCheckResult(
            service_name="live-broker",
            check_type="reconcile",
            status=reconcile_status,
            latency_ms=None,
            details=reconcile_details,
        ),
        ServiceCheckResult(
            service_name="live-broker",
            check_type="kill_switch",
            status=kill_switch_status,
            latency_ms=None,
            details=kill_switch_details,
        ),
        ServiceCheckResult(
            service_name="live-broker",
            check_type="audit",
            status=audit_status,
            latency_ms=None,
            details=audit_details,
        ),
        ServiceCheckResult(
            service_name="live-broker",
            check_type="shadow_live_divergence",
            status=shadow_live_status,
            latency_ms=None,
            details=shadow_live_details,
        ),
        ServiceCheckResult(
            service_name="live-broker",
            check_type="safety_latch",
            status=safety_latch_status,
            latency_ms=None,
            details=safety_latch_details,
        ),
    ]


def load_live_broker_service_checks(
    dsn: str,
    *,
    reconcile_stale_ms: int,
    error_lookback_ms: int,
    kill_switch_age_ms: int,
    now_ms: int | None = None,
) -> list[ServiceCheckResult]:
    current_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
    snapshot = load_live_broker_snapshot(
        dsn,
        error_lookback_ms=error_lookback_ms,
        now_ms=current_ms,
    )
    return build_live_broker_service_checks(
        snapshot,
        now_ms=current_ms,
        reconcile_stale_ms=reconcile_stale_ms,
        kill_switch_age_ms=kill_switch_age_ms,
    )


def load_live_broker_snapshot(
    dsn: str,
    *,
    error_lookback_ms: int,
    now_ms: int,
) -> dict[str, Any]:
    cutoff = datetime.fromtimestamp(
        max(0, now_ms - error_lookback_ms) / 1000,
        tz=timezone.utc,
    )
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        latest_reconcile = conn.execute(
            """
            SELECT status, created_ts, details_json
            FROM live.reconcile_snapshots
            ORDER BY created_ts DESC
            LIMIT 1
            """
        ).fetchone()
        active_kill_switches = conn.execute(
            """
            SELECT *
            FROM (
                SELECT DISTINCT ON (scope, scope_key) *
                FROM live.kill_switch_events
                WHERE event_type = ANY(%s)
                ORDER BY scope, scope_key, created_ts DESC
            ) latest
            WHERE is_active = true
            ORDER BY created_ts DESC
            LIMIT 20
            """,
            (list(_KILL_SWITCH_STATE_EVENT_TYPES),),
        ).fetchall()
        critical_audits = conn.execute(
            """
            SELECT category, action, severity, scope, scope_key, symbol, created_ts, details_json
            FROM live.audit_trails
            WHERE severity = 'critical'
              AND created_ts >= %s
            ORDER BY created_ts DESC
            LIMIT 20
            """,
            (cutoff,),
        ).fetchall()
        last_fill = conn.execute(
            """
            SELECT created_ts
            FROM live.fills
            ORDER BY created_ts DESC
            LIMIT 1
            """
        ).fetchone()
        order_rows = conn.execute(
            """
            SELECT status, count(*) AS total
            FROM live.orders
            GROUP BY status
            """
        ).fetchall()
        shadow_live_row = conn.execute(
            """
            SELECT
              count(*) FILTER (WHERE decision_reason = 'shadow_live_divergence_gate')
                AS gate_blocks_24h,
              count(*) FILTER (
                WHERE payload_json->'shadow_live_divergence'->>'match_ok' = 'false'
              ) AS match_failures_24h
            FROM live.execution_decisions
            WHERE created_ts >= now() - interval '24 hours'
            """
        ).fetchone()
        latch_row = conn.execute(
            """
            SELECT action
            FROM live.audit_trails
            WHERE category = 'safety_latch'
            ORDER BY created_ts DESC
            LIMIT 1
            """
        ).fetchone()
    shadow_live_stats: dict[str, int] = {"gate_blocks_24h": 0, "match_failures_24h": 0}
    if shadow_live_row is not None:
        shadow_live_stats = {
            "gate_blocks_24h": int(shadow_live_row.get("gate_blocks_24h") or 0),
            "match_failures_24h": int(shadow_live_row.get("match_failures_24h") or 0),
        }
    safety_latch_active = (
        str(dict(latch_row).get("action") or "") == "arm" if latch_row is not None else False
    )
    return {
        "latest_reconcile": dict(latest_reconcile) if latest_reconcile is not None else None,
        "active_kill_switches": [dict(row) for row in active_kill_switches],
        "critical_audits": [dict(row) for row in critical_audits],
        "last_fill_created_ts": last_fill["created_ts"] if last_fill is not None else None,
        "order_status_counts": {
            str(row["status"]): int(row["total"]) for row in order_rows
        },
        "shadow_live_stats": shadow_live_stats,
        "safety_latch_active": safety_latch_active,
    }


def _coerce_json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _age_ms(value: Any, *, now_ms: int) -> int | None:
    parsed = _to_datetime(value)
    if parsed is None:
        return None
    return max(0, now_ms - int(parsed.timestamp() * 1000))


def _iso(value: Any) -> str | None:
    parsed = _to_datetime(value)
    if parsed is None:
        return None
    return parsed.isoformat()


def _to_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None
