from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row

from monitor_engine.checks.services_http import ServiceCheckResult


def load_online_drift_service_check(database_url: str) -> list[ServiceCheckResult]:
    try:
        with psycopg.connect(database_url, row_factory=dict_row, connect_timeout=5) as conn:
            row = conn.execute(
                """
                SELECT effective_action, computed_at, lookback_minutes, breakdown_json
                FROM learn.online_drift_state
                WHERE scope = 'global'
                LIMIT 1
                """
            ).fetchone()
    except Exception as exc:
        return [
            ServiceCheckResult(
                service_name="online-drift",
                check_type="learn_online_drift_state",
                status="fail",
                latency_ms=None,
                details={"error": str(exc)[:240]},
            )
        ]
    if row is None:
        return [
            ServiceCheckResult(
                service_name="online-drift",
                check_type="learn_online_drift_state",
                status="fail",
                latency_ms=None,
                details={"detail": "missing_global_row"},
            )
        ]
    r = dict(row)
    act = str(r.get("effective_action") or "ok").strip().lower()
    status = "ok"
    if act == "warn":
        status = "degraded"
    elif act == "shadow_only":
        status = "degraded"
    elif act == "hard_block":
        status = "fail"
    details: dict[str, Any] = {
        "effective_action": act,
        "computed_at": r["computed_at"].isoformat() if r.get("computed_at") else None,
        "lookback_minutes": r.get("lookback_minutes"),
    }
    b = r.get("breakdown_json")
    if isinstance(b, dict):
        details["effective_action_breakdown"] = b.get("effective_action")
    return [
        ServiceCheckResult(
            service_name="online-drift",
            check_type="learn_online_drift_state",
            status=status,
            latency_ms=None,
            details=details,
        )
    ]
