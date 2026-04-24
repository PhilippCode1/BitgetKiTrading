from __future__ import annotations

import json
import logging
from typing import Any

import httpx
import psycopg
from config.internal_service_discovery import http_base_from_health_or_ready_url
from fastapi import APIRouter, Depends, HTTPException
from psycopg import errors as pg_errors
from pydantic import BaseModel, Field
from shared_py.service_auth import INTERNAL_SERVICE_HEADER

from api_gateway.auth import GatewayAuthContext, require_operator_aggregate_auth
from api_gateway.config import get_gateway_settings
from api_gateway.db import DatabaseHealthError, get_database_url
from api_gateway.db_ops_queries import fetch_self_healing_state_rows

logger = logging.getLogger("api_gateway.ops_self_healing")

router = APIRouter(prefix="/v1/ops", tags=["ops-self-healing"])


@router.get("/self-healing/status")
def self_healing_status_get() -> dict[str, Any]:
    try:
        dsn = get_database_url()
    except DatabaseHealthError:
        return {
            "ok": True,
            "items": [],
            "empty": True,
            "degradation_reason": "no_database_url",
        }
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            items = fetch_self_healing_state_rows(conn)
        return {
            "ok": True,
            "items": items,
        }
    except (pg_errors.Error, OSError) as exc:
        logger.warning("self-healing status read: %s", exc)
        raise HTTPException(503, detail="self_healing_db_error") from exc


def _monitor_base() -> str:
    g = get_gateway_settings()
    b = http_base_from_health_or_ready_url(str(g.health_url_monitor_engine or ""))
    return b.rstrip("/") if b else ""


class SelfHealingRestartIn(BaseModel):
    service_name: str = Field(min_length=2, max_length=64)


@router.post("/self-healing/restart")
def self_healing_restart(
    body: SelfHealingRestartIn,
    _op: GatewayAuthContext = Depends(require_operator_aggregate_auth),  # noqa: B008
) -> dict[str, Any]:
    g = get_gateway_settings()
    if not g.health_url_monitor_engine or not (base := _monitor_base()):
        raise HTTPException(503, detail="monitor_engine_base_unconfigured")
    k = (getattr(g, "service_internal_api_key", None) or "").strip()
    headers: dict[str, str] = {}
    if k:
        headers[INTERNAL_SERVICE_HEADER] = k
    url = f"{base}/ops/self-healing/restart"
    try:
        payload = json.dumps({"service_name": body.service_name.strip()}).encode("utf-8")
        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                url,
                content=payload,
                headers={**headers, "Content-Type": "application/json"},
            )
    except httpx.RequestError as exc:
        raise HTTPException(502, detail=f"monitor_unavailable:{exc!s}"[:200]) from exc
    if r.status_code in (200, 201, 202):
        try:
            return dict(r.json())
        except Exception:
            return {"ok": True, "raw": (r.text or "")[:200]}
    if r.status_code == 429:
        try:
            d = r.json() if r.content else {}
        except Exception:
            d = {}
        dct = d if isinstance(d, dict) else {}
        de = dct.get("detail")
        raise HTTPException(429, detail=de or "RESTART_RATE_LIMIT")
    if r.status_code == 409:
        try:
            d = r.json() if r.content else {}
        except Exception:
            d = {}
        dct = d if isinstance(d, dict) else {}
        de = dct.get("detail")
        raise HTTPException(409, detail=de or "RESTART_CONFLICT")
    if r.status_code in (400, 401, 404):
        raise HTTPException(400, detail=(r.text or "bad_request")[:200])
    raise HTTPException(502, detail=(r.text or f"http_{r.status_code}")[:300])
