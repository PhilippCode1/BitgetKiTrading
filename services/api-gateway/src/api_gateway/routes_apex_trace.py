"""Apex-Trace: Lesen der gespeicherten `apex_trace`-Kette (Postgres)."""

from __future__ import annotations

from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg.rows import dict_row

from api_gateway.auth import GatewayAuthContext, require_sensitive_auth
from api_gateway.db import get_database_url
from api_gateway.db_apex_latency import fetch_apex_trace_by_signal_id

router = APIRouter(prefix="/v1/apex-trace", tags=["apex-trace"])


@router.get("/by-signal", response_model=None)
def apex_trace_by_signal(
    _auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
    signal_id: str = Query(..., min_length=1, max_length=2000),
) -> dict[str, Any]:
    try:
        dsn = get_database_url()
    except Exception:
        return {
            "ok": False,
            "error": "database_unconfigured",
            "signal_id": signal_id,
        }
    try:
        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            row = fetch_apex_trace_by_signal_id(conn, signal_id=signal_id)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail={"code": "query_failed", "message": str(exc)[:500]}
        ) from exc
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "signal_id": signal_id})
    at = row.get("apex_trace")
    return {
        "ok": True,
        "signal_id": str(row.get("signal_id") or signal_id),
        "execution_id": str(row.get("execution_id") or "") or None,
        "trace_id": str(row.get("trace_id") or "") or None,
        "apex_trace": at or {},
    }
