"""Prompt 15: Gewinnbeteiligung, High-Water-Mark, Statements, Freigabe."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

import psycopg
import psycopg.errors
from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from api_gateway.audit import record_gateway_audit_line
from api_gateway.auth import (
    GatewayAuthContext,
    require_billing_admin,
    require_billing_read,
)
from api_gateway.config import get_gateway_settings
from api_gateway.db import get_database_url
from api_gateway.db_profit_fee import (
    acknowledge_statement,
    admin_preview_numbers,
    approve_statement,
    create_draft_statement,
    dispute_statement,
    fetch_hwm_cents,
    fetch_statement,
    issue_statement,
    list_statements_admin,
    list_statements_for_tenant,
    reopen_disputed_to_issued,
    void_statement,
)
from api_gateway.db_settlement import list_settlements_for_tenant
from api_gateway.routes_commerce_customer import (
    _ensure_commercial,
    _mask_tenant_id,
    _require_tenant_commercial_state,
    _resolve_target_tenant,
)

profit_fee_customer_router = APIRouter(
    prefix="/v1/commerce/customer/profit-fee",
    tags=["commerce-profit-fee"],
)
profit_fee_admin_router = APIRouter(
    prefix="/v1/commerce/admin/profit-fee",
    tags=["commerce-profit-fee"],
)

TradingModeLiteral = Literal["paper", "live"]


def _migration_exc() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "code": "PROFIT_FEE_MIGRATION_REQUIRED",
            "message": "611_profit_fee_hwm.sql",
        },
    )


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"code": "PROFIT_FEE_NOT_FOUND", "message": "Statement nicht gefunden."},
    )


def _stale_hwm() -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "code": "PROFIT_FEE_HWM_STALE",
            "message": "High-Water-Mark geaendert; Statement veraltet — neu bewerten.",
        },
    )


@profit_fee_customer_router.get(
    "/summary",
    summary="HWM und Statements (Kunde)",
)
def customer_profit_fee_summary(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    if not settings.profit_fee_module_enabled:
        raise HTTPException(status_code=404, detail="profit fee disabled")
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    settlements: list[dict[str, Any]] = []
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
            _require_tenant_commercial_state(conn, tid)
            paper_hwm = fetch_hwm_cents(conn, tenant_id=tid, trading_mode="paper")
            live_hwm = fetch_hwm_cents(conn, tenant_id=tid, trading_mode="live")
            stmts = list_statements_for_tenant(conn, tenant_id=tid, limit=40)
            if settings.profit_fee_settlement_enabled:
                try:
                    settlements = list_settlements_for_tenant(
                        conn, tenant_id=tid, limit=40
                    )
                except psycopg.errors.UndefinedTable:
                    settlements = []
    except psycopg.errors.UndefinedTable:
        raise _migration_exc() from None
    record_gateway_audit_line(
        request, auth, "commerce_customer_profit_fee_summary", extra={"tenant_id": tid}
    )
    return {
        "schema_version": "profit-fee-customer-summary-v2",
        "tenant_id_masked": _mask_tenant_id(tid),
        "high_water_mark_cents": {"paper": paper_hwm, "live": live_hwm},
        "statements": stmts,
        "settlements": settlements,
    }


class CustomerAckBody(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


@profit_fee_customer_router.post(
    "/statements/{statement_id}/acknowledge",
    summary="Statement zur Kenntnis nehmen (vor Admin-Freigabe)",
)
def customer_ack_statement(
    request: Request,
    statement_id: UUID,
    body: CustomerAckBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    if not settings.profit_fee_module_enabled:
        raise HTTPException(status_code=404, detail="profit fee disabled")
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
            _require_tenant_commercial_state(conn, tid)
            with conn.transaction():
                row = acknowledge_statement(
                    conn, statement_id=statement_id, note=body.note
                )
    except psycopg.errors.UndefinedTable:
        raise _migration_exc() from None
    if not row or str(row["tenant_id"]) != tid:
        raise _not_found()
    if row.get("customer_ack_ts") is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PROFIT_FEE_ACK_FAILED",
                "message": "Nur im Status issued.",
            },
        )
    record_gateway_audit_line(
        request,
        auth,
        "commerce_customer_profit_fee_ack",
        extra={"statement_id": str(statement_id)},
    )
    return {"schema_version": "profit-fee-ack-v1", "statement": row}


class CustomerDisputeBody(BaseModel):
    reason: str = Field(min_length=4, max_length=4000)


@profit_fee_customer_router.post(
    "/statements/{statement_id}/dispute",
    summary="Streitfall melden",
)
def customer_dispute_statement(
    request: Request,
    statement_id: UUID,
    body: CustomerDisputeBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    if not settings.profit_fee_module_enabled:
        raise HTTPException(status_code=404, detail="profit fee disabled")
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
            _require_tenant_commercial_state(conn, tid)
            with conn.transaction():
                row = dispute_statement(
                    conn, statement_id=statement_id, reason=body.reason
                )
    except psycopg.errors.UndefinedTable:
        raise _migration_exc() from None
    if not row or str(row["tenant_id"]) != tid:
        raise _not_found()
    if row.get("status") != "disputed":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PROFIT_FEE_DISPUTE_FAILED",
                "message": "Nur im Status issued.",
            },
        )
    record_gateway_audit_line(
        request,
        auth,
        "commerce_customer_profit_fee_dispute",
        extra={"statement_id": str(statement_id)},
    )
    return {"schema_version": "profit-fee-dispute-v1", "statement": row}


class AdminPreviewBody(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    trading_mode: TradingModeLiteral
    cumulative_realized_pnl_cents: int
    fee_rate_basis_points: int | None = Field(
        default=None,
        ge=0,
        le=10000,
        description="Default aus Gateway-Settings wenn null",
    )


@profit_fee_admin_router.post(
    "/preview",
    summary="Berechnung Trockenlauf",
)
def admin_profit_fee_preview(
    request: Request,
    body: AdminPreviewBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    if not settings.profit_fee_module_enabled:
        raise HTTPException(status_code=404, detail="profit fee disabled")
    rate = body.fee_rate_basis_points
    if rate is None:
        rate = settings.profit_fee_default_rate_basis_points
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
            _require_tenant_commercial_state(conn, body.tenant_id)
            preview = admin_preview_numbers(
                conn,
                tenant_id=body.tenant_id,
                trading_mode=body.trading_mode,
                cumulative_realized_pnl_cents=body.cumulative_realized_pnl_cents,
                fee_rate_basis_points=rate,
            )
    except psycopg.errors.UndefinedTable:
        raise _migration_exc() from None
    record_gateway_audit_line(
        request,
        auth,
        "commerce_admin_profit_fee_preview",
        extra={"tenant_id": body.tenant_id},
    )
    return {"schema_version": "profit-fee-preview-v1", "preview": preview}


class AdminCreateDraftBody(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    trading_mode: TradingModeLiteral
    period_start: date
    period_end: date
    cumulative_realized_pnl_cents: int
    fee_rate_basis_points: int | None = Field(default=None, ge=0, le=10000)
    pnl_source_ref: str | None = Field(default=None, max_length=512)
    currency: str = Field(default="USD", min_length=3, max_length=8)
    corrects_statement_id: UUID | None = None


@profit_fee_admin_router.post(
    "/statements/draft",
    summary="Statement-Entwurf anlegen",
)
def admin_create_draft_statement(
    request: Request,
    body: AdminCreateDraftBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    if not settings.profit_fee_module_enabled:
        raise HTTPException(status_code=404, detail="profit fee disabled")
    rate = body.fee_rate_basis_points
    if rate is None:
        rate = settings.profit_fee_default_rate_basis_points
    if body.period_end < body.period_start:
        raise HTTPException(status_code=422, detail="period_end before period_start")
    actor = auth.actor or "admin"
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
            _require_tenant_commercial_state(conn, body.tenant_id)
            with conn.transaction():
                row = create_draft_statement(
                    conn,
                    tenant_id=body.tenant_id,
                    trading_mode=body.trading_mode,
                    period_start=body.period_start,
                    period_end=body.period_end,
                    cumulative_realized_pnl_cents=body.cumulative_realized_pnl_cents,
                    fee_rate_basis_points=rate,
                    actor=actor,
                    currency=body.currency,
                    pnl_source_ref=body.pnl_source_ref,
                    corrects_statement_id=body.corrects_statement_id,
                )
    except psycopg.errors.UniqueViolation as e:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PROFIT_FEE_DUPLICATE_PERIOD",
                "message": "Zeitraum existiert bereits (nicht voided/superseded).",
            },
        ) from e
    except psycopg.errors.UndefinedTable:
        raise _migration_exc() from None
    record_gateway_audit_line(
        request,
        auth,
        "commerce_admin_profit_fee_draft",
        extra={"tenant_id": body.tenant_id, "statement_id": row["statement_id"]},
    )
    return {"schema_version": "profit-fee-draft-v1", "statement": row}


@profit_fee_admin_router.post(
    "/statements/{statement_id}/issue",
    summary="Entwurf veroeffentlichen",
)
def admin_issue_statement(
    request: Request,
    statement_id: UUID,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    if not settings.profit_fee_module_enabled:
        raise HTTPException(status_code=404, detail="profit fee disabled")
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
            with conn.transaction():
                row = issue_statement(conn, statement_id=statement_id)
    except psycopg.errors.UndefinedTable:
        raise _migration_exc() from None
    if not row:
        raise _not_found()
    record_gateway_audit_line(
        request,
        auth,
        "commerce_admin_profit_fee_issue",
        extra={"id": str(statement_id)},
    )
    return {"schema_version": "profit-fee-issue-v1", "statement": row}


class AdminApproveBody(BaseModel):
    force_without_customer_ack: bool = False


@profit_fee_admin_router.post(
    "/statements/{statement_id}/approve",
    summary="Freigabe und HWM-Update",
)
def admin_approve_statement(
    request: Request,
    statement_id: UUID,
    body: AdminApproveBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    if not settings.profit_fee_module_enabled:
        raise HTTPException(status_code=404, detail="profit fee disabled")
    actor = auth.actor or "admin"
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
            with conn.transaction():
                st_full = fetch_statement(conn, statement_id=statement_id)
                if not st_full:
                    raise _not_found()
                if st_full["status"] not in ("issued", "disputed"):
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "code": "PROFIT_FEE_BAD_STATUS",
                            "message": "Nur issued oder disputed freigebbar.",
                        },
                    )
                disputed = st_full["status"] == "disputed"
                if disputed and not body.force_without_customer_ack:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "code": "PROFIT_FEE_DISPUTED",
                            "message": "Streitfall: force_without_customer_ack setzen.",
                        },
                    )
                if (
                    st_full.get("customer_ack_ts") is None
                    and not body.force_without_customer_ack
                ):
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "code": "PROFIT_FEE_ACK_REQUIRED",
                            "message": "Kunden-ACK oder force erforderlich.",
                        },
                    )
                row = approve_statement(
                    conn, statement_id=statement_id, admin_actor=actor
                )
    except HTTPException:
        raise
    except psycopg.errors.UndefinedTable:
        raise _migration_exc() from None
    if not row:
        raise _stale_hwm()
    record_gateway_audit_line(
        request,
        auth,
        "commerce_admin_profit_fee_approve",
        extra={"id": str(statement_id)},
    )
    return {"schema_version": "profit-fee-approve-v1", "statement": row}


class AdminVoidBody(BaseModel):
    reason: str = Field(min_length=4, max_length=4000)


@profit_fee_admin_router.post(
    "/statements/{statement_id}/void",
    summary="Statement stornieren",
)
def admin_void_statement_route(
    request: Request,
    statement_id: UUID,
    body: AdminVoidBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    if not settings.profit_fee_module_enabled:
        raise HTTPException(status_code=404, detail="profit fee disabled")
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
            with conn.transaction():
                row = void_statement(
                    conn, statement_id=statement_id, reason=body.reason
                )
    except psycopg.errors.UndefinedTable:
        raise _migration_exc() from None
    if not row or row.get("status") != "voided":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PROFIT_FEE_VOID_FAILED",
                "message": "Void nicht moeglich.",
            },
        )
    record_gateway_audit_line(
        request,
        auth,
        "commerce_admin_profit_fee_void",
        extra={"id": str(statement_id)},
    )
    return {"schema_version": "profit-fee-void-v1", "statement": row}


class AdminResolveDisputeBody(BaseModel):
    resolution_note: str = Field(min_length=4, max_length=2000)


@profit_fee_admin_router.post(
    "/statements/{statement_id}/resolve-dispute",
    summary="Streitfall schliessen, wieder issued",
)
def admin_resolve_dispute(
    request: Request,
    statement_id: UUID,
    body: AdminResolveDisputeBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    if not settings.profit_fee_module_enabled:
        raise HTTPException(status_code=404, detail="profit fee disabled")
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
            with conn.transaction():
                row = reopen_disputed_to_issued(
                    conn,
                    statement_id=statement_id,
                    resolution_note=body.resolution_note,
                )
    except psycopg.errors.UndefinedTable:
        raise _migration_exc() from None
    if not row or row.get("status") != "issued":
        raise HTTPException(
            status_code=409,
            detail={"code": "PROFIT_FEE_RESOLVE_FAILED", "message": "Nur disputed."},
        )
    record_gateway_audit_line(
        request,
        auth,
        "commerce_admin_profit_fee_resolve",
        extra={"id": str(statement_id)},
    )
    return {"schema_version": "profit-fee-resolve-v1", "statement": row}


@profit_fee_admin_router.get(
    "/statements",
    summary="Statements filtern",
)
def admin_list_statements(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
    tenant_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    if not settings.profit_fee_module_enabled:
        raise HTTPException(status_code=404, detail="profit fee disabled")
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
            rows = list_statements_admin(
                conn, tenant_id=tenant_id, status=status, limit=limit
            )
    except psycopg.errors.UndefinedTable:
        raise _migration_exc() from None
    record_gateway_audit_line(request, auth, "commerce_admin_profit_fee_list", extra={})
    return {"schema_version": "profit-fee-admin-list-v1", "statements": rows}
