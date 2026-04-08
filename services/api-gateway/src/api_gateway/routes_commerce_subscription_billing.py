"""Prompt 13: Abo-Katalog, USt, Rechnungen, Finanz-Ledger (Kunde + Admin)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

import psycopg
import psycopg.errors
from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from api_gateway.audit import record_gateway_audit_line
from api_gateway.auth import GatewayAuthContext, require_billing_admin, require_billing_read
from api_gateway.config import get_gateway_settings
from api_gateway.db import get_database_url
from api_gateway.db_subscription_billing import (
    assign_subscription_plan,
    cancel_subscription,
    fetch_invoice_header,
    fetch_invoice_lines,
    fetch_tenant_subscription,
    issue_full_credit_note,
    issue_subscription_invoice,
    list_active_plans,
    list_all_subscriptions_admin,
    list_invoices_for_tenant,
    list_ledger_for_tenant,
    record_payment_allocation,
    record_renewal_event,
    update_dunning_stage,
)
from api_gateway.routes_commerce_customer import (
    _ensure_commercial,
    _require_tenant_commercial_state,
    _resolve_target_tenant,
)
from api_gateway.subscription_billing_amounts import plan_row_to_public_amounts

billing_customer_router = APIRouter(
    prefix="/v1/commerce/customer/billing",
    tags=["commerce-billing"],
)
billing_admin_router = APIRouter(
    prefix="/v1/commerce/admin/billing",
    tags=["commerce-billing"],
)


def _http(code: str, message: str, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


class AdminIssueInvoiceBody(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    plan_code: str = Field(min_length=2, max_length=64)
    period_label: str | None = Field(default=None, max_length=120)


class AdminCreditInvoiceBody(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    credits_invoice_id: UUID


class AdminDunningBody(BaseModel):
    dunning_stage: str = Field(min_length=2, max_length=64)


class AdminAssignPlanBody(BaseModel):
    plan_code: str = Field(min_length=2, max_length=64)


class AdminCancelBody(BaseModel):
    cancel_at_period_end: bool = False


class AdminRenewalBody(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class AdminPaymentAllocateBody(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    amount_gross_cents: int = Field(..., description="Brutto-Cent (kann negativ sein fuer Rueckbuchung)")
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    payment_intent_id: str | None = Field(default=None, max_length=64)


@billing_customer_router.get("/plans", summary="Abo-Preisliste (netto/USt/brutto)")
def customer_billing_plans(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            _require_tenant_commercial_state(conn, tid)
            raw = list_active_plans(conn)
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "BILLING_MIGRATION_REQUIRED", "message": "609_subscription_billing_ledger"},
        ) from None
    plans = [plan_row_to_public_amounts(dict(r)) for r in raw]
    record_gateway_audit_line(request, auth, "commerce_customer_billing_plans", extra={"tenant_id": tid})
    return {"schema_version": "billing-plans-v1", "plans": plans}


@billing_customer_router.get("/subscription", summary="Eigenes Abo und Mahnstatus")
def customer_billing_subscription(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            _require_tenant_commercial_state(conn, tid)
            sub = fetch_tenant_subscription(conn, tenant_id=tid)
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "BILLING_MIGRATION_REQUIRED", "message": "609_subscription_billing_ledger"},
        ) from None
    record_gateway_audit_line(request, auth, "commerce_customer_billing_subscription", extra={"tenant_id": tid})
    if sub is None:
        return {"schema_version": "tenant-subscription-v1", "subscription": None}
    preview = plan_row_to_public_amounts(
        {
            "plan_code": sub["plan_code"],
            "billing_interval": sub["billing_interval"],
            "display_name_de": sub["display_name_de"],
            "net_amount_cents": sub["net_amount_cents"],
            "currency": sub["currency"],
            "vat_rate_bps": sub["vat_rate_bps"],
        }
    )
    pub = {k: v for k, v in sub.items() if k not in ("meta_json",)}
    pub["pricing_preview"] = preview
    return {"schema_version": "tenant-subscription-v1", "subscription": pub}


@billing_customer_router.get("/invoices", summary="Rechnungen und Gutschriften")
def customer_billing_invoices(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            _require_tenant_commercial_state(conn, tid)
            items = list_invoices_for_tenant(conn, tenant_id=tid, limit=50)
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "BILLING_MIGRATION_REQUIRED", "message": "609_subscription_billing_ledger"},
        ) from None
    record_gateway_audit_line(request, auth, "commerce_customer_billing_invoices", extra={"tenant_id": tid})
    return {"schema_version": "billing-invoices-v1", "invoices": items}


@billing_customer_router.get(
    "/invoices/{invoice_id}/lines",
    summary="Positionen zu einer Rechnung",
)
def customer_billing_invoice_lines(
    request: Request,
    invoice_id: UUID,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            _require_tenant_commercial_state(conn, tid)
            inv = fetch_invoice_header(conn, invoice_id=invoice_id, tenant_id=tid)
            if inv is None:
                raise HTTPException(status_code=404, detail="invoice not found")
            lines = fetch_invoice_lines(conn, invoice_id=invoice_id)
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "BILLING_MIGRATION_REQUIRED", "message": "609_subscription_billing_ledger"},
        ) from None
    record_gateway_audit_line(
        request,
        auth,
        "commerce_customer_billing_invoice_lines",
        extra={"tenant_id": tid, "invoice_id": str(invoice_id)},
    )
    inv_d = dict(inv)
    inv_d["invoice_id"] = str(inv_d["invoice_id"])
    if inv_d.get("credits_invoice_id") is not None:
        inv_d["credits_invoice_id"] = str(inv_d["credits_invoice_id"])
    for tk in ("issued_ts", "due_ts", "paid_ts", "created_ts"):
        tv = inv_d.get(tk)
        if tv is not None and hasattr(tv, "isoformat"):
            inv_d[tk] = tv.isoformat()
    return {
        "schema_version": "billing-invoice-detail-v1",
        "invoice": inv_d,
        "lines": lines,
    }


@billing_customer_router.get("/ledger", summary="Finanz-Journal (Kunde)")
def customer_billing_ledger(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            _require_tenant_commercial_state(conn, tid)
            items = list_ledger_for_tenant(conn, tenant_id=tid, limit=80)
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "BILLING_MIGRATION_REQUIRED", "message": "609_subscription_billing_ledger"},
        ) from None
    record_gateway_audit_line(request, auth, "commerce_customer_billing_ledger", extra={"tenant_id": tid})
    return {"schema_version": "billing-financial-ledger-v1", "entries": items}


@billing_admin_router.get("/tenant/{tenant_id}/snapshot", summary="Abo + Rechnungen + Ledger")
def admin_billing_tenant_snapshot(
    request: Request,
    tenant_id: str,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=10) as conn:
            _require_tenant_commercial_state(conn, tenant_id)
            sub = fetch_tenant_subscription(conn, tenant_id=tenant_id)
            invoices = list_invoices_for_tenant(conn, tenant_id=tenant_id, limit=25)
            ledger = list_ledger_for_tenant(conn, tenant_id=tenant_id, limit=40)
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "BILLING_MIGRATION_REQUIRED", "message": "609_subscription_billing_ledger"},
        ) from None
    record_gateway_audit_line(
        request, auth, "commerce_admin_billing_snapshot", extra={"tenant_id": tenant_id}
    )
    return {
        "schema_version": "admin-billing-snapshot-v1",
        "tenant_id": tenant_id,
        "subscription": sub,
        "invoices": invoices,
        "ledger": ledger,
    }


@billing_admin_router.get("/subscriptions", summary="Alle Mandanten-Abos (Admin)")
def admin_billing_subscriptions(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
    limit: int = 100,
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            rows = list_all_subscriptions_admin(conn, limit=limit)
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "BILLING_MIGRATION_REQUIRED", "message": "609_subscription_billing_ledger"},
        ) from None
    record_gateway_audit_line(request, auth, "commerce_admin_billing_subscriptions", extra={})
    return {"schema_version": "admin-billing-subscriptions-v1", "subscriptions": rows}


@billing_admin_router.post("/invoices/issue", summary="Rechnung aus Plan ausstellen")
def admin_billing_issue_invoice(
    request: Request,
    body: AdminIssueInvoiceBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=10) as conn:
            _require_tenant_commercial_state(conn, body.tenant_id)
            with conn.transaction():
                out = issue_subscription_invoice(
                    conn,
                    tenant_id=body.tenant_id,
                    plan_code=body.plan_code,
                    actor=auth.actor,
                    period_label=body.period_label,
                )
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "BILLING_MIGRATION_REQUIRED", "message": "609_subscription_billing_ledger"},
        ) from None
    except ValueError as e:
        raise _http(str(e), str(e), 404) from e
    record_gateway_audit_line(
        request,
        auth,
        "commerce_admin_billing_issue_invoice",
        extra={"tenant_id": body.tenant_id, "invoice_id": out.get("invoice_id")},
    )
    return {"schema_version": "billing-issue-invoice-v1", **out}


@billing_admin_router.post("/invoices/credit", summary="Volle Gutschrift zu Rechnung")
def admin_billing_credit_invoice(
    request: Request,
    body: AdminCreditInvoiceBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=10) as conn:
            _require_tenant_commercial_state(conn, body.tenant_id)
            with conn.transaction():
                out = issue_full_credit_note(
                    conn,
                    tenant_id=body.tenant_id,
                    credits_invoice_id=body.credits_invoice_id,
                    actor=auth.actor,
                )
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "BILLING_MIGRATION_REQUIRED", "message": "609_subscription_billing_ledger"},
        ) from None
    except ValueError as e:
        raise _http(str(e), str(e), 409) from e
    record_gateway_audit_line(
        request,
        auth,
        "commerce_admin_billing_credit_invoice",
        extra={"tenant_id": body.tenant_id},
    )
    return {"schema_version": "billing-credit-invoice-v1", **out}


@billing_admin_router.patch("/tenant/{tenant_id}/dunning", summary="Mahnstufe setzen")
def admin_billing_dunning(
    request: Request,
    tenant_id: str,
    body: AdminDunningBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=10) as conn:
            _require_tenant_commercial_state(conn, tenant_id)
            with conn.transaction():
                update_dunning_stage(
                    conn,
                    tenant_id=tenant_id,
                    dunning_stage=body.dunning_stage,
                    actor=auth.actor,
                )
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "BILLING_MIGRATION_REQUIRED", "message": "609_subscription_billing_ledger"},
        ) from None
    except ValueError as e:
        raise _http(str(e), str(e), 404) from e
    record_gateway_audit_line(
        request, auth, "commerce_admin_billing_dunning", extra={"tenant_id": tenant_id}
    )
    return {"schema_version": "billing-dunning-v1", "tenant_id": tenant_id, "dunning_stage": body.dunning_stage}


@billing_admin_router.post("/tenant/{tenant_id}/plan", summary="Abo-Plan zuweisen/aendern")
def admin_billing_assign_plan(
    request: Request,
    tenant_id: str,
    body: AdminAssignPlanBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=10) as conn:
            _require_tenant_commercial_state(conn, tenant_id)
            with conn.transaction():
                assign_subscription_plan(
                    conn,
                    tenant_id=tenant_id,
                    plan_code=body.plan_code,
                    actor=auth.actor,
                )
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "BILLING_MIGRATION_REQUIRED", "message": "609_subscription_billing_ledger"},
        ) from None
    except ValueError as e:
        raise _http(str(e), str(e), 404) from e
    record_gateway_audit_line(
        request, auth, "commerce_admin_billing_assign_plan", extra={"tenant_id": tenant_id}
    )
    return {"schema_version": "billing-assign-plan-v1", "tenant_id": tenant_id, "plan_code": body.plan_code}


@billing_admin_router.post("/tenant/{tenant_id}/cancel", summary="Kuendigung")
def admin_billing_cancel(
    request: Request,
    tenant_id: str,
    body: AdminCancelBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=10) as conn:
            _require_tenant_commercial_state(conn, tenant_id)
            with conn.transaction():
                cancel_subscription(
                    conn,
                    tenant_id=tenant_id,
                    actor=auth.actor,
                    cancel_at_period_end=body.cancel_at_period_end,
                )
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "BILLING_MIGRATION_REQUIRED", "message": "609_subscription_billing_ledger"},
        ) from None
    except ValueError as e:
        raise _http(str(e), str(e), 404) from e
    record_gateway_audit_line(
        request, auth, "commerce_admin_billing_cancel", extra={"tenant_id": tenant_id}
    )
    return {
        "schema_version": "billing-cancel-v1",
        "tenant_id": tenant_id,
        "cancel_at_period_end": body.cancel_at_period_end,
    }


@billing_admin_router.post("/tenant/{tenant_id}/renewal", summary="Verlaengerung protokollieren")
def admin_billing_renewal(
    request: Request,
    tenant_id: str,
    body: AdminRenewalBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    dsn = get_database_url()
    meta = {"note": body.note} if body.note else {}
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=10) as conn:
            _require_tenant_commercial_state(conn, tenant_id)
            with conn.transaction():
                record_renewal_event(conn, tenant_id=tenant_id, actor=auth.actor, meta_json=meta)
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "BILLING_MIGRATION_REQUIRED", "message": "609_subscription_billing_ledger"},
        ) from None
    except ValueError as e:
        raise _http(str(e), str(e), 404) from e
    record_gateway_audit_line(
        request, auth, "commerce_admin_billing_renewal", extra={"tenant_id": tenant_id}
    )
    return {"schema_version": "billing-renewal-v1", "tenant_id": tenant_id}


@billing_admin_router.post("/payments/allocate", summary="Zahlungszuordnung (Journal)")
def admin_billing_payment_allocate(
    request: Request,
    body: AdminPaymentAllocateBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    dsn = get_database_url()
    meta: dict[str, Any] = {}
    if body.payment_intent_id:
        meta["payment_intent_id"] = body.payment_intent_id
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=10) as conn:
            _require_tenant_commercial_state(conn, body.tenant_id)
            with conn.transaction():
                record_payment_allocation(
                    conn,
                    tenant_id=body.tenant_id,
                    actor=auth.actor,
                    amount_gross_cents=body.amount_gross_cents,
                    currency=body.currency,
                    meta_json=meta,
                )
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "BILLING_MIGRATION_REQUIRED", "message": "609_subscription_billing_ledger"},
        ) from None
    record_gateway_audit_line(
        request,
        auth,
        "commerce_admin_billing_payment_allocate",
        extra={"tenant_id": body.tenant_id},
    )
    return {"schema_version": "billing-payment-allocate-v1", "ok": True}
