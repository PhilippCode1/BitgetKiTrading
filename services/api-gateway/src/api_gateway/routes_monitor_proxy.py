from __future__ import annotations

import logging
from typing import Any

import psycopg
from fastapi import APIRouter
from psycopg import errors as pg_errors
from psycopg.rows import dict_row

from api_gateway.db import DatabaseHealthError, get_database_url
from api_gateway.db_ops_queries import fetch_monitor_open_alerts
from api_gateway.gateway_read_envelope import NEXT_STEP_DB, merge_read_envelope
from api_gateway.routes_live_broker_proxy import _lim

logger = logging.getLogger("api_gateway.monitor_proxy")

router = APIRouter(prefix="/v1/monitor", tags=["monitor"])


@router.get(
    "/alerts/open",
    response_model=None,
    summary="Offene Monitor-Alerts",
    description="Liste aus ops.alerts (state=open). HTTP 200 mit Envelope; kein 500 bei leerer DB-Tabelle.",
)
def monitor_alerts_open() -> dict[str, Any]:
    limit = _lim()
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            items = fetch_monitor_open_alerts(conn, limit=limit)
        es = len(items) == 0
        return merge_read_envelope(
            {"items": items, "limit": limit},
            status="ok",
            message="Keine offenen Monitor-Alerts." if es else None,
            empty_state=es,
            degradation_reason="no_open_alerts" if es else None,
            next_step=None,
        )
    except DatabaseHealthError as exc:
        logger.warning("monitor alerts/open: %s", exc)
        return merge_read_envelope(
            {"items": [], "limit": limit},
            status="degraded",
            message="Datenbank ist nicht konfiguriert.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except (pg_errors.Error, OSError) as exc:
        logger.warning("monitor alerts/open degraded: %s", exc)
        return merge_read_envelope(
            {"items": [], "limit": limit},
            status="degraded",
            message="Alerts konnten nicht geladen werden.",
            empty_state=True,
            degradation_reason="database_error",
            next_step=NEXT_STEP_DB,
        )
