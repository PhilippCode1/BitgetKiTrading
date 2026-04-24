from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any

from monitor_engine.alerts.publisher import publish_system_alert
from monitor_engine.checks.services_http import ServiceCheckResult
from monitor_engine.storage.repo_self_healing import get_state, set_phase, try_begin_restart
from monitor_engine.self_healing.service_restarter import ServiceRestarter
from shared_py.eventbus import RedisStreamBus

logger = logging.getLogger("monitor_engine.self_healing.coordinator")

RECOVERY_EVENT = "RECOVERY_REQUESTED"


def _group_checks(rows: list[ServiceCheckResult]) -> dict[str, list[ServiceCheckResult]]:
    g: dict[str, list[ServiceCheckResult]] = defaultdict(list)
    for r in rows:
        g[r.service_name].append(r)
    return g


def _is_any_bad(crs: list[ServiceCheckResult]) -> bool:
    return any(x.status != "ok" for x in crs)


def _heartbeat_age_sec(r: ServiceCheckResult) -> float | None:
    d = r.details
    if not isinstance(d, dict):
        return None
    w = d.get("worker_heartbeat")
    if not isinstance(w, dict):
        return None
    a = w.get("age_sec")
    if a is None:
        return None
    try:
        return float(a)
    except (TypeError, ValueError):
        return None


def is_critical_for_self_heal(
    crs: list[ServiceCheckResult], *, stale_heartbeat_crit_sec: float
) -> bool:
    for r in crs:
        if r.status == "fail":
            return True
        if r.check_type == "metrics" and r.status == "degraded":
            age = _heartbeat_age_sec(r)
            if age is not None and age >= float(stale_heartbeat_crit_sec):
                return True
    return False


def _phase_of(dsn: str, name: str) -> str:
    s = get_state(dsn, name)
    if s is None:
        return "healthy"
    return s.health_phase or "healthy"


def run_self_healing_coordinator(
    dsn: str,
    bus: RedisStreamBus,
    settings: Any,
    svc_results: list[ServiceCheckResult],
    restarter: ServiceRestarter,
) -> None:
    if not bool(getattr(settings, "monitor_self_healing_coordinator_enabled", True)):
        return
    raw = str(getattr(settings, "monitor_self_healing_stateless_services", "") or "")
    targets = {x.strip() for x in raw.split(",") if x.strip()}
    if not targets:
        return
    crit_sec = float(getattr(settings, "monitor_self_healing_heartbeat_crit_sec", 300.0))
    max_h = int(getattr(settings, "monitor_self_healing_max_restarts_per_hour", 3) or 3)
    grouped = _group_checks(svc_results)

    for name in sorted(targets):
        crs = grouped.get(name) or []
        if not crs:
            continue
        any_bad = _is_any_bad(crs)
        crit = is_critical_for_self_heal(crs, stale_heartbeat_crit_sec=crit_sec)
        ph = _phase_of(dsn, name)

        if not any_bad:
            if ph in ("degraded", "recovering"):
                set_phase(
                    dsn,
                    name,
                    "healthy",
                    event="RECOVERED",
                    message="Healthy again: alle Checks gruen.",
                    details={"auto": True},
                )
            continue

        if not crit and ph != "recovering":
            if ph != "degraded":
                set_phase(
                    dsn,
                    name,
                    "degraded",
                    event="DEGRADED",
                    message="Nicht-OK, aber nicht kritisch: Noch kein Auto-Restart.",
                    details={},
                )
            continue

        if ph == "recovering" or not crit:
            continue

        ok, reason, _row = try_begin_restart(
            dsn,
            name,
            max_restarts=max_h,
            from_phase_required=None,
            timeline_message="Auto-Restart: RECOVERY_REQUESTED (Kritisch)",
            timeline_source="coordinator",
        )
        if not ok:
            logger.info("self-healing skip service=%s reason=%s", name, reason)
            if reason == "restart_rate_limited":
                publish_rate_limit_event(bus, name)
            continue

        rr = restarter.restart(name)
        publish_recovery_requested(bus, name, restarter=rr)
        if isinstance(rr, dict) and (rr or {}).get("ok"):
            logger.info("self-healing restart ok service=%r mode=%r", name, rr.get("mode"))


def publish_recovery_requested(
    bus: RedisStreamBus, service_name: str, *, restarter: dict[str, Any]
) -> None:
    try:
        publish_system_alert(
            bus,
            alert_key=f"RECOVERY_REQUESTED:{service_name}:{int(time.time()) // 20}",
            severity="info",
            title=RECOVERY_EVENT,
            message=f"{RECOVERY_EVENT} {service_name}",
            details={
                "self_healing": True,
                "recovery_phase": RECOVERY_EVENT,
                "service": service_name,
                "source": "monitor_engine_coordinator",
                "restarter": restarter,
            },
        )
    except Exception as exc:
        logger.exception("RECOVERY_REQUESTED publish failed: %s", exc)


def publish_rate_limit_event(bus: RedisStreamBus, service_name: str) -> None:
    try:
        publish_system_alert(
            bus,
            alert_key=f"RECOVERY_THROTTLED:{service_name}:{int(time.time()) // 60}",
            severity="warn",
            title="RECOVERY throttled (max 3/h)",
            message=f"Loop-Schutz: {service_name} (max. Restarts/Std.)",
            details={"self_healing": True, "service": service_name},
        )
    except Exception as exc:
        logger.warning("rate limit alert publish: %s", exc)
