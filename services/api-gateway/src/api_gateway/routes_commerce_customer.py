"""Kundenbereich-APIs und Commerce-Admin (tenant-scoped); keine Secrets im Response."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

import psycopg
import psycopg.errors
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from psycopg.rows import dict_row
from pydantic import BaseModel, Field
from shared_py.billing_wallet import fetch_prepaid_balance_list_usd
from shared_py.customer_lifecycle import CustomerLifecycleStatus, TransitionActor
from shared_py.customer_telegram_prefs import (
    audit_prefs_changed,
    fetch_notify_prefs_merged,
    upsert_notify_prefs,
)
from shared_py.customer_telegram_repo import (
    create_pending_link,
    get_binding_row,
    is_telegram_connected,
    mask_chat_id,
)

from api_gateway.audit import record_gateway_audit_line
from api_gateway.auth import (
    GatewayAuthContext,
    require_billing_admin,
    require_billing_read,
)
from api_gateway.billing.daily_run import build_billing_status_public
from api_gateway.config import get_gateway_settings
from api_gateway.db import get_database_url
from api_gateway.db_billing import (
    fetch_billing_accruals_recent,
    fetch_billing_alerts_recent,
)
from api_gateway.db_commerce_queries import (
    fetch_plan_for_tenant,
    fetch_tenant_state,
    sum_ledger_usd_month,
    sum_llm_tokens_month,
)
from api_gateway.db_customer_portal import (
    adjust_wallet_balance,
    fetch_customer_profile,
    fetch_customer_wallet,
    fetch_integration_snapshot,
    fetch_ledger_customer_safe,
    fetch_payment_events,
    fetch_portal_audit_recent,
    fetch_portal_identity_security,
    insert_payment_event,
    sanitize_display_name,
    update_customer_display_name,
    upsert_integration_snapshot,
)
from api_gateway.db_payment_intents import fetch_intent_by_id
from api_gateway.db_tenant_lifecycle import (
    apply_trial_expiry_if_due,
    build_lifecycle_public_payload,
    fetch_lifecycle_audit_recent,
    fetch_tenant_lifecycle_row,
    set_email_verified,
    transition_lifecycle,
)
from api_gateway.payments.capabilities import build_payment_capabilities
from api_gateway.payments.deposit import resume_stripe_checkout, start_deposit_checkout
from api_gateway.provider_ops_summary import bitget_env_hints_for_customer_portal
from api_gateway.telegram_customer_notify import enqueue_customer_notify

customer_router = APIRouter(prefix="/v1/commerce/customer", tags=["commerce-customer"])
admin_customer_router = APIRouter(
    prefix="/v1/commerce/admin/customer", tags=["commerce-admin-customer"]
)


def _resolve_target_tenant(ctx: GatewayAuthContext, query_tenant: str | None) -> str:
    settings = get_gateway_settings()
    default_tid = settings.commercial_default_tenant_id.strip() or "default"
    if ctx.can_admin_write() and query_tenant and query_tenant.strip():
        return query_tenant.strip()
    return ctx.effective_tenant(default_tenant_id=default_tid)


def _mask_checkout_ref(ref: str, *, keep: int = 8) -> str:
    r = ref.strip()
    if len(r) <= keep:
        return "***"
    return f"…{r[-keep:]}"


def _public_deposit_intent(row: dict[str, Any]) -> dict[str, Any]:
    d: dict[str, Any] = {
        "intent_id": row["intent_id"],
        "status": row["status"],
        "environment": row.get("environment"),
        "provider": row.get("provider"),
        "amount_list_usd": row.get("amount_list_usd"),
        "currency": row.get("currency"),
        "last_error_public": row.get("last_error_public"),
    }
    if str(row.get("status") or "") == "succeeded":
        d["receipt"] = row.get("receipt_json") if row.get("receipt_json") is not None else {}
    sid = row.get("provider_checkout_session_id")
    if sid:
        d["provider_checkout_session_id_masked"] = _mask_checkout_ref(str(sid))
    return d


def _mask_tenant_id(tid: str) -> str:
    t = tid.strip()
    if len(t) <= 8:
        return f"{t[:2]}…" if len(t) > 2 else t
    return f"{t[:4]}…{t[-4:]}"


class CustomerMePatch(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)


class DepositCheckoutBody(BaseModel):
    provider: str = Field(default="stripe", min_length=2, max_length=32)
    amount_list_usd: float = Field(ge=0.5, le=1_000_000)
    currency: str = Field(default="USD", max_length=8)


class DepositResumeBody(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=128)


class AdminPaymentBody(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    amount_list_usd: float = Field(ge=0)
    currency: str = Field(default="USD", max_length=8)
    status: str = Field(min_length=2, max_length=32)
    provider: str = Field(default="manual", max_length=32)
    provider_reference_masked: str | None = Field(default=None, max_length=64)
    notes_public: str | None = Field(default=None, max_length=500)


class AdminWalletAdjustBody(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    delta_list_usd: float
    reason_code: str = Field(min_length=2, max_length=64)


class AdminIntegrationBody(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    telegram_state: str = Field(min_length=2, max_length=48)
    telegram_hint_public: str | None = Field(default=None, max_length=500)
    broker_state: str = Field(min_length=2, max_length=48)
    broker_hint_public: str | None = Field(default=None, max_length=500)


class TelegramNotifyPrefsPatch(BaseModel):
    notify_orders_demo: bool | None = None
    notify_orders_live: bool | None = None
    notify_billing: bool | None = None
    notify_contract: bool | None = None
    notify_risk: bool | None = None
    notify_ai_tip: bool | None = None


class AdminLifecycleTransitionBody(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    to_status: str = Field(min_length=3, max_length=64)
    reason_code: str | None = Field(default=None, max_length=128)


class AdminLifecycleEmailBody(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    email_verified: bool = True


def _ensure_commercial(settings: Any) -> None:
    if not settings.commercial_enabled:
        raise HTTPException(status_code=404, detail="commercial module disabled")


def _require_tenant_commercial_state(conn: psycopg.Connection[Any], tenant_id: str) -> None:
    row = conn.execute(
        "SELECT 1 FROM app.tenant_commercial_state WHERE tenant_id = %s",
        (tenant_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="tenant has no commercial state")


@customer_router.get(
    "/me",
    summary="Kundenprofil und Berechtigungen",
    description="Tenant, Plan, Telegram-Zusammenfassung, access_matrix — JWT/billing:read.",
)
def customer_me(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    tg_summary: dict[str, Any] = {
        "connected": False,
        "console_telegram_required": settings.commercial_telegram_required_for_console,
    }
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        _require_tenant_commercial_state(conn, tid)
        profile = fetch_customer_profile(conn, tenant_id=tid)
        plan = fetch_plan_for_tenant(conn, tenant_id=tid)
        tstate = fetch_tenant_state(conn, tenant_id=tid)
        try:
            tg_summary["connected"] = is_telegram_connected(conn, tenant_id=tid)
        except psycopg.errors.UndefinedTable:
            tg_summary["migration_required"] = True
    record_gateway_audit_line(
        request, auth, "commerce_customer_me", extra={"tenant_id": tid}
    )
    return {
        "schema_version": "customer-me-v1",
        "tenant": {"id_masked": _mask_tenant_id(tid)},
        "profile": profile,
        "plan": plan,
        "tenant_state": tstate,
        "access": auth.access_matrix(),
        "telegram": tg_summary,
    }


@customer_router.get(
    "/security/summary",
    summary="Konto-Sicherheit (Flags, keine Secrets)",
    description=(
        "E-Mail-Verifikation, MFA- und Passwort-Login-Status je Tenant; "
        "Migration 606. Vollstaendige Flows (Reset, Session, OTP) werden angebunden."
    ),
)
def customer_security_summary(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        _require_tenant_commercial_state(conn, tid)
        try:
            row = fetch_portal_identity_security(conn, tenant_id=tid)
        except psycopg.errors.UndefinedTable:
            row = None
    record_gateway_audit_line(
        request, auth, "commerce_customer_security_summary", extra={"tenant_id": tid}
    )
    if row is None:
        return {
            "schema_version": "portal-security-v1",
            "migration_required": True,
            "email_verified": False,
            "mfa_totp_enabled": False,
            "password_login_configured": False,
        }
    return {
        "schema_version": "portal-security-v1",
        "migration_required": False,
        "email_verified": row.get("email_verified_at") is not None,
        "email_verified_at": row.get("email_verified_at"),
        "mfa_totp_enabled": bool(row.get("mfa_totp_enabled")),
        "password_login_configured": bool(row.get("password_login_configured")),
        "updated_ts": row.get("updated_ts"),
    }


def _http_lifecycle_reject(message: str) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"code": "LIFECYCLE_TRANSITION_REJECTED", "message": message},
    )


@customer_router.get(
    "/lifecycle/me",
    summary="Kundenlebenszyklus (Prompt 11)",
    description=(
        "Status, Trial-Fenster, deutschsprachiger Titel, Capabilities und Gate-Vorschau. "
        "Trial-Ablauf wird lazy nach DB-Zeit ausgewertet und bei Bedarf persistiert."
    ),
)
def customer_lifecycle_me(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        _require_tenant_commercial_state(conn, tid)
        try:
            apply_trial_expiry_if_due(conn, tenant_id=tid, actor=auth.actor)
            row = fetch_tenant_lifecycle_row(conn, tenant_id=tid)
        except psycopg.errors.UndefinedTable:
            raise HTTPException(
                status_code=503,
                detail={"code": "LIFECYCLE_MIGRATION_REQUIRED", "message": "607_tenant_customer_lifecycle"},
            ) from None
    if row is None:
        raise HTTPException(status_code=404, detail="tenant lifecycle not provisioned")
    record_gateway_audit_line(
        request, auth, "commerce_customer_lifecycle_me", extra={"tenant_id": tid}
    )
    return build_lifecycle_public_payload(row)


@customer_router.get(
    "/lifecycle/audit",
    summary="Lifecycle-Audit (letzte Eintraege)",
)
def customer_lifecycle_audit(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
    limit: int = 40,
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        _require_tenant_commercial_state(conn, tid)
        try:
            rows = fetch_lifecycle_audit_recent(conn, tenant_id=tid, limit=limit)
        except psycopg.errors.UndefinedTable:
            raise HTTPException(
                status_code=503,
                detail={"code": "LIFECYCLE_MIGRATION_REQUIRED", "message": "607_tenant_customer_lifecycle"},
            ) from None
    record_gateway_audit_line(
        request, auth, "commerce_customer_lifecycle_audit", extra={"tenant_id": tid}
    )
    return {"schema_version": "tenant-lifecycle-audit-v1", "items": rows}


@customer_router.post(
    "/lifecycle/start-trial",
    summary="21-Tage-Trial starten",
    description="Nur aus `registered` mit verifizierter E-Mail; setzt trial_started_at / trial_ends_at.",
)
def customer_lifecycle_start_trial(
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
            transition_lifecycle(
                conn,
                tenant_id=tid,
                to_status=CustomerLifecycleStatus.TRIAL_ACTIVE,
                actor=auth.actor,
                actor_role=TransitionActor.USER,
                reason_code="user_start_trial",
                meta_json={},
            )
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "LIFECYCLE_MIGRATION_REQUIRED", "message": "607_tenant_customer_lifecycle"},
        ) from None
    except ValueError as e:
        raise _http_lifecycle_reject(str(e)) from e
    record_gateway_audit_line(
        request, auth, "commerce_customer_lifecycle_start_trial", extra={"tenant_id": tid}
    )
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        row = fetch_tenant_lifecycle_row(conn, tenant_id=tid)
    assert row is not None
    return build_lifecycle_public_payload(row)


@customer_router.post(
    "/lifecycle/open-contract",
    summary="Vertragsprozess oeffnen",
    description="Von aktiver oder abgelaufener Probephase in `contract_pending` (Prompt 11).",
)
def customer_lifecycle_open_contract(
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
            apply_trial_expiry_if_due(conn, tenant_id=tid, actor=auth.actor)
            row = fetch_tenant_lifecycle_row(conn, tenant_id=tid)
            if row is None:
                raise _http_lifecycle_reject("lifecycle_row_missing")
            cur = CustomerLifecycleStatus(str(row["lifecycle_status"]))
            if cur not in (
                CustomerLifecycleStatus.TRIAL_ACTIVE,
                CustomerLifecycleStatus.TRIAL_EXPIRED,
            ):
                raise _http_lifecycle_reject("open_contract_requires_trial_phase")
            try:
                transition_lifecycle(
                    conn,
                    tenant_id=tid,
                    to_status=CustomerLifecycleStatus.CONTRACT_PENDING,
                    actor=auth.actor,
                    actor_role=TransitionActor.USER,
                    reason_code="user_open_contract_flow",
                    meta_json={},
                )
            except ValueError as e:
                raise _http_lifecycle_reject(str(e)) from e
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "LIFECYCLE_MIGRATION_REQUIRED", "message": "607_tenant_customer_lifecycle"},
        ) from None
    except ValueError as e:
        raise _http_lifecycle_reject(str(e)) from e
    record_gateway_audit_line(
        request, auth, "commerce_customer_lifecycle_open_contract", extra={"tenant_id": tid}
    )
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        row = fetch_tenant_lifecycle_row(conn, tenant_id=tid)
    assert row is not None
    return build_lifecycle_public_payload(row)


@customer_router.post(
    "/lifecycle/ack-contract-signed",
    summary="Vertragsunterzeichnung bestaetigen (Legacy-Stub)",
    description=(
        "Uebergang contract_pending -> contract_signed_waiting_admin ohne PDF/E-Sign. "
        "Deaktiviert wenn COMMERCIAL_CONTRACT_ENFORCE_SIGNING_WORKFLOW=true oder "
        "in Production mit gesetztem COMMERCIAL_CONTRACT_WEBHOOK_SECRET."
    ),
)
def customer_lifecycle_ack_contract_signed(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    if settings.commercial_contract_stub_ack_disabled():
        raise HTTPException(
            status_code=409,
            detail={
                "code": "CONTRACT_USE_SIGNING_WORKFLOW",
                "message": (
                    "Vertragsunterzeichnung laeuft ueber E-Sign/Webhook (Prompt 12). "
                    "Stub ack-contract-signed ist deaktiviert."
                ),
            },
        )
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            _require_tenant_commercial_state(conn, tid)
            transition_lifecycle(
                conn,
                tenant_id=tid,
                to_status=CustomerLifecycleStatus.CONTRACT_SIGNED_WAITING_ADMIN,
                actor=auth.actor,
                actor_role=TransitionActor.USER,
                reason_code="user_ack_contract_signed_stub",
                meta_json={},
            )
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "LIFECYCLE_MIGRATION_REQUIRED", "message": "607_tenant_customer_lifecycle"},
        ) from None
    except ValueError as e:
        raise _http_lifecycle_reject(str(e)) from e
    record_gateway_audit_line(
        request,
        auth,
        "commerce_customer_lifecycle_ack_contract_signed",
        extra={"tenant_id": tid},
    )
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        row = fetch_tenant_lifecycle_row(conn, tenant_id=tid)
    assert row is not None
    return build_lifecycle_public_payload(row)


@customer_router.patch(
    "/me",
    summary="Anzeigename aktualisieren",
)
def customer_me_patch(
    request: Request,
    body: CustomerMePatch,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = _resolve_target_tenant(auth, None)
    display = sanitize_display_name(body.display_name)
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        _require_tenant_commercial_state(conn, tid)
        with conn.transaction():
            update_customer_display_name(
                conn, tenant_id=tid, display_name=display, actor=auth.actor
            )
            profile = fetch_customer_profile(conn, tenant_id=tid)
    record_gateway_audit_line(
        request,
        auth,
        "commerce_customer_profile_patch",
        extra={"tenant_id": tid},
    )
    return {"status": "ok", "profile": profile}


@customer_router.get(
    "/integrations",
    summary="Integrations-Snapshot (Telegram, Broker-Hinweise)",
)
def customer_integrations(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    tg_public: dict[str, Any] = {
        "connected": False,
        "verified_ts": None,
        "chat_ref_masked": None,
        "pending_link_expires_at": None,
        "bot_username_configured": bool(settings.telegram_bot_username.strip()),
        "console_telegram_required": settings.commercial_telegram_required_for_console,
        "deep_link_template": None,
    }
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        _require_tenant_commercial_state(conn, tid)
        snap = fetch_integration_snapshot(conn, tenant_id=tid)
        try:
            bind = get_binding_row(conn, tenant_id=tid)
            if bind:
                tg_public["connected"] = True
                vt = bind.get("verified_ts")
                tg_public["verified_ts"] = vt.isoformat() if vt is not None else None
                tg_public["chat_ref_masked"] = mask_chat_id(int(bind["telegram_chat_id"]))
            else:
                row = conn.execute(
                    """
                    SELECT expires_ts FROM app.telegram_link_pending
                    WHERE tenant_id = %s AND consumed_ts IS NULL
                    ORDER BY created_ts DESC
                    LIMIT 1
                    """,
                    (tid,),
                ).fetchone()
                if row and dict(row).get("expires_ts"):
                    exp = dict(row)["expires_ts"]
                    tg_public["pending_link_expires_at"] = (
                        exp.isoformat() if hasattr(exp, "isoformat") else str(exp)
                    )
            u = settings.telegram_bot_username.strip().lstrip("@")
            if u:
                tg_public["deep_link_template"] = f"https://t.me/{u}?start=link_<token>"
        except psycopg.errors.UndefinedTable:
            tg_public["migration_required"] = True
    if snap is None:
        snap = {
            "tenant_id": tid,
            "telegram_state": "unknown",
            "telegram_hint_public": None,
            "broker_state": "unknown",
            "broker_hint_public": None,
            "updated_ts": None,
        }
    record_gateway_audit_line(
        request, auth, "commerce_customer_integrations", extra={"tenant_id": tid}
    )
    return {
        "tenant_id_masked": _mask_tenant_id(tid),
        "integration": snap,
        "telegram_onboarding": tg_public,
        "bitget_env": bitget_env_hints_for_customer_portal(settings),
    }


@customer_router.post(
    "/integrations/telegram/start-link",
    summary="Telegram Deep-Link ausstellen",
    description="Erfordert TELEGRAM_BOT_USERNAME; liefert link_<token> Start-Payload.",
)
def customer_telegram_start_link(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    bot = settings.telegram_bot_username.strip().lstrip("@")
    if not bot:
        raise HTTPException(
            status_code=503,
            detail="TELEGRAM_BOT_USERNAME is not configured",
        )
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            _require_tenant_commercial_state(conn, tid)
            with conn.transaction():
                token, exp = create_pending_link(conn, tenant_id=tid, ttl_hours=24)
    except psycopg.errors.UndefinedTable as e:
        raise HTTPException(
            status_code=503,
            detail="telegram onboarding tables missing (run migrations)",
        ) from e
    payload = f"link_{token}"
    deep_link = f"https://t.me/{bot}?start={payload}"
    record_gateway_audit_line(
        request,
        auth,
        "telegram_start_link_issued",
        extra={"tenant_id": tid},
    )
    return {
        "tenant_id_masked": _mask_tenant_id(tid),
        "expires_at": exp.isoformat(),
        "deep_link": deep_link,
    }


@customer_router.post(
    "/integrations/telegram/test",
    summary="Testnachricht an gebundenen Telegram-Chat",
)
def customer_telegram_test_message(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    aid: str | None = None
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        _require_tenant_commercial_state(conn, tid)
        try:
            linked = is_telegram_connected(conn, tenant_id=tid)
        except psycopg.errors.UndefinedTable as e:
            raise HTTPException(
                status_code=503,
                detail="telegram onboarding tables missing (run migrations)",
            ) from e
        if not linked:
            raise HTTPException(
                status_code=409,
                detail="telegram not linked; complete onboarding first",
            )
        with conn.transaction():
            aid = enqueue_customer_notify(
                conn,
                tenant_id=tid,
                text=(
                    "Testnachricht aus dem Kundenbereich: Die Verbindung zu Ihrem "
                    "Telegram-Chat funktioniert. Sie erhalten hier kuenftig Pflicht-"
                    "Hinweise zu Konto, Guthaben und Risiko."
                ),
                category="telegram_test",
                severity="info",
                dedupe_key=None,
                audit_actor="commerce_customer_ui",
            )
    record_gateway_audit_line(
        request,
        auth,
        "telegram_test_message_enqueued",
        extra={"tenant_id": tid, "alert_id": aid},
    )
    if aid is None:
        raise HTTPException(status_code=409, detail="no telegram chat on file")
    return {"status": "ok", "alert_id": aid}


@customer_router.get(
    "/integrations/telegram/notify-prefs",
    summary="Telegram: Benachrichtigungsarten (Lesen)",
    description="Fehlende DB-Zeile = Server-Defaults; Trial-Kunden gleicher Endpunkt.",
)
def customer_telegram_notify_prefs_get(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        _require_tenant_commercial_state(conn, tid)
        try:
            prefs = fetch_notify_prefs_merged(conn, tenant_id=tid)
        except psycopg.errors.UndefinedTable as e:
            raise HTTPException(
                status_code=503,
                detail="customer telegram notify prefs table missing (run migrations)",
            ) from e
    record_gateway_audit_line(
        request, auth, "commerce_customer_telegram_notify_prefs_read", extra={"tenant_id": tid}
    )
    return {"tenant_id_masked": _mask_tenant_id(tid), "prefs": prefs}


@customer_router.patch(
    "/integrations/telegram/notify-prefs",
    summary="Telegram: Benachrichtigungsarten (Teil-Update)",
)
def customer_telegram_notify_prefs_patch(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
    body: TelegramNotifyPrefsPatch,
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = _resolve_target_tenant(auth, None)
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=400, detail="no fields to update")
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        _require_tenant_commercial_state(conn, tid)
        try:
            before = fetch_notify_prefs_merged(conn, tenant_id=tid)
            with conn.transaction():
                after = upsert_notify_prefs(conn, tenant_id=tid, **patch)
                audit_prefs_changed(
                    conn,
                    tenant_id=tid,
                    actor="commerce_customer_ui",
                    detail={"before": before, "after": after},
                )
        except psycopg.errors.UndefinedTable as e:
            raise HTTPException(
                status_code=503,
                detail="customer telegram notify prefs table missing (run migrations)",
            ) from e
    record_gateway_audit_line(
        request, auth, "commerce_customer_telegram_notify_prefs_patch", extra={"tenant_id": tid}
    )
    return {"tenant_id_masked": _mask_tenant_id(tid), "prefs": after}


@customer_router.get(
    "/balance",
    summary="Guthaben und Verbrauch (Monat UTC)",
)
def customer_balance(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        _require_tenant_commercial_state(conn, tid)
        wallet = fetch_customer_wallet(conn, tenant_id=tid) or {
            "tenant_id": tid,
            "prepaid_balance_list_usd": "0",
            "updated_ts": None,
        }
        month_usd = sum_ledger_usd_month(conn, tenant_id=tid)
        llm_tok = sum_llm_tokens_month(conn, tenant_id=tid)
        prepaid = fetch_prepaid_balance_list_usd(conn, tenant_id=tid)
        try:
            accruals = fetch_billing_accruals_recent(conn, tenant_id=tid, limit=14)
            alerts = fetch_billing_alerts_recent(conn, tenant_id=tid, limit=30)
        except psycopg.errors.UndefinedTable:
            accruals, alerts = [], []
    s = get_gateway_settings()
    billing_status = build_billing_status_public(
        prepaid_balance_list_usd=prepaid,
        daily_fee_usd=Decimal(str(s.billing_daily_api_fee_usd.strip() or "50")),
        min_new_trade_usd=Decimal(str(s.billing_min_balance_new_trade_usd.strip() or "50")),
        warning_below_usd=Decimal(str(s.billing_warning_balance_usd.strip() or "100")),
        critical_below_usd=Decimal(str(s.billing_critical_balance_usd.strip() or "50")),
    )
    record_gateway_audit_line(
        request, auth, "commerce_customer_balance", extra={"tenant_id": tid}
    )
    return {
        "tenant_id_masked": _mask_tenant_id(tid),
        "wallet": wallet,
        "billing": {
            "status": billing_status,
            "daily_accruals_recent": accruals,
            "balance_alerts_recent": alerts,
        },
        "usage_month_utc": {
            "ledger_total_list_usd": str(month_usd),
            "llm_tokens_used": str(llm_tok),
        },
    }


@customer_router.get(
    "/payments",
    summary="Zahlungsereignisse (maskiert)",
)
def customer_payments(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
    limit: int = 50,
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        _require_tenant_commercial_state(conn, tid)
        items = fetch_payment_events(conn, tenant_id=tid, limit=limit)
    record_gateway_audit_line(
        request,
        auth,
        "commerce_customer_payments",
        extra={"tenant_id": tid, "limit": limit},
    )
    return {"tenant_id_masked": _mask_tenant_id(tid), "items": items}


@customer_router.get(
    "/payments/capabilities",
    summary="Zahlungsfaehigkeiten (Sandbox/Live, Methoden)",
    description="Keine Secrets; gleiche Logik wie Dashboard-Einzahlungsseite.",
)
def customer_payments_capabilities(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = _resolve_target_tenant(auth, None)
    record_gateway_audit_line(
        request, auth, "commerce_customer_payments_capabilities", extra={"tenant_id": tid}
    )
    return build_payment_capabilities(settings)


@customer_router.post(
    "/payments/deposit/checkout",
    summary="Einzahlungs-Checkout starten",
    description="Idempotency-Key Header; provider mock|stripe.",
)
def customer_deposit_checkout(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
    body: DepositCheckoutBody,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = _resolve_target_tenant(auth, None)
    key = idempotency_key.strip()
    if len(key) < 8:
        raise HTTPException(status_code=400, detail="Idempotency-Key too short (min 8)")
    amt = Decimal(str(body.amount_list_usd))
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        _require_tenant_commercial_state(conn, tid)
        with conn.transaction():
            out = start_deposit_checkout(
                conn,
                settings,
                tenant_id=tid,
                idempotency_key=key,
                provider=body.provider.strip().lower(),
                amount_list_usd=amt,
                currency=body.currency,
            )
    record_gateway_audit_line(
        request,
        auth,
        "commerce_customer_deposit_checkout",
        extra={"tenant_id": tid, "provider": body.provider.strip().lower()},
    )
    return {"tenant_id_masked": _mask_tenant_id(tid), **out}


@customer_router.post(
    "/payments/deposit/resume",
    summary="Stripe Checkout Session fortsetzen",
)
def customer_deposit_resume(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
    body: DepositResumeBody,
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        _require_tenant_commercial_state(conn, tid)
        row = resume_stripe_checkout(
            conn,
            settings,
            tenant_id=tid,
            idempotency_key=body.idempotency_key.strip(),
        )
    record_gateway_audit_line(
        request, auth, "commerce_customer_deposit_resume", extra={"tenant_id": tid}
    )
    if row is None:
        raise HTTPException(status_code=404, detail="no resumable stripe checkout")
    return {"tenant_id_masked": _mask_tenant_id(tid), **row}


@customer_router.get(
    "/payments/deposit/intents/{intent_id}",
    summary="Deposit-Intent Status",
)
def customer_deposit_intent_get(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
    intent_id: UUID,
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        _require_tenant_commercial_state(conn, tid)
        row = fetch_intent_by_id(conn, intent_id=intent_id, tenant_id=tid)
    if row is None:
        raise HTTPException(status_code=404, detail="intent not found")
    record_gateway_audit_line(
        request,
        auth,
        "commerce_customer_deposit_intent_get",
        extra={"tenant_id": tid, "intent_id": str(intent_id)},
    )
    return {"tenant_id_masked": _mask_tenant_id(tid), "intent": _public_deposit_intent(row)}


@customer_router.get(
    "/history",
    summary="Verbrauchs- und Portal-Audit-Auszug",
)
def customer_history(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
    ledger_limit: int = 40,
    audit_limit: int = 40,
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        _require_tenant_commercial_state(conn, tid)
        ledger = fetch_ledger_customer_safe(conn, tenant_id=tid, limit=ledger_limit)
        audits = fetch_portal_audit_recent(conn, tenant_id=tid, limit=audit_limit)
    record_gateway_audit_line(
        request, auth, "commerce_customer_history", extra={"tenant_id": tid}
    )
    return {
        "tenant_id_masked": _mask_tenant_id(tid),
        "usage_ledger": ledger,
        "portal_audit": audits,
    }


@admin_customer_router.post("/lifecycle/transition")
def admin_lifecycle_transition(
    request: Request,
    body: AdminLifecycleTransitionBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = body.tenant_id.strip()
    try:
        target = CustomerLifecycleStatus(body.to_status.strip())
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_LIFECYCLE_STATUS", "message": str(e)},
        ) from e
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            _require_tenant_commercial_state(conn, tid)
            transition_lifecycle(
                conn,
                tenant_id=tid,
                to_status=target,
                actor=auth.actor,
                actor_role=TransitionActor.ADMIN,
                reason_code=body.reason_code,
                meta_json={"via": "admin_api"},
            )
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "LIFECYCLE_MIGRATION_REQUIRED", "message": "607_tenant_customer_lifecycle"},
        ) from None
    except ValueError as e:
        raise _http_lifecycle_reject(str(e)) from e
    record_gateway_audit_line(
        request,
        auth,
        "commerce_admin_lifecycle_transition",
        extra={"tenant_id": tid, "to_status": target.value},
    )
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        row = fetch_tenant_lifecycle_row(conn, tenant_id=tid)
    assert row is not None
    return {"status": "ok", "lifecycle": build_lifecycle_public_payload(row)}


@admin_customer_router.post("/lifecycle/set-email-verified")
def admin_lifecycle_set_email_verified(
    request: Request,
    body: AdminLifecycleEmailBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = body.tenant_id.strip()
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            _require_tenant_commercial_state(conn, tid)
            set_email_verified(
                conn,
                tenant_id=tid,
                actor=auth.actor,
                verified=body.email_verified,
            )
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "LIFECYCLE_MIGRATION_REQUIRED", "message": "607_tenant_customer_lifecycle"},
        ) from None
    except ValueError as e:
        raise _http_lifecycle_reject(str(e)) from e
    record_gateway_audit_line(
        request,
        auth,
        "commerce_admin_lifecycle_email_verified",
        extra={"tenant_id": tid, "verified": body.email_verified},
    )
    return {"status": "ok", "tenant_id_masked": _mask_tenant_id(tid)}


@admin_customer_router.post("/payment")
def admin_record_payment(
    request: Request,
    body: AdminPaymentBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = body.tenant_id.strip()
    amt = Decimal(str(body.amount_list_usd))
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        _require_tenant_commercial_state(conn, tid)
        with conn.transaction():
            pid = insert_payment_event(
                conn,
                tenant_id=tid,
                amount_list_usd=amt,
                currency=body.currency,
                status=body.status,
                provider=body.provider,
                provider_reference_masked=body.provider_reference_masked,
                notes_public=body.notes_public,
                actor=auth.actor,
            )
    record_gateway_audit_line(
        request,
        auth,
        "commerce_admin_payment_recorded",
        extra={"tenant_id": tid, "payment_id": str(pid)},
    )
    return {"status": "ok", "payment_id": str(pid)}


@admin_customer_router.post("/wallet/adjust")
def admin_wallet_adjust(
    request: Request,
    body: AdminWalletAdjustBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = body.tenant_id.strip()
    delta = Decimal(str(body.delta_list_usd))
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        _require_tenant_commercial_state(conn, tid)
        with conn.transaction():
            new_bal = adjust_wallet_balance(
                conn,
                tenant_id=tid,
                delta_list_usd=delta,
                actor=auth.actor,
                reason_code=body.reason_code,
            )
    record_gateway_audit_line(
        request,
        auth,
        "commerce_admin_wallet_adjusted",
        extra={"tenant_id": tid},
    )
    return {"status": "ok", "prepaid_balance_list_usd": new_bal}


@admin_customer_router.patch("/integrations")
def admin_integrations_patch(
    request: Request,
    body: AdminIntegrationBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = body.tenant_id.strip()
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        _require_tenant_commercial_state(conn, tid)
        with conn.transaction():
            upsert_integration_snapshot(
                conn,
                tenant_id=tid,
                telegram_state=body.telegram_state,
                telegram_hint_public=body.telegram_hint_public,
                broker_state=body.broker_state,
                broker_hint_public=body.broker_hint_public,
                actor=auth.actor,
            )
    record_gateway_audit_line(
        request,
        auth,
        "commerce_admin_integrations_patched",
        extra={"tenant_id": tid},
    )
    return {"status": "ok"}


from api_gateway.customer_performance_attach import (  # noqa: E402
    attach_customer_performance_routes,
)

attach_customer_performance_routes(customer_router)
