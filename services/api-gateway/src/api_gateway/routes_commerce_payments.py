"""Webhooks: Stripe, Mock, Wise, PayPal-Stub — Rohbody, nur serverseitige Secrets."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, Header, Request
from psycopg.rows import dict_row
from pydantic import BaseModel

from api_gateway.audit import record_gateway_audit_line
from api_gateway.auth import GatewayAuthContext, require_billing_admin
from api_gateway.config import get_gateway_settings
from api_gateway.db import get_database_url
from api_gateway.db_payment_failure_log import (
    fetch_payment_rail_inbox_summary,
    list_payment_webhook_failures_recent,
)
from api_gateway.payments.capabilities import build_payment_capabilities
from api_gateway.payments.deposit import (
    process_mock_webhook,
    process_stripe_webhook_payload,
)
from api_gateway.payments.paypal_stub_webhook import process_paypal_stub_webhook
from api_gateway.payments.wise_webhook import process_wise_webhook

payments_router = APIRouter(prefix="/v1/commerce/payments", tags=["commerce-payments"])
payments_admin_router = APIRouter(
    prefix="/v1/commerce/admin/payments",
    tags=["commerce-payments"],
)


class MockWebhookBody(BaseModel):
    intent_id: UUID


@payments_router.post("/webhooks/stripe")
async def stripe_payment_webhook(request: Request) -> dict[str, Any]:
    settings = get_gateway_settings()
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=10) as conn:
        with conn.transaction():
            return process_stripe_webhook_payload(
                conn, settings, payload=payload, sig_header=sig
            )


@payments_router.post("/webhooks/mock")
def mock_payment_webhook(
    body: MockWebhookBody,
    x_payment_mock_secret: str | None = Header(
        default=None, alias="X-Payment-Mock-Secret"
    ),
) -> dict[str, Any]:
    settings = get_gateway_settings()
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=10) as conn:
        with conn.transaction():
            return process_mock_webhook(
                conn,
                settings,
                intent_id=body.intent_id,
                mock_secret_header=x_payment_mock_secret,
            )


@payments_router.post("/webhooks/wise")
async def wise_payment_webhook(
    request: Request,
    x_wise_signature: str | None = Header(default=None, alias="X-Wise-Signature"),
) -> dict[str, Any]:
    """Rohbody; HMAC-SHA256 hex in X-Wise-Signature (PAYMENT_WISE_WEBHOOK_SECRET)."""
    settings = get_gateway_settings()
    payload = await request.body()
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=10) as conn:
        with conn.transaction():
            return process_wise_webhook(
                conn,
                settings,
                body=payload,
                signature_header=x_wise_signature,
            )


@payments_router.post("/webhooks/paypal")
async def paypal_stub_payment_webhook(
    request: Request,
    x_paypal_stub_secret: str | None = Header(
        default=None, alias="X-Paypal-Stub-Secret"
    ),
) -> dict[str, Any]:
    """Dev-/Test-Stub bis PayPal Commerce/Subscriptions produktiv angebunden sind."""
    settings = get_gateway_settings()
    payload = await request.body()
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=10) as conn:
        with conn.transaction():
            return process_paypal_stub_webhook(
                conn,
                settings,
                body=payload,
                stub_secret_header=x_paypal_stub_secret,
            )


@payments_admin_router.get("/diagnostics")
def admin_payments_diagnostics(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    """Admin: Capabilities-Kurzform, Webhook-Failure-Log, Rail-Inbox-Zaehler."""
    record_gateway_audit_line(
        request, auth, "commerce_admin_payments_diagnostics", extra={}
    )
    settings = get_gateway_settings()
    caps = build_payment_capabilities(settings)
    methods_summary = [
        {
            "id": m["id"],
            "enabled": m.get("enabled"),
            "providers": m.get("providers"),
            "usage_constraint": m.get("usage_constraint"),
        }
        for m in caps["methods"]
    ]
    result: dict[str, Any] = {
        "capabilities": {
            "schema_version": caps["schema_version"],
            "checkout_enabled": caps["checkout_enabled"],
            "environment": caps["environment"],
            "commercial_enabled": caps["commercial_enabled"],
            "payment_checkout_enabled": caps["payment_checkout_enabled"],
            "stripe_checkout_events": caps["stripe_checkout_events"],
            "providers": caps["providers"],
            "methods": methods_summary,
        },
        "webhook_failure_log_recent": [],
        "rail_webhook_inbox_summary": [],
    }
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=10) as conn:
        result["webhook_failure_log_recent"] = list_payment_webhook_failures_recent(
            conn, limit=25
        )
        result["rail_webhook_inbox_summary"] = fetch_payment_rail_inbox_summary(conn)
    return result
