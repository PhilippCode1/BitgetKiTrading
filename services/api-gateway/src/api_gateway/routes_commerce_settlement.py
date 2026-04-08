"""Prompt 16: Treasury und kontrolliertes Settlement (keine Exchange-Auto-Payouts)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

import psycopg
import psycopg.errors
from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from api_gateway.audit import record_gateway_audit_line
from api_gateway.auth import GatewayAuthContext, require_billing_admin
from api_gateway.config import get_gateway_settings
from api_gateway.db import get_database_url
from api_gateway.db_settlement import (
    cancel_settlement_request,
    confirm_settlement_settled,
    create_settlement_request,
    fail_settlement_request,
    fetch_settlement,
    list_settlement_audit,
    list_settlements_admin,
    list_treasury_configs,
    record_payout_submission,
    treasury_approve_settlement,
    update_treasury_config,
)
from api_gateway.routes_commerce_customer import _ensure_commercial

treasury_admin_router = APIRouter(
    prefix="/v1/commerce/admin/treasury",
    tags=["commerce-settlement"],
)
settlement_admin_router = APIRouter(
    prefix="/v1/commerce/admin/settlements",
    tags=["commerce-settlement"],
)


def _settlement_migration_exc() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "code": "SETTLEMENT_MIGRATION_REQUIRED",
            "message": "612_profit_fee_settlement_treasury.sql",
        },
    )


def _ensure_settlement(settings: Any) -> None:
    _ensure_commercial(settings)
    mod = settings.profit_fee_module_enabled
    st = settings.profit_fee_settlement_enabled
    if not mod or not st:
        raise HTTPException(status_code=404, detail="settlement disabled")


@treasury_admin_router.get("/configs", summary="Treasury-Konfigurationen")
def admin_list_treasury_configs(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_settlement(settings)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
            rows = list_treasury_configs(conn)
    except psycopg.errors.UndefinedTable:
        raise _settlement_migration_exc() from None
    record_gateway_audit_line(request, auth, "commerce_admin_treasury_list", extra={})
    return {"schema_version": "treasury-configs-v1", "configs": rows}


class TreasuryPatchBody(BaseModel):
    target_asset: str | None = Field(default=None, max_length=32)
    network: str | None = Field(default=None, max_length=64)
    destination_hint_public: str | None = Field(default=None, max_length=2000)
    daily_limit_major_units: str | None = None
    monthly_limit_major_units: str | None = None
    active: bool | None = None
    manual_execution_only: bool | None = None


@treasury_admin_router.patch(
    "/configs/{config_id}",
    summary="Treasury-Config anpassen",
)
def admin_patch_treasury_config(
    request: Request,
    config_id: UUID,
    body: TreasuryPatchBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_settlement(settings)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
            with conn.transaction():
                row = update_treasury_config(
                    conn,
                    config_id=config_id,
                    target_asset=body.target_asset,
                    network=body.network,
                    destination_hint_public=body.destination_hint_public,
                    daily_limit_major_units=body.daily_limit_major_units,
                    monthly_limit_major_units=body.monthly_limit_major_units,
                    active=body.active,
                    manual_execution_only=body.manual_execution_only,
                )
    except psycopg.errors.UndefinedTable:
        raise _settlement_migration_exc() from None
    if not row:
        raise HTTPException(status_code=404, detail="config not found")
    record_gateway_audit_line(
        request, auth, "commerce_admin_treasury_patch", extra={"id": str(config_id)}
    )
    return {"schema_version": "treasury-config-patch-v1", "config": row}


class CreateSettlementBody(BaseModel):
    treasury_config_id: UUID | None = None


@settlement_admin_router.post(
    "/from-statement/{statement_id}",
    summary="Settlement aus freigegebenem Statement",
)
def admin_create_settlement_from_statement(
    request: Request,
    statement_id: UUID,
    body: CreateSettlementBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_settlement(settings)
    actor = auth.actor or "admin"
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
            with conn.transaction():
                row = create_settlement_request(
                    conn,
                    statement_id=statement_id,
                    treasury_config_id=body.treasury_config_id,
                    actor=actor,
                    secondary_treasury_approval_required=(
                        settings.profit_fee_settlement_treasury_secondary_approval
                    ),
                )
    except psycopg.errors.UniqueViolation as e:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "SETTLEMENT_ALREADY_OPEN_OR_SETTLED",
                "message": "Settlement zu diesem Statement bereits aktiv oder fertig.",
            },
        ) from e
    except psycopg.errors.UndefinedTable:
        raise _settlement_migration_exc() from None
    if not row:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "SETTLEMENT_CREATE_REJECTED",
                "message": "Statement ungueltig, Gebuehr 0 oder keine Treasury-Config.",
            },
        )
    record_gateway_audit_line(
        request,
        auth,
        "commerce_admin_settlement_create",
        extra={
            "statement_id": str(statement_id),
            "settlement_id": row["settlement_id"],
        },
    )
    return {"schema_version": "settlement-create-v1", "settlement": row}


@settlement_admin_router.post(
    "/{settlement_id}/treasury-approve",
    summary="Zweite Treasury-Freigabe",
)
def admin_settlement_treasury_approve(
    request: Request,
    settlement_id: UUID,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_settlement(settings)
    actor = auth.actor or "admin"
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
            with conn.transaction():
                row = treasury_approve_settlement(
                    conn, settlement_id=settlement_id, actor=actor
                )
    except psycopg.errors.UndefinedTable:
        raise _settlement_migration_exc() from None
    if not row:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "SETTLEMENT_TRANSITION_FAILED",
                "message": "Ungueltiger Status.",
            },
        )
    record_gateway_audit_line(
        request,
        auth,
        "commerce_admin_settlement_treasury_approve",
        extra={"id": str(settlement_id)},
    )
    return {"schema_version": "settlement-treasury-approve-v1", "settlement": row}


class RecordPayoutBody(BaseModel):
    external_submission_ref: str = Field(min_length=4, max_length=512)
    note: str | None = Field(default=None, max_length=4000)


@settlement_admin_router.post(
    "/{settlement_id}/record-payout",
    summary="Manuelle Ausfuehrung dokumentieren",
)
def admin_settlement_record_payout(
    request: Request,
    settlement_id: UUID,
    body: RecordPayoutBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_settlement(settings)
    actor = auth.actor or "admin"
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
            with conn.transaction():
                row = record_payout_submission(
                    conn,
                    settlement_id=settlement_id,
                    actor=actor,
                    external_submission_ref=body.external_submission_ref,
                    note=body.note,
                )
    except psycopg.errors.UndefinedTable:
        raise _settlement_migration_exc() from None
    if not row:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "SETTLEMENT_TRANSITION_FAILED",
                "message": "Ungueltiger Status.",
            },
        )
    record_gateway_audit_line(
        request,
        auth,
        "commerce_admin_settlement_record_payout",
        extra={"id": str(settlement_id)},
    )
    return {"schema_version": "settlement-record-payout-v1", "settlement": row}


class ConfirmSettledBody(BaseModel):
    confirmation_ref: str = Field(min_length=4, max_length=512)
    note: str | None = Field(default=None, max_length=4000)


@settlement_admin_router.post(
    "/{settlement_id}/confirm-settled",
    summary="Settlement abschliessen",
)
def admin_settlement_confirm(
    request: Request,
    settlement_id: UUID,
    body: ConfirmSettledBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_settlement(settings)
    actor = auth.actor or "admin"
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
            with conn.transaction():
                row = confirm_settlement_settled(
                    conn,
                    settlement_id=settlement_id,
                    actor=actor,
                    confirmation_ref=body.confirmation_ref,
                    note=body.note,
                )
    except psycopg.errors.UndefinedTable:
        raise _settlement_migration_exc() from None
    if not row:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "SETTLEMENT_TRANSITION_FAILED",
                "message": "Ungueltiger Status.",
            },
        )
    record_gateway_audit_line(
        request,
        auth,
        "commerce_admin_settlement_confirm",
        extra={"id": str(settlement_id)},
    )
    return {"schema_version": "settlement-confirm-v1", "settlement": row}


class CancelBody(BaseModel):
    reason: str = Field(min_length=4, max_length=4000)


@settlement_admin_router.post("/{settlement_id}/cancel", summary="Settlement abbrechen")
def admin_settlement_cancel(
    request: Request,
    settlement_id: UUID,
    body: CancelBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_settlement(settings)
    actor = auth.actor or "admin"
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
            with conn.transaction():
                row = cancel_settlement_request(
                    conn,
                    settlement_id=settlement_id,
                    actor=actor,
                    reason=body.reason,
                )
    except psycopg.errors.UndefinedTable:
        raise _settlement_migration_exc() from None
    if not row:
        raise HTTPException(
            status_code=409,
            detail={"code": "SETTLEMENT_CANCEL_FAILED", "message": "Nicht abbrechbar."},
        )
    record_gateway_audit_line(
        request,
        auth,
        "commerce_admin_settlement_cancel",
        extra={"id": str(settlement_id)},
    )
    return {"schema_version": "settlement-cancel-v1", "settlement": row}


class FailBody(BaseModel):
    reason: str = Field(min_length=4, max_length=4000)


@settlement_admin_router.post(
    "/{settlement_id}/fail",
    summary="Settlement fehlgeschlagen",
)
def admin_settlement_fail(
    request: Request,
    settlement_id: UUID,
    body: FailBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_settlement(settings)
    actor = auth.actor or "admin"
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
            with conn.transaction():
                row = fail_settlement_request(
                    conn,
                    settlement_id=settlement_id,
                    actor=actor,
                    reason=body.reason,
                )
    except psycopg.errors.UndefinedTable:
        raise _settlement_migration_exc() from None
    if not row:
        raise HTTPException(
            status_code=409,
            detail={"code": "SETTLEMENT_FAIL_FAILED", "message": "Nicht fehlbar."},
        )
    record_gateway_audit_line(
        request,
        auth,
        "commerce_admin_settlement_fail",
        extra={"id": str(settlement_id)},
    )
    return {"schema_version": "settlement-fail-v1", "settlement": row}


@settlement_admin_router.get("", summary="Settlements filtern")
def admin_list_settlements(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
    tenant_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_settlement(settings)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
            rows = list_settlements_admin(
                conn, tenant_id=tenant_id, status=status, limit=limit
            )
    except psycopg.errors.UndefinedTable:
        raise _settlement_migration_exc() from None
    record_gateway_audit_line(request, auth, "commerce_admin_settlement_list", extra={})
    return {"schema_version": "settlement-list-v1", "settlements": rows}


@settlement_admin_router.get("/{settlement_id}", summary="Settlement Detail")
def admin_get_settlement(
    request: Request,
    settlement_id: UUID,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_settlement(settings)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
            row = fetch_settlement(conn, settlement_id=settlement_id)
    except psycopg.errors.UndefinedTable:
        raise _settlement_migration_exc() from None
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    record_gateway_audit_line(
        request,
        auth,
        "commerce_admin_settlement_get",
        extra={"id": str(settlement_id)},
    )
    return {"schema_version": "settlement-get-v1", "settlement": row}


@settlement_admin_router.get("/{settlement_id}/audit", summary="Settlement Audit-Trail")
def admin_settlement_audit(
    request: Request,
    settlement_id: UUID,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
    limit: int = 200,
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_settlement(settings)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
            rows = list_settlement_audit(conn, settlement_id=settlement_id, limit=limit)
    except psycopg.errors.UndefinedTable:
        raise _settlement_migration_exc() from None
    record_gateway_audit_line(
        request,
        auth,
        "commerce_admin_settlement_audit",
        extra={"id": str(settlement_id)},
    )
    return {"schema_version": "settlement-audit-v1", "audit": rows}
