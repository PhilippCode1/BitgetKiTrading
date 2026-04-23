from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from monitor_engine.prom_metrics import TIMESFM_INFERENCE_BATCH_LATENCY_MS
from monitor_engine.storage.repo_alerts import ack_alert, list_open_alerts
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
