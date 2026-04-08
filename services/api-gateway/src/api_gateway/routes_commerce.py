"""Kommerzielle Transparenz-APIs: Plaene, Ledger, Metering (serverseitig)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from psycopg.rows import dict_row

from api_gateway.audit import record_gateway_audit_line
from api_gateway.auth import GatewayAuthContext, require_billing_read, require_sensitive_auth
from api_gateway.billing.daily_run import run_daily_billing
from api_gateway.commerce.pricing import llm_tokens_line_total_usd
from api_gateway.config import get_gateway_settings
from api_gateway.db import get_database_url
from api_gateway.db_commerce_queries import (
    fetch_ledger_recent,
    fetch_plan_definitions,
    fetch_plan_for_tenant,
    fetch_tenant_state,
    insert_usage_ledger_line,
    sum_ledger_usd_month,
    sum_llm_tokens_month,
)

router = APIRouter(prefix="/v1/commerce", tags=["commerce"])

_HEADER_METER = "X-Commercial-Meter-Secret"


class InternalBillingRunBody(BaseModel):
    accrual_date: str | None = Field(
        default=None,
        max_length=10,
        description="UTC-Datum YYYY-MM-DD; Standard heute.",
    )
    tenant_id: str | None = Field(
        default=None,
        max_length=128,
        description="Optional nur dieser Tenant (sonst alle).",
    )


class InternalUsageBody(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    event_type: str = Field(min_length=2, max_length=64)
    quantity: float = Field(ge=0)
    unit: str = Field(min_length=1, max_length=32)
    correlation_id: str | None = Field(default=None, max_length=128)
    meta_json: dict[str, Any] = Field(default_factory=dict)


def _resolve_target_tenant(ctx: GatewayAuthContext, query_tenant: str | None) -> str:
    settings = get_gateway_settings()
    default_tid = settings.commercial_default_tenant_id.strip() or "default"
    if ctx.can_admin_write() and query_tenant and query_tenant.strip():
        return query_tenant.strip()
    return ctx.effective_tenant(default_tenant_id=default_tid)


@router.get("/plans")
def list_plans(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    if not settings.commercial_enabled:
        raise HTTPException(status_code=404, detail="commercial module disabled")
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        items = fetch_plan_definitions(conn)
    record_gateway_audit_line(request, auth, "commerce_plans_list", extra={})
    return {"items": items, "transparency_note_de": "Preise = List-Referenz; keine Laufzeit-Multiplikatoren."}


@router.get("/usage/summary")
def usage_summary(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
    tenant_id: str | None = None,
) -> dict[str, Any]:
    settings = get_gateway_settings()
    if not settings.commercial_enabled:
        raise HTTPException(status_code=404, detail="commercial module disabled")
    tid = _resolve_target_tenant(auth, tenant_id)
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        plan = fetch_plan_for_tenant(conn, tenant_id=tid)
        tstate = fetch_tenant_state(conn, tenant_id=tid)
        month_usd = sum_ledger_usd_month(conn, tenant_id=tid)
        llm_tok = sum_llm_tokens_month(conn, tenant_id=tid)
    cap = plan.get("llm_monthly_token_cap") if plan else None
    budget = tstate.get("budget_cap_usd_month") if tstate else None
    cap_exceeded = cap is not None and float(llm_tok) > float(cap)
    budget_exceeded = budget is not None and month_usd > Decimal(str(budget))
    record_gateway_audit_line(
        request, auth, "commerce_usage_summary", extra={"tenant_id": tid}
    )
    return {
        "tenant_id": tid,
        "plan": plan,
        "tenant_state": tstate,
        "month_utc": {
            "ledger_total_list_usd": str(month_usd),
            "llm_tokens_used": str(llm_tok),
            "llm_monthly_token_cap": cap,
            "budget_cap_usd_month": str(budget) if budget is not None else None,
            "cap_exceeded": cap_exceeded,
            "budget_exceeded": budget_exceeded,
        },
    }


@router.get("/usage/ledger")
def usage_ledger(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
    tenant_id: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    settings = get_gateway_settings()
    if not settings.commercial_enabled:
        raise HTTPException(status_code=404, detail="commercial module disabled")
    tid = _resolve_target_tenant(auth, tenant_id)
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        items = fetch_ledger_recent(conn, tenant_id=tid, limit=limit)
    record_gateway_audit_line(
        request, auth, "commerce_ledger_list", extra={"tenant_id": tid, "limit": limit}
    )
    return {"tenant_id": tid, "items": items}


@router.get("/invoice-preview")
def invoice_preview(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Aggregat aus Ledger (kein externes Billing); fuer Owner-Transparenz."""
    settings = get_gateway_settings()
    if not settings.commercial_enabled:
        raise HTTPException(status_code=404, detail="commercial module disabled")
    tid = _resolve_target_tenant(auth, tenant_id)
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        lines = fetch_ledger_recent(conn, tenant_id=tid, limit=500)
        total = sum_ledger_usd_month(conn, tenant_id=tid)
        plan = fetch_plan_for_tenant(conn, tenant_id=tid)
    record_gateway_audit_line(
        request, auth, "commerce_invoice_preview", extra={"tenant_id": tid}
    )
    return {
        "schema_version": "invoice-preview-v1",
        "tenant_id": tid,
        "plan": plan,
        "month_utc_subtotal_list_usd": str(total),
        "line_items_recent": lines,
        "disclaimer_de": (
            "Summen aus usage_ledger (List-USD). Steuern/Netto nicht enthalten; "
            "keine stillen Aufschlaege (platform_markup_factor=1)."
        ),
    }


@router.post("/internal/usage")
def internal_record_usage(
    request: Request,
    body: InternalUsageBody,
    x_commercial_meter_secret: Annotated[str | None, Header(alias=_HEADER_METER)] = None,
) -> dict[str, Any]:
    settings = get_gateway_settings()
    if not settings.commercial_enabled:
        raise HTTPException(status_code=404, detail="commercial module disabled")
    expected = settings.commercial_meter_secret.strip()
    if not expected or (x_commercial_meter_secret or "").strip() != expected:
        raise HTTPException(status_code=401, detail="commercial meter secret required")
    tid = body.tenant_id.strip()
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        plan = fetch_plan_for_tenant(conn, tenant_id=tid)
        if plan is None:
            raise HTTPException(status_code=400, detail="unknown tenant or plan")
        tstate = fetch_tenant_state(conn, tenant_id=tid)
        unit_price: Decimal | None = None
        line_total: Decimal
        meta = dict(body.meta_json)
        meta.setdefault("pricing_formula", "transparent_list")
        meta["platform_markup_factor_fixed"] = "1.0"

        if body.event_type == "llm_tokens":
            raw_p = plan.get("llm_per_1k_tokens_list_usd")
            if raw_p is None:
                raise HTTPException(status_code=400, detail="plan ohne Token-Listenpreis")
            unit_price = Decimal(str(raw_p))
            line_total = llm_tokens_line_total_usd(
                token_count=body.quantity, usd_per_1k_tokens=unit_price
            )
            used = sum_llm_tokens_month(conn, tenant_id=tid)
            cap = plan.get("llm_monthly_token_cap")
            if cap is not None and float(used) + body.quantity > float(cap):
                raise HTTPException(
                    status_code=402,
                    detail={
                        "code": "LLM_TOKEN_CAP_EXCEEDED",
                        "message": "Plan-Token-Cap fuer Monat wuerde ueberschritten.",
                    },
                )
        else:
            line_total = Decimal("0")
            unit_price = None
            meta.setdefault("note", "non-billable or zero-priced event type")

        month_usd = sum_ledger_usd_month(conn, tenant_id=tid)
        budget = tstate.get("budget_cap_usd_month") if tstate else None
        if budget is not None and month_usd + line_total > Decimal(str(budget)):
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "BUDGET_CAP_EXCEEDED",
                    "message": "Monatsbudget wuerde ueberschritten.",
                },
            )

        with conn.transaction():
            lid = insert_usage_ledger_line(
                conn,
                tenant_id=tid,
                event_type=body.event_type,
                quantity=Decimal(str(body.quantity)),
                unit=body.unit.strip(),
                unit_price_list_usd=unit_price,
                line_total_list_usd=line_total,
                correlation_id=body.correlation_id,
                actor="meter_ingest",
                meta_json=meta,
            )
    record_gateway_audit_line(
        request,
        GatewayAuthContext(
            actor="commercial_meter",
            auth_method="meter_secret",
            roles=frozenset({"billing:admin"}),
            tenant_id=None,
            portal_roles=frozenset(),
        ),
        "commerce_internal_usage_recorded",
        extra={"tenant_id": tid, "event_type": body.event_type, "ledger_id": str(lid)},
    )
    return {"status": "ok", "ledger_id": str(lid)}


@router.post("/internal/billing/run-daily")
def internal_billing_run_daily(
    request: Request,
    body: InternalBillingRunBody,
    x_commercial_meter_secret: Annotated[str | None, Header(alias=_HEADER_METER)] = None,
) -> dict[str, Any]:
    settings = get_gateway_settings()
    if not settings.commercial_enabled:
        raise HTTPException(status_code=404, detail="commercial module disabled")
    expected = settings.commercial_meter_secret.strip()
    if not expected or (x_commercial_meter_secret or "").strip() != expected:
        raise HTTPException(status_code=401, detail="commercial meter secret required")
    accrual: date | None = None
    if body.accrual_date and body.accrual_date.strip():
        try:
            accrual = date.fromisoformat(body.accrual_date.strip())
        except ValueError as e:
            raise HTTPException(status_code=400, detail="invalid accrual_date") from e
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=15) as conn:
        out = run_daily_billing(
            conn,
            settings=settings,
            accrual_date=accrual,
            tenant_id_filter=body.tenant_id.strip() if body.tenant_id else None,
        )
    if (
        body.tenant_id
        and body.tenant_id.strip()
        and out.get("status") == "ok"
        and not out.get("results")
    ):
        raise HTTPException(
            status_code=404,
            detail="tenant not found or no commercial tenant for billing",
        )
    record_gateway_audit_line(
        request,
        GatewayAuthContext(
            actor="commercial_meter",
            auth_method="meter_secret",
            roles=frozenset({"billing:admin"}),
            tenant_id=None,
            portal_roles=frozenset(),
        ),
        "commerce_internal_billing_run_daily",
        extra={"accrual_date": out.get("accrual_date")},
    )
    return out
