from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from monitor_engine.checks.data_freshness import FreshnessRow
from monitor_engine.checks.redis_streams import StreamGroupCheckResult
from monitor_engine.checks.services_http import ServiceCheckResult


@dataclass(frozen=True)
class AlertSpec:
    alert_key: str
    severity: str
    title: str
    message: str
    details: dict[str, Any]
    # Niedrigere Zahl = hoehere Dringlichkeit (Safety/Trading zuerst).
    priority: int = 100


_SERVICE_CHECK_PRIORITY: dict[tuple[str, str], int] = {
    ("live-broker", "kill_switch"): 5,
    ("live-broker", "audit"): 8,
    ("live-broker", "reconcile"): 12,
    ("live-broker", "shadow_live_divergence"): 18,
    ("online-drift", "learn_online_drift_state"): 22,
}


def alerts_from_service_checks(results: list[ServiceCheckResult]) -> list[AlertSpec]:
    out: list[AlertSpec] = []
    for r in results:
        if r.status == "ok":
            continue
        key = f"svc:{r.service_name}:{r.check_type}"
        sev = "warn" if r.status == "degraded" else "critical"
        pri = _SERVICE_CHECK_PRIORITY.get(
            (r.service_name, r.check_type),
            35 if sev == "critical" else 55,
        )
        out.append(
            AlertSpec(
                alert_key=key,
                severity=sev,
                title=f"Service {r.service_name} {r.check_type}",
                message=f"Status {r.status} Latenz {r.latency_ms}ms",
                details=r.details,
                priority=pri,
            )
        )
    return out


def alerts_from_stream_checks(results: list[StreamGroupCheckResult]) -> list[AlertSpec]:
    out: list[AlertSpec] = []
    for r in results:
        if r.status == "ok":
            continue
        key = f"stream:{r.stream}:group:{r.group_name}"
        sev = "warn" if r.status == "degraded" else "critical"
        pri = 40 if sev == "critical" else 60
        out.append(
            AlertSpec(
                alert_key=key,
                severity=sev,
                title="Redis Stream belastet",
                message=(
                    f"{r.stream} / {r.group_name}: pending={r.pending_count} lag={r.lag}"
                ),
                details={
                    "stream": r.stream,
                    "group": r.group_name,
                    "pending_count": r.pending_count,
                    "lag": r.lag,
                    **r.details,
                },
                priority=pri,
            )
        )
    return out


def alerts_from_freshness(rows: list[FreshnessRow]) -> list[AlertSpec]:
    out: list[AlertSpec] = []
    for row in rows:
        if row.status == "ok":
            continue
        key = f"freshness:{row.datapoint}"
        sev = "warn" if row.status == "warn" else "critical"
        pri = 25 if sev == "critical" else 45
        out.append(
            AlertSpec(
                alert_key=key,
                severity=sev,
                title=f"Datenfrische {row.datapoint}",
                message=f"age_ms={row.age_ms} last_ts_ms={row.last_ts_ms}",
                details={**row.details, "age_ms": row.age_ms, "last_ts_ms": row.last_ts_ms},
                priority=pri,
            )
        )
    return out


def alert_stream_stalled(stream: str, *, candle_stale_critical: bool) -> AlertSpec | None:
    if not candle_stale_critical:
        return None
    key = f"stream_stalled:{stream}"
    return AlertSpec(
        alert_key=key,
        severity="critical",
        title="Stream waechst nicht bei veralteter Kerze",
        message=f"Stream {stream} und 1m-Kerze kritisch stale",
        details={"stream": stream},
        priority=15,
    )
