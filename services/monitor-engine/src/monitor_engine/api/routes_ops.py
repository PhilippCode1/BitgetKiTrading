from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from monitor_engine.prom_metrics import TIMESFM_INFERENCE_BATCH_LATENCY_MS
from monitor_engine.storage.repo_alerts import ack_alert, list_open_alerts
from monitor_engine.storage.repo_post_mortem import fetch_post_mortem
from monitor_engine.storage.repo_self_healing import (
    SelfHealingStateRow,
    fetch_all_states,
    try_begin_restart,
)
from monitor_engine.self_healing.coordinator import publish_recovery_requested
from monitor_engine.self_healing.service_restarter import ServiceRestarter
from shared_py.service_auth import INTERNAL_SERVICE_HEADER, InternalServiceAuthContext, assert_internal_service_auth

router = APIRouter(tags=["ops"])


def _require_internal_service(
    request: Request,
    x_internal_service_key: str | None = Header(default=None, alias=INTERNAL_SERVICE_HEADER),
) -> InternalServiceAuthContext:
    settings = request.app.state.settings
    return assert_internal_service_auth(settings, x_internal_service_key)


@router.get("/ops/alerts/open")
def alerts_open(
    request: Request,
    limit: int = 50,
    _auth: InternalServiceAuthContext = Depends(_require_internal_service),
) -> dict[str, Any]:
    settings = request.app.state.settings
    rows = list_open_alerts(settings.database_url, limit=min(limit, 200))
    return {
        "alerts": [
            {
                "alert_key": r.alert_key,
                "severity": r.severity,
                "title": r.title,
                "message": r.message,
                "details": r.details,
                "state": r.state,
                "created_ts": r.created_ts.isoformat() if r.created_ts else None,
                "updated_ts": r.updated_ts.isoformat() if r.updated_ts else None,
            }
            for r in rows
        ]
    }


@router.post("/ops/alerts/{alert_key:path}/ack")
def alerts_ack(
    request: Request,
    alert_key: str,
    _auth: InternalServiceAuthContext = Depends(_require_internal_service),
) -> dict[str, Any]:
    settings = request.app.state.settings
    ok = ack_alert(settings.database_url, alert_key)
    if not ok:
        raise HTTPException(status_code=404, detail="alert_key not found")
    return {"ok": True, "alert_key": alert_key}


class InferenceBatchMetricIn(BaseModel):
    """Push-Metrik vom inference-server (Batch-Latenz)."""

    model_id: str = Field(default="unknown", max_length=160)
    batch_size: int = Field(ge=0, le=10_000)
    forecast_horizon: int = Field(ge=0, le=2048)
    latency_ms: float = Field(ge=0.0)
    backend: str = Field(default="stub", max_length=32)


@router.post("/ops/inference-batch-metric")
def inference_batch_metric(
    request: Request,
    body: InferenceBatchMetricIn,
    _auth: InternalServiceAuthContext = Depends(_require_internal_service),
) -> dict[str, Any]:
    mid = (body.model_id or "unknown")[:80]
    be = (body.backend or "stub")[:16]
    TIMESFM_INFERENCE_BATCH_LATENCY_MS.labels(model_id=mid, backend=be).observe(
        float(body.latency_ms)
    )
    return {"ok": True, "observed_ms": body.latency_ms}


@router.post("/ops/run-now")
async def run_now(
    request: Request,
    _auth: InternalServiceAuthContext = Depends(_require_internal_service),
) -> dict[str, str]:
    sched = request.app.state.scheduler
    await sched.run_once()
    return {"status": "ok"}


def _row_to_dict(r: SelfHealingStateRow) -> dict[str, Any]:
    return {
        "service_name": r.service_name,
        "health_phase": r.health_phase,
        "updated_ts": r.updated_ts_epoch,
        "restart_events_ts": r.restart_events_ts,
        "timeline": r.timeline,
    }


@router.get("/ops/self-healing/status")
def self_healing_status(
    request: Request,
    _auth: InternalServiceAuthContext = Depends(_require_internal_service),
) -> dict[str, Any]:
    s = request.app.state.settings
    rows = fetch_all_states(s.database_url)
    return {
        "ok": True,
        "items": [_row_to_dict(x) for x in rows],
        "coordinator_enabled": bool(
            getattr(s, "monitor_self_healing_coordinator_enabled", True)
        ),
    }


class SelfHealingRestartIn(BaseModel):
    service_name: str = Field(
        min_length=2, max_length=64, description="z.B. feature-engine, drawing-engine, signal-engine"
    )


@router.get("/ops/post-mortems/{post_mortem_id}")
def get_post_mortem(
    request: Request,
    post_mortem_id: str,
    _auth: InternalServiceAuthContext = Depends(_require_internal_service),
) -> dict[str, Any]:
    s = request.app.state.settings
    r = fetch_post_mortem(s.database_url, post_mortem_id)
    if r is None:
        raise HTTPException(status_code=404, detail="post_mortem not found or migration 630 fehlt")
    return {
        "schema_version": "ops-post-mortem-v1",
        "id": r.id,
        "created_ts": r.created_ts.isoformat() if r.created_ts else None,
        "trigger": r.trigger,
        "correlation_id": r.correlation_id,
        "duration_ms": r.duration_ms,
        "redis_event_samples": r.redis_event_samples,
        "service_health": r.service_health,
        "llm_status": r.llm_status,
        "llm_result": r.llm_result,
        "telegram_enqueued": r.telegram_enqueued,
        "report_url": r.report_url,
    }


@router.post("/ops/self-healing/restart")
def self_healing_restart(
    request: Request,
    body: SelfHealingRestartIn,
    _auth: InternalServiceAuthContext = Depends(_require_internal_service),
) -> dict[str, Any]:
    s = request.app.state.settings
    m = int(getattr(s, "monitor_self_healing_max_restarts_per_hour", 3) or 3)
    ok, reason, st = try_begin_restart(
        s.database_url,
        body.service_name,
        max_restarts=m,
        from_phase_required="degraded",
        timeline_message="Operator/API: RECOVERY_REQUESTED (degraded->recovering)",
        timeline_source="api_post_restart",
    )
    if not ok:
        if reason == "restart_rate_limited":
            raise HTTPException(
                status_code=429,
                detail={"ok": False, "code": "RESTART_RATE_LIMIT", "message": reason},
            )
        if "phase_mismatch" in reason or reason == "already_recovering":
            raise HTTPException(
                status_code=409,
                detail={"ok": False, "code": "RESTART_CONFLICT", "message": reason},
            )
        raise HTTPException(
            status_code=400,
            detail={"ok": False, "code": "RESTART_REJECTED", "message": reason},
        )
    rest = ServiceRestarter.from_settings(s).restart(body.service_name)
    bus = request.app.state.bus
    publish_recovery_requested(
        bus,
        body.service_name,
        restarter=rest,
    )
    st2 = st
    return {
        "ok": True,
        "service_name": body.service_name,
        "health_phase": st2.health_phase if st2 is not None else "recovering",
        "restarter": rest,
        "state": _row_to_dict(st2) if st2 is not None else None,
    }
