"""Prompt 12: Vertragsvorlagen, PDF, Mock-E-Sign, Webhook, Admin-Review-Queue."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

import psycopg
import psycopg.errors
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from psycopg.rows import dict_row
from pydantic import BaseModel, Field
from shared_py.customer_lifecycle import CustomerLifecycleStatus

from api_gateway.audit import record_gateway_audit_line
from api_gateway.auth import GatewayAuthContext, require_billing_admin, require_billing_read
from api_gateway.config import get_gateway_settings
from api_gateway.contract_pdf import build_contract_pdf_bytes
from api_gateway.db import get_database_url
from api_gateway.db_contract_workflow import (
    complete_contract_signing,
    fetch_contract_by_id_for_tenant,
    fetch_document_row_for_download,
    fetch_latest_active_template_for_key,
    fetch_open_contract_for_tenant,
    fetch_template,
    insert_contract_document,
    insert_tenant_contract_row,
    list_active_templates,
    list_contracts_for_tenant,
    list_documents_for_contract,
    list_review_queue,
    patch_review_queue_item,
    update_contract_envelope_and_status,
)
from api_gateway.db_tenant_lifecycle import apply_trial_expiry_if_due, fetch_tenant_lifecycle_row
from api_gateway.esign_mock import create_mock_envelope, verify_webhook_signature
from api_gateway.routes_commerce_customer import (
    _ensure_commercial,
    _require_tenant_commercial_state,
    _resolve_target_tenant,
)

contract_customer_router = APIRouter(
    prefix="/v1/commerce/customer/contracts",
    tags=["commerce-customer"],
)
contract_admin_router = APIRouter(
    prefix="/v1/commerce/admin/contracts",
    tags=["commerce-admin-customer"],
)
contract_webhook_router = APIRouter(
    prefix="/v1/commerce/webhooks",
    tags=["commerce-contracts"],
)


def _mask_tenant_id(tid: str) -> str:
    t = tid.strip()
    if len(t) <= 8:
        return f"{t[:2]}…" if len(t) > 2 else t
    return f"{t[:4]}…{t[-4:]}"


def _http_contract(code: str, message: str, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


class StartContractBody(BaseModel):
    template_key: str = Field(min_length=1, max_length=128)
    template_version: int | None = Field(default=None, ge=1)


class ReviewQueuePatchBody(BaseModel):
    queue_status: str | None = Field(default=None, min_length=4, max_length=64)
    admin_notes_internal: str | None = Field(default=None, max_length=4000)
    customer_message_public: str | None = Field(default=None, max_length=4000)


class ContractEsignWebhookBody(BaseModel):
    provider: str
    event: str
    contract_id: str
    tenant_id: str
    envelope_id: str | None = None
    completed_at_unix: int | None = None


@contract_customer_router.get("/templates", summary="Aktive Vertragsvorlagen")
def customer_contract_templates(
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
            rows = list_active_templates(conn)
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "CONTRACT_MIGRATION_REQUIRED", "message": "608_commercial_contract_workflow"},
        ) from None
    record_gateway_audit_line(
        request, auth, "commerce_customer_contract_templates", extra={"tenant_id": tid}
    )
    return {"schema_version": "contract-templates-v1", "templates": rows}


@contract_customer_router.get("", summary="Eigene Vertragsinstanzen")
def customer_contract_list(
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
            items = list_contracts_for_tenant(conn, tenant_id=tid, limit=40)
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "CONTRACT_MIGRATION_REQUIRED", "message": "608_commercial_contract_workflow"},
        ) from None
    record_gateway_audit_line(request, auth, "commerce_customer_contract_list", extra={"tenant_id": tid})
    return {"schema_version": "tenant-contracts-v1", "contracts": items}


@contract_customer_router.post("/start", summary="Neue Vertragsinstanz starten")
def customer_contract_start(
    request: Request,
    body: StartContractBody,
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
            lc = fetch_tenant_lifecycle_row(conn, tenant_id=tid)
            if lc is None:
                raise _http_contract("lifecycle_missing", "Lebenszyklus nicht initialisiert", 409)
            st = CustomerLifecycleStatus(str(lc["lifecycle_status"]))
            if st != CustomerLifecycleStatus.CONTRACT_PENDING:
                raise _http_contract(
                    "lifecycle_not_contract_pending",
                    "Vertrag nur im Status contract_pending startbar",
                    409,
                )
            if fetch_open_contract_for_tenant(conn, tenant_id=tid) is not None:
                raise _http_contract("open_contract_exists", "Bereits eine offene Vertragsinstanz", 409)

            if body.template_version is not None:
                tpl = fetch_template(
                    conn, template_key=body.template_key, version=body.template_version
                )
            else:
                tpl = fetch_latest_active_template_for_key(conn, template_key=body.template_key)
            if tpl is None:
                raise _http_contract("template_not_found", "Vorlage nicht gefunden oder inaktiv", 404)

            with conn.transaction():
                cid = insert_tenant_contract_row(
                    conn,
                    tenant_id=tid,
                    template_key=str(tpl["template_key"]),
                    template_version=int(tpl["version"]),
                    status="awaiting_customer_sign",
                )
                iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                draft_pdf = build_contract_pdf_bytes(
                    title=str(tpl["title_de"]),
                    body_text=str(tpl["body_text"]),
                    tenant_id_masked=_mask_tenant_id(tid),
                    template_key=str(tpl["template_key"]),
                    template_version=int(tpl["version"]),
                    generated_at_iso=iso,
                )
                insert_contract_document(
                    conn,
                    contract_id=cid,
                    tenant_id=tid,
                    document_kind="draft_pdf",
                    pdf_bytes=draft_pdf,
                    meta_json={"kind": "draft", "generated_at_utc": iso},
                )
            row = fetch_contract_by_id_for_tenant(conn, contract_id=cid, tenant_id=tid)
    except psycopg.errors.UniqueViolation as e:
        raise _http_contract("open_contract_exists", "Bereits eine offene Vertragsinstanz", 409) from e
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "CONTRACT_MIGRATION_REQUIRED", "message": "608_commercial_contract_workflow"},
        ) from None

    record_gateway_audit_line(
        request,
        auth,
        "commerce_customer_contract_start",
        extra={"tenant_id": tid, "template_key": body.template_key},
    )
    return {"schema_version": "tenant-contract-started-v1", "contract": row}


@contract_customer_router.get("/{contract_id}", summary="Vertragsinstanz")
def customer_contract_get(
    request: Request,
    contract_id: UUID,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            _require_tenant_commercial_state(conn, tid)
            row = fetch_contract_by_id_for_tenant(conn, contract_id=contract_id, tenant_id=tid)
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "CONTRACT_MIGRATION_REQUIRED", "message": "608_commercial_contract_workflow"},
        ) from None
    if row is None:
        raise HTTPException(status_code=404, detail="contract not found")
    record_gateway_audit_line(
        request, auth, "commerce_customer_contract_get", extra={"tenant_id": tid, "contract_id": str(contract_id)}
    )
    return {"schema_version": "tenant-contract-v1", "contract": row}


@contract_customer_router.get("/{contract_id}/documents", summary="Dokument-Metadaten")
def customer_contract_documents(
    request: Request,
    contract_id: UUID,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            _require_tenant_commercial_state(conn, tid)
            if fetch_contract_by_id_for_tenant(conn, contract_id=contract_id, tenant_id=tid) is None:
                raise HTTPException(status_code=404, detail="contract not found")
            docs = list_documents_for_contract(conn, contract_id=contract_id, tenant_id=tid)
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "CONTRACT_MIGRATION_REQUIRED", "message": "608_commercial_contract_workflow"},
        ) from None
    record_gateway_audit_line(
        request,
        auth,
        "commerce_customer_contract_documents",
        extra={"tenant_id": tid, "contract_id": str(contract_id)},
    )
    return {"schema_version": "tenant-contract-documents-v1", "documents": docs}


@contract_customer_router.get(
    "/{contract_id}/documents/{document_id}/download",
    summary="PDF-Download",
)
def customer_contract_document_download(
    contract_id: UUID,
    document_id: UUID,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> Response:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            _require_tenant_commercial_state(conn, tid)
            if fetch_contract_by_id_for_tenant(conn, contract_id=contract_id, tenant_id=tid) is None:
                raise HTTPException(status_code=404, detail="contract not found")
            row = fetch_document_row_for_download(conn, document_id=document_id, tenant_id=tid)
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "CONTRACT_MIGRATION_REQUIRED", "message": "608_commercial_contract_workflow"},
        ) from None
    if row is None or UUID(str(row["contract_id"])) != contract_id:
        raise HTTPException(status_code=404, detail="document not found")
    pdf: bytes = row["pdf_bytes"]
    kind = str(row["document_kind"])
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{kind}_{document_id}.pdf"',
        },
    )


@contract_customer_router.post("/{contract_id}/signing-session", summary="E-Sign-Session (Mock)")
def customer_contract_signing_session(
    request: Request,
    contract_id: UUID,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    if settings.commercial_contract_esign_provider.strip().lower() != "mock":
        raise _http_contract("esign_provider_unsupported", "Nur mock-Provider implementiert", 501)
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            _require_tenant_commercial_state(conn, tid)
            c = fetch_contract_by_id_for_tenant(conn, contract_id=contract_id, tenant_id=tid)
            if c is None:
                raise HTTPException(status_code=404, detail="contract not found")
            if str(c["status"]) != "awaiting_customer_sign":
                raise _http_contract("contract_not_awaiting_sign", "Keine aktive Signatur-Phase", 409)
            env = create_mock_envelope(contract_id=str(contract_id), tenant_id=tid)
            update_contract_envelope_and_status(
                conn,
                contract_id=contract_id,
                tenant_id=tid,
                status="awaiting_customer_sign",
                provider_envelope_id=env.envelope_id,
                signing_url_hint=env.signing_url,
            )
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "CONTRACT_MIGRATION_REQUIRED", "message": "608_commercial_contract_workflow"},
        ) from None
    record_gateway_audit_line(
        request,
        auth,
        "commerce_customer_contract_signing_session",
        extra={"tenant_id": tid, "contract_id": str(contract_id)},
    )
    return {
        "schema_version": "contract-signing-session-v1",
        "provider": "mock",
        "envelope_id": env.envelope_id,
        "signing_url": env.signing_url,
        "expires_at_unix": env.expires_at_unix,
    }


@contract_customer_router.post(
    "/{contract_id}/mock-complete-sign",
    summary="Mock-Signatur abschliessen (nur Dev)",
)
def customer_contract_mock_complete_sign(
    request: Request,
    contract_id: UUID,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_read)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    if settings.production or not settings.commercial_contract_allow_mock_customer_complete:
        raise HTTPException(status_code=404, detail="not available")
    tid = _resolve_target_tenant(auth, None)
    dsn = get_database_url()
    iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            _require_tenant_commercial_state(conn, tid)
            c = fetch_contract_by_id_for_tenant(conn, contract_id=contract_id, tenant_id=tid)
            if c is None:
                raise HTTPException(status_code=404, detail="contract not found")
            tpl = fetch_template(
                conn,
                template_key=str(c["template_key"]),
                template_version=int(c["template_version"]),
            )
            if tpl is None:
                raise _http_contract("template_not_found", "Vorlage fehlt", 500)
            env_id = str(c.get("provider_envelope_id") or "")
            footer = (
                f"ELECTRONISCH SIGNIERT (Mock-Provider, Dev-Endpunkt). "
                f"Envelope: {env_id or 'n/a'}. Zeit (UTC): {iso}."
            )
            signed_pdf = build_contract_pdf_bytes(
                title=str(tpl["title_de"]),
                body_text=str(tpl["body_text"]),
                tenant_id_masked=_mask_tenant_id(tid),
                template_key=str(tpl["template_key"]),
                template_version=int(tpl["version"]),
                generated_at_iso=iso,
                footer_extra=footer,
            )
            with conn.transaction():
                out = complete_contract_signing(
                    conn,
                    tenant_id=tid,
                    contract_id=contract_id,
                    envelope_id=env_id or None,
                    signed_pdf_bytes=signed_pdf,
                    meta_extra={"source": "mock_customer_endpoint", "provider": "mock"},
                    lifecycle_actor_label=auth.actor,
                    reason_code="mock_customer_complete_sign",
                )
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "CONTRACT_MIGRATION_REQUIRED", "message": "608_commercial_contract_workflow"},
        ) from None
    except ValueError as e:
        raise _http_contract(str(e), str(e), 409) from e
    record_gateway_audit_line(
        request,
        auth,
        "commerce_customer_contract_mock_complete",
        extra={"tenant_id": tid, "contract_id": str(contract_id)},
    )
    return {"schema_version": "contract-sign-complete-v1", **out}


@contract_admin_router.get("/review-queue", summary="Vertragspruefung (Warteschlange)")
def admin_contract_review_queue(
    request: Request,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
    status: str | None = None,
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            items = list_review_queue(conn, status_filter=status, limit=200)
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "CONTRACT_MIGRATION_REQUIRED", "message": "608_commercial_contract_workflow"},
        ) from None
    record_gateway_audit_line(request, auth, "commerce_admin_contract_review_queue", extra={})
    return {"schema_version": "contract-review-queue-v1", "items": items}


@contract_admin_router.patch("/review-queue/{queue_id}", summary="Queue-Eintrag aktualisieren")
def admin_contract_review_queue_patch(
    request: Request,
    queue_id: UUID,
    body: ReviewQueuePatchBody,
    auth: Annotated[GatewayAuthContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    settings = get_gateway_settings()
    _ensure_commercial(settings)
    if body.queue_status is None and body.admin_notes_internal is None and body.customer_message_public is None:
        raise _http_contract("no_fields", "Mindestens ein Feld erforderlich", 422)
    dsn = get_database_url()
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            with conn.transaction():
                row = patch_review_queue_item(
                    conn,
                    queue_id=queue_id,
                    queue_status=body.queue_status,
                    admin_notes_internal=body.admin_notes_internal,
                    customer_message_public=body.customer_message_public,
                )
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "CONTRACT_MIGRATION_REQUIRED", "message": "608_commercial_contract_workflow"},
        ) from None
    if row is None:
        raise HTTPException(status_code=404, detail="queue item not found")
    record_gateway_audit_line(
        request,
        auth,
        "commerce_admin_contract_review_patch",
        extra={"queue_id": str(queue_id)},
    )
    return {"schema_version": "contract-review-queue-item-v1", "item": row}


@contract_webhook_router.post("/contract-esign", summary="E-Sign-Webhook (HMAC)")
async def contract_esign_webhook(request: Request) -> dict[str, Any]:
    settings = get_gateway_settings()
    if not settings.commercial_enabled:
        raise HTTPException(status_code=404, detail="commercial module disabled")
    secret = settings.commercial_contract_webhook_secret.strip()
    if not secret:
        raise HTTPException(status_code=503, detail="webhook secret not configured")
    raw = await request.body()
    sig = (request.headers.get("X-Commercial-Contract-Signature") or "").strip()
    if not verify_webhook_signature(secret, raw, sig):
        raise HTTPException(status_code=401, detail="invalid signature")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="invalid json")
    try:
        body = ContractEsignWebhookBody.model_validate(payload)
    except Exception:
        raise HTTPException(status_code=422, detail="invalid body")
    if body.event != "completed":
        return {"ok": True, "ignored": True, "event": body.event}
    try:
        cid = UUID(body.contract_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid contract_id")
    dsn = get_database_url()
    iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=10) as conn:
            c = fetch_contract_by_id_for_tenant(conn, contract_id=cid, tenant_id=body.tenant_id)
            if c is None:
                raise HTTPException(status_code=404, detail="contract not found")
            tpl = fetch_template(
                conn,
                template_key=str(c["template_key"]),
                template_version=int(c["template_version"]),
            )
            if tpl is None:
                raise HTTPException(status_code=500, detail="template missing")
            env_id = body.envelope_id or str(c.get("provider_envelope_id") or "")
            footer = (
                f"ELECTRONISCH SIGNIERT (Webhook/Mock-Provider). "
                f"Envelope: {env_id or 'n/a'}. "
                f"Provider-Event-Zeit (Unix): {body.completed_at_unix or 'n/a'}."
            )
            signed_pdf = build_contract_pdf_bytes(
                title=str(tpl["title_de"]),
                body_text=str(tpl["body_text"]),
                tenant_id_masked=_mask_tenant_id(body.tenant_id),
                template_key=str(tpl["template_key"]),
                template_version=int(tpl["version"]),
                generated_at_iso=iso,
                footer_extra=footer,
            )
            with conn.transaction():
                out = complete_contract_signing(
                    conn,
                    tenant_id=body.tenant_id,
                    contract_id=cid,
                    envelope_id=body.envelope_id,
                    signed_pdf_bytes=signed_pdf,
                    meta_extra={
                        "source": "webhook",
                        "provider": body.provider,
                        "event": body.event,
                        "completed_at_unix": body.completed_at_unix,
                    },
                    lifecycle_actor_label="contract_esign_webhook",
                    reason_code="esign_webhook_completed",
                )
    except psycopg.errors.UndefinedTable:
        raise HTTPException(
            status_code=503,
            detail={"code": "CONTRACT_MIGRATION_REQUIRED", "message": "608_commercial_contract_workflow"},
        ) from None
    except ValueError as e:
        if str(e) == "contract_not_found":
            raise HTTPException(status_code=404, detail="contract not found") from e
        if str(e) == "envelope_mismatch":
            raise HTTPException(status_code=409, detail="envelope mismatch") from e
        if str(e) == "contract_not_awaiting_sign":
            return {"ok": True, "duplicate_or_stale": True, "detail": str(e)}
        raise HTTPException(status_code=409, detail=str(e)) from e
    return {"ok": True, **out}
