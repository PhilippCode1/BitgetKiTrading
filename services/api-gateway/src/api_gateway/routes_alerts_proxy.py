from __future__ import annotations

import logging
from typing import Any

import psycopg
from fastapi import APIRouter
from psycopg.rows import dict_row

from api_gateway.db import DatabaseHealthError, get_database_url
from api_gateway.db_ops_queries import fetch_alert_outbox_recent
from api_gateway.gateway_read_envelope import NEXT_STEP_DB, merge_read_envelope
from api_gateway.routes_live_broker_proxy import _lim

logger = logging.getLogger("api_gateway.alerts_proxy")

router = APIRouter(prefix="/v1/alerts", tags=["alerts"])


@router.get("/outbox/recent", response_model=None)
def alerts_outbox_recent() -> dict[str, Any]:
    limit = _lim()
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            items = fetch_alert_outbox_recent(conn, limit=limit)
        es = len(items) == 0
        return merge_read_envelope(
            {"items": items, "limit": limit},
            status="ok",
            message="Outbox ist leer." if es else None,
            empty_state=es,
            degradation_reason="outbox_empty" if es else None,
            next_step=None,
        )
    except DatabaseHealthError as exc:
        logger.warning("alerts outbox: %s", exc)
        return merge_read_envelope(
            {"items": [], "limit": limit},
            status="degraded",
            message="Datenbank ist nicht konfiguriert.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except Exception as exc:
        logger.warning("alerts outbox: %s", exc)
        return merge_read_envelope(
            {"items": [], "limit": limit},
            status="degraded",
            message="Alert-Outbox nicht ladbar.",
            empty_state=True,
            degradation_reason="database_error",
            next_step=NEXT_STEP_DB,
        )
