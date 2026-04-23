"""
Lese-Proxys (GET) unter /v1/live-broker/* aus Postgres.

Live-Broker-**Mutationen** (POST: Safety, operator-release) liegen in
`routes_live_broker_safety`, `routes_live_broker_operator` und rufen dort
`verify_live_trading_capability` (siehe `api_gateway.deps` + `mutation_deps`) — Fail-Fast 403
ohne gueltigen Mandanten-Vertrag.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from psycopg.rows import dict_row

from api_gateway.auth import GatewayAuthContext
from api_gateway.config import get_gateway_settings
from api_gateway.db import DatabaseHealthError, get_database_url
from api_gateway.deps import audited_sensitive
from api_gateway.db_live_broker_queries import (
    fetch_execution_forensic_timeline,
    fetch_live_broker_audit_trails,
    fetch_live_broker_decisions,
    fetch_live_broker_fills,
    fetch_live_broker_kill_switch_events,
    fetch_live_broker_order_actions,
    fetch_live_broker_orders,
    fetch_live_broker_paper_reference,
    fetch_live_broker_runtime,
)
from api_gateway.gateway_read_envelope import NEXT_STEP_DB, merge_read_envelope, safe_db_items

logger = logging.getLogger("api_gateway.live_broker_proxy")

router = APIRouter(prefix="/v1/live-broker", tags=["live-broker"])


def _lim(default: int = 20, cap: int = 200) -> int:
    try:
        raw = int(get_gateway_settings().dashboard_page_size or default)
    except ValueError:
        raw = default
    return max(1, min(cap, raw))


@router.get("/runtime", response_model=None)
def live_broker_runtime(
    _auth: Annotated[GatewayAuthContext, Depends(audited_sensitive("live_broker_runtime_view"))],
) -> dict[str, Any]:
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            item = fetch_live_broker_runtime(conn)
    except DatabaseHealthError as exc:
        logger.warning("live_broker runtime: %s", exc)
        return merge_read_envelope(
            {"item": None},
            status="degraded",
            message="Datenbank ist nicht konfiguriert.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except Exception as exc:
        logger.warning("live_broker runtime: %s", exc)
        return merge_read_envelope(
            {"item": None},
            status="degraded",
            message="Runtime-Status nicht ladbar.",
            empty_state=True,
            degradation_reason="database_error",
            next_step=NEXT_STEP_DB,
        )
    es = item is None or (isinstance(item, dict) and len(item) == 0)
    return merge_read_envelope(
        {"item": item},
        status="ok",
        message="Kein Live-Broker-Runtime-Datensatz." if es else None,
        empty_state=es,
        degradation_reason="no_runtime_row" if es else None,
        next_step=None,
    )


@router.get("/executions/{execution_id}/forensic-timeline", response_model=None)
def live_broker_execution_forensic_timeline(
    execution_id: UUID,
    _auth: Annotated[
        GatewayAuthContext, Depends(audited_sensitive("live_broker_forensic_timeline_view"))
    ],
) -> dict[str, Any]:
    """Aggregierte Trade-/Execution-Forensik (keine Roh-Secrets; verschachtelte JSON redacted)."""
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            row = fetch_execution_forensic_timeline(conn, execution_id=str(execution_id))
    except DatabaseHealthError as exc:
        logger.warning("live_broker forensic: %s", exc)
        return merge_read_envelope(
            {"execution_id": str(execution_id), "error": "database_unconfigured"},
            status="degraded",
            message="Datenbank ist nicht konfiguriert.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except Exception as exc:
        logger.warning("live_broker forensic: %s", exc)
        return merge_read_envelope(
            {"execution_id": str(execution_id), "error": "query_failed"},
            status="degraded",
            message="Forensik nicht ladbar.",
            empty_state=True,
            degradation_reason="database_error",
            next_step=NEXT_STEP_DB,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="execution not found")
    return merge_read_envelope(
        row,
        status="ok",
        message=None,
        empty_state=False,
        degradation_reason=None,
        next_step=None,
    )


@router.get("/decisions/recent", response_model=None)
def live_broker_decisions_recent(
    _auth: Annotated[GatewayAuthContext, Depends(audited_sensitive("live_broker_decisions_view"))],
) -> dict[str, Any]:
    lim = _lim()
    return safe_db_items(
        route_tag="live_broker_decisions",
        limit=lim,
        fetch=lambda c: fetch_live_broker_decisions(c, limit=lim),
        empty_message="Keine Execution-Decisions.",
        degraded_message="Decisions nicht ladbar.",
    )


@router.get("/reference/paper", response_model=None)
def live_broker_paper_reference(
    _auth: Annotated[GatewayAuthContext, Depends(audited_sensitive("live_broker_paper_reference_view"))],
) -> dict[str, Any]:
    lim = _lim()
    return safe_db_items(
        route_tag="live_broker_paper_ref",
        limit=lim,
        fetch=lambda c: fetch_live_broker_paper_reference(c, limit=lim),
        empty_message="Keine Paper-Referenzen.",
        degraded_message="Paper-Referenz nicht ladbar.",
    )


@router.get("/orders/recent", response_model=None)
def live_broker_orders_recent(
    _auth: Annotated[GatewayAuthContext, Depends(audited_sensitive("live_broker_orders_view"))],
) -> dict[str, Any]:
    lim = _lim()
    return safe_db_items(
        route_tag="live_broker_orders",
        limit=lim,
        fetch=lambda c: fetch_live_broker_orders(c, limit=lim),
        empty_message="Keine Live-Orders.",
        degraded_message="Orders nicht ladbar.",
    )


@router.get("/fills/recent", response_model=None)
def live_broker_fills_recent(
    _auth: Annotated[GatewayAuthContext, Depends(audited_sensitive("live_broker_fills_view"))],
) -> dict[str, Any]:
    lim = _lim()
    return safe_db_items(
        route_tag="live_broker_fills",
        limit=lim,
        fetch=lambda c: fetch_live_broker_fills(c, limit=lim),
        empty_message="Keine Fills.",
        degraded_message="Fills nicht ladbar.",
    )


@router.get("/orders/actions/recent", response_model=None)
def live_broker_order_actions_recent(
    _auth: Annotated[
        GatewayAuthContext, Depends(audited_sensitive("live_broker_order_actions_view"))
    ],
) -> dict[str, Any]:
    lim = _lim()
    return safe_db_items(
        route_tag="live_broker_order_actions",
        limit=lim,
        fetch=lambda c: fetch_live_broker_order_actions(c, limit=lim),
        empty_message="Keine Order-Aktionen.",
        degraded_message="Order-Aktionen nicht ladbar.",
    )


@router.get("/kill-switch/active", response_model=None)
def live_broker_kill_switch_active(
    _auth: Annotated[GatewayAuthContext, Depends(audited_sensitive("live_broker_kill_switch_view"))],
) -> dict[str, Any]:
    lim = _lim()
    return safe_db_items(
        route_tag="live_broker_kill_active",
        limit=lim,
        fetch=lambda c: fetch_live_broker_kill_switch_events(c, limit=lim, active_only=True),
        empty_message=(
            "Kein aktiver Kill-Switch — Live wird hierdurch nicht blockiert. "
            "Weitere Sperren (Safety-Latch, Konfiguration, Reconcile) siehe GET /v1/live-broker/runtime "
            "(Feld operator_live_submission)."
        ),
        empty_reason="kill_switch_inactive",
        degraded_message="Kill-Switch-Status nicht ladbar.",
    )


@router.get("/kill-switch/events/recent", response_model=None)
def live_broker_kill_switch_events_recent(
    _auth: Annotated[
        GatewayAuthContext, Depends(audited_sensitive("live_broker_kill_switch_events_view"))
    ],
) -> dict[str, Any]:
    lim = _lim()
    return safe_db_items(
        route_tag="live_broker_kill_events",
        limit=lim,
        fetch=lambda c: fetch_live_broker_kill_switch_events(c, limit=lim, active_only=False),
        empty_message="Keine Kill-Switch-Events.",
        degraded_message="Kill-Switch-Events nicht ladbar.",
    )


@router.get("/audit/recent", response_model=None)
def live_broker_audit_recent(
    _auth: Annotated[GatewayAuthContext, Depends(audited_sensitive("live_broker_audit_trail_view"))],
    category: str | None = None,
) -> dict[str, Any]:
    lim = _lim()
    cat = category.strip() if isinstance(category, str) and category.strip() else None

    def _fetch(c: Any) -> list[Any]:
        return fetch_live_broker_audit_trails(c, limit=lim, category=cat)

    base = safe_db_items(
        route_tag="live_broker_audit",
        limit=lim,
        fetch=_fetch,
        extra={"category": cat},
        empty_message="Keine Audit-Eintraege.",
        degraded_message="Audit-Trail nicht ladbar.",
    )
    return base
