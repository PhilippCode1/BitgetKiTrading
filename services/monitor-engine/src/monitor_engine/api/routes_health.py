from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Request

logger = logging.getLogger("monitor_engine.api.health")

from shared_py.observability import (
    append_peer_readiness_checks,
    check_postgres,
    check_redis_url,
    merge_ready_details,
)

from monitor_engine.storage.repo_alerts import count_open_alerts

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    scheduler = request.app.state.scheduler
    stats = scheduler.stats_snapshot()
    now_ms = int(time.time() * 1000)
    sm = float(settings.monitor_scheduler_stale_multiplier)
    stale_after_ms = int(max(15_000, int(settings.monitor_interval_sec) * 3 * 1000) * sm)
    last_run_ts_ms = stats.get("last_run_ts_ms")
    scheduler_stale = (
        True
        if last_run_ts_ms is None
        else (now_ms - int(last_run_ts_ms)) > stale_after_ms
    )
    last_error = stats.get("last_error")
    try:
        open_alert_count = count_open_alerts(settings.database_url)
    except Exception:
        open_alert_count = int(stats.get("open_alert_count") or 0)
    status = "ok"
    if scheduler_stale or last_error:
        status = "degraded"
        if scheduler_stale and last_run_ts_ms is not None:
            age = now_ms - int(last_run_ts_ms)
            logger.warning(
                "monitor-engine /health scheduler deemed stale: tick_age_ms=%s > stale_after_ms=%s "
                "(last_run_ts_ms=%s monitor_interval_sec=%s stale_multiplier=%s)",
                age,
                stale_after_ms,
                last_run_ts_ms,
                settings.monitor_interval_sec,
                sm,
            )
        if last_error:
            logger.warning(
                "monitor-engine /health degraded: last_error=%r",
                last_error,
            )
    return {
        "status": status,
        "service": "monitor-engine",
        "open_alert_count": open_alert_count,
        "last_run_ts_ms": last_run_ts_ms,
        "last_run_duration_ms": stats.get("last_duration_ms"),
        "last_alert_count": stats.get("last_alert_count"),
        "service_check_count": stats.get("service_check_count"),
        "stream_check_count": stats.get("stream_check_count"),
        "freshness_check_count": stats.get("freshness_check_count"),
        "live_broker_check_count": stats.get("live_broker_check_count"),
        "last_error": last_error,
        "live_broker_monitored": "live-broker" in settings.service_urls,
        "system_alert_stream_monitored": "events:system_alert" in settings.streams,
    }


@router.get("/ready")
def ready(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    scheduler = request.app.state.scheduler
    stats = scheduler.stats_snapshot()
    now_ms = int(time.time() * 1000)
    boot_ts_ms = int(getattr(request.app.state, "boot_ts_ms", now_ms))
    boot_age_ms = now_ms - boot_ts_ms
    grace_ms = int(settings.monitor_readiness_boot_grace_ms)
    in_boot_grace = boot_age_ms < grace_ms
    sm = float(settings.monitor_scheduler_stale_multiplier)
    stale_after_ms = int(max(15_000, int(settings.monitor_interval_sec) * 3 * 1000) * sm)
    last_run_ts_ms = stats.get("last_run_ts_ms")
    last_err = stats.get("last_error")
    if last_run_ts_ms is not None:
        scheduler_ok = (now_ms - int(last_run_ts_ms)) <= stale_after_ms
        sched_detail = (
            f"last_run_ts_ms={last_run_ts_ms} stale_after_ms={stale_after_ms}"
        )
    elif in_boot_grace:
        scheduler_ok = last_err is None
        sched_detail = f"boot_grace_ms={grace_ms} boot_age_ms={boot_age_ms}"
    else:
        scheduler_ok = False
        sched_detail = "scheduler has not completed a run after boot_grace"
    if not scheduler_ok and last_run_ts_ms is not None and not in_boot_grace:
        age = now_ms - int(last_run_ts_ms)
        if age > stale_after_ms:
            logger.warning(
                "monitor-engine /ready scheduler not ok: tick_age_ms=%s > stale_after_ms=%s "
                "(last_run_ts_ms=%s interval=%s mult=%s detail=%s)",
                age,
                stale_after_ms,
                last_run_ts_ms,
                settings.monitor_interval_sec,
                sm,
                sched_detail,
            )
    try:
        eb_ok = bool(request.app.state.bus.ping())
        eb_detail = "ok"
    except Exception as exc:
        eb_ok = False
        eb_detail = str(exc)[:200]
    parts = {
        "postgres": check_postgres(settings.database_url),
        "redis": check_redis_url(settings.redis_url),
        "eventbus": (eb_ok, eb_detail),
        "scheduler": (scheduler_ok, sched_detail),
    }
    parts = append_peer_readiness_checks(
        parts,
        settings.readiness_require_urls_raw,
        timeout_sec=float(settings.readiness_peer_timeout_sec),
    )
    ok, details = merge_ready_details(parts)
    details["live_broker_monitored"] = "live-broker" in settings.service_urls
    details["system_alert_stream_monitored"] = "events:system_alert" in settings.streams
    if last_err:
        details["scheduler_last_error"] = last_err
    return {"ready": ok, "checks": details}
