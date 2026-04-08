"""Persistiert Gateway-Auditzeilen (Admin, sensible Reads, Modell-/Ops-Kontext)."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json
from shared_py.observability.correlation import log_correlation_fields
from shared_py.observability.execution_forensic import redact_nested_mapping
from starlette.requests import Request

from api_gateway.db import get_database_url
from api_gateway.gateway_metrics import observe_auth_failure

if TYPE_CHECKING:
    from api_gateway.auth import GatewayAuthContext

logger = logging.getLogger("api_gateway.audit")


def record_gateway_audit_line(
    request: Request,
    auth: GatewayAuthContext,
    action: str,
    *,
    extra: dict[str, Any] | None = None,
) -> None:
    from api_gateway.auth import GatewayAuthContext as Ctx

    if not isinstance(auth, Ctx):
        return
    client_ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    rid = getattr(request.state, "request_id", None)
    cid = getattr(request.state, "correlation_id", None)
    insert_gateway_audit(
        actor=auth.actor,
        auth_method=auth.auth_method,
        action=action,
        http_method=request.method,
        path=str(request.url.path),
        client_ip=client_ip,
        user_agent=ua,
        detail=extra or {},
        request_id=str(rid) if rid else None,
        correlation_id=str(cid) if cid else None,
    )


def record_gateway_auth_failure(
    request: Request,
    action: str,
    *,
    actor: str = "anonymous",
    auth_method: str = "none",
    extra: dict[str, Any] | None = None,
) -> None:
    observe_auth_failure(action)
    client_ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    rid = getattr(request.state, "request_id", None)
    cid = getattr(request.state, "correlation_id", None)
    insert_gateway_audit(
        actor=actor,
        auth_method=auth_method,
        action=action,
        http_method=request.method,
        path=str(request.url.path),
        client_ip=client_ip,
        user_agent=ua,
        detail=extra or {},
        request_id=str(rid) if rid else None,
        correlation_id=str(cid) if cid else None,
    )


def insert_gateway_audit(
    *,
    actor: str,
    auth_method: str,
    action: str,
    http_method: str,
    path: str,
    client_ip: str | None,
    user_agent: str | None,
    detail: dict[str, Any],
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> None:
    try:
        dsn = get_database_url()
    except Exception as exc:
        logger.warning("gateway audit skipped: %s", exc)
        return
    if not dsn:
        logger.warning("gateway audit skipped: no DATABASE_URL")
        return
    safe_detail = json.loads(json.dumps(detail, default=str)) if detail else {}
    safe_detail = redact_nested_mapping(safe_detail, max_depth=4)
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            row = conn.execute(
                """
                INSERT INTO app.gateway_request_audit (
                    actor, auth_method, action, http_method, path,
                    client_ip, user_agent, detail_json
                ) VALUES (
                    %(actor)s, %(auth_method)s, %(action)s, %(http_method)s, %(path)s,
                    %(client_ip)s, %(user_agent)s, %(detail_json)s
                )
                RETURNING id
                """,
                {
                    "actor": actor[:200],
                    "auth_method": auth_method[:64],
                    "action": action[:128],
                    "http_method": http_method[:16],
                    "path": path[:512],
                    "client_ip": (client_ip or "")[:128] or None,
                    "user_agent": (user_agent or "")[:512] or None,
                    "detail_json": Json(safe_detail),
                },
            ).fetchone()
            conn.commit()
        if row and row.get("id") is not None:
            tid = None
            if isinstance(safe_detail, dict):
                raw_tid = safe_detail.get("tenant_id")
                tid = str(raw_tid).strip()[:128] if raw_tid else None
            logger.info(
                "gateway_audit_recorded",
                extra={
                    **log_correlation_fields(
                        gateway_audit_id=str(row["id"]),
                        tenant_id=tid,
                        request_id=request_id,
                        correlation_id=correlation_id,
                    ),
                    "audit_action": action[:128],
                    "audit_http_method": http_method[:16],
                    "audit_path": path[:512],
                },
            )
    except Exception as exc:
        logger.warning("gateway audit insert failed: %s", exc)
