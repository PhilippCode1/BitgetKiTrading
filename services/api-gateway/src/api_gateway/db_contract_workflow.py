"""Postgres: Prompt-12-Vertragsworkflow (Vorlagen, Instanzen, PDF-Revisionen, Review-Queue)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Json
from shared_py.customer_lifecycle import CustomerLifecycleStatus, TransitionActor
from shared_py.commercial_contract_workflow import (
    ContractDocumentKind,
    ContractReviewQueueStatus,
    TenantContractStatus,
)

from api_gateway.db_tenant_lifecycle import transition_lifecycle


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def list_active_templates(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT template_key, version, title_de, content_sha256_hex, effective_from, is_active, created_ts
        FROM app.contract_template
        WHERE is_active = true
        ORDER BY template_key, version DESC
        """
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        if d.get("created_ts") is not None:
            d["created_ts"] = d["created_ts"].isoformat()
        if d.get("effective_from") is not None:
            d["effective_from"] = str(d["effective_from"])
        out.append(d)
    return out


def fetch_template(
    conn: psycopg.Connection[Any], *, template_key: str, version: int
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT template_key, version, title_de, body_text, content_sha256_hex, is_active
        FROM app.contract_template
        WHERE template_key = %s AND version = %s AND is_active = true
        """,
        (template_key, version),
    ).fetchone()
    return dict(row) if row else None


def fetch_latest_active_template_for_key(
    conn: psycopg.Connection[Any], *, template_key: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT template_key, version, title_de, body_text, content_sha256_hex, is_active
        FROM app.contract_template
        WHERE template_key = %s AND is_active = true
        ORDER BY version DESC
        LIMIT 1
        """,
        (template_key,),
    ).fetchone()
    return dict(row) if row else None


def fetch_open_contract_for_tenant(
    conn: psycopg.Connection[Any], *, tenant_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT contract_id, tenant_id, template_key, template_version, status,
               provider_name, provider_envelope_id, signing_url_hint, created_ts, updated_ts
        FROM app.tenant_contract
        WHERE tenant_id = %s
          AND status IN (
              'awaiting_customer_sign',
              'awaiting_provider_sign',
              'signed_awaiting_admin'
          )
        ORDER BY updated_ts DESC
        LIMIT 1
        """,
        (tenant_id,),
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["contract_id"] = str(d["contract_id"])
    for k in ("created_ts", "updated_ts"):
        if d.get(k) is not None:
            d[k] = d[k].isoformat()
    return d


def fetch_contract_by_id_for_tenant(
    conn: psycopg.Connection[Any], *, contract_id: UUID, tenant_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT contract_id, tenant_id, template_key, template_version, status,
               provider_name, provider_envelope_id, signing_url_hint, created_ts, updated_ts
        FROM app.tenant_contract
        WHERE contract_id = %s AND tenant_id = %s
        """,
        (contract_id, tenant_id),
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["contract_id"] = str(d["contract_id"])
    for k in ("created_ts", "updated_ts"):
        if d.get(k) is not None:
            d[k] = d[k].isoformat()
    return d


def list_contracts_for_tenant(
    conn: psycopg.Connection[Any], *, tenant_id: str, limit: int = 20
) -> list[dict[str, Any]]:
    lim = max(1, min(limit, 100))
    rows = conn.execute(
        """
        SELECT c.contract_id, c.tenant_id, c.template_key, c.template_version, c.status,
               c.provider_name, c.created_ts, c.updated_ts,
               q.queue_status AS review_queue_status,
               q.customer_message_public AS review_customer_message_public
        FROM app.tenant_contract c
        LEFT JOIN LATERAL (
            SELECT queue_status, customer_message_public
            FROM app.contract_review_queue
            WHERE contract_id = c.contract_id
            ORDER BY updated_ts DESC
            LIMIT 1
        ) q ON true
        WHERE c.tenant_id = %s
        ORDER BY c.updated_ts DESC
        LIMIT %s
        """,
        (tenant_id, lim),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["contract_id"] = str(d["contract_id"])
        for k in ("created_ts", "updated_ts"):
            if d.get(k) is not None:
                d[k] = d[k].isoformat()
        out.append(d)
    return out


def insert_tenant_contract_row(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    template_key: str,
    template_version: int,
    status: str,
    provider_name: str = "mock",
    provider_envelope_id: str | None = None,
    signing_url_hint: str | None = None,
) -> UUID:
    row = conn.execute(
        """
        INSERT INTO app.tenant_contract (
            tenant_id, template_key, template_version, status,
            provider_name, provider_envelope_id, signing_url_hint
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING contract_id
        """,
        (
            tenant_id,
            template_key,
            template_version,
            status,
            provider_name,
            provider_envelope_id,
            signing_url_hint,
        ),
    ).fetchone()
    if row is None:
        raise RuntimeError("insert_tenant_contract_row failed")
    return UUID(str(dict(row)["contract_id"]))


def update_contract_envelope_and_status(
    conn: psycopg.Connection[Any],
    *,
    contract_id: UUID,
    tenant_id: str,
    status: str,
    provider_envelope_id: str | None = None,
    signing_url_hint: str | None = None,
) -> bool:
    cur = conn.execute(
        """
        UPDATE app.tenant_contract
        SET status = %s,
            provider_envelope_id = COALESCE(%s, provider_envelope_id),
            signing_url_hint = COALESCE(%s, signing_url_hint),
            updated_ts = now()
        WHERE contract_id = %s AND tenant_id = %s
        """,
        (status, provider_envelope_id, signing_url_hint, contract_id, tenant_id),
    )
    return cur.rowcount > 0


def update_contract_status_only(
    conn: psycopg.Connection[Any],
    *,
    contract_id: UUID,
    tenant_id: str,
    status: str,
) -> bool:
    cur = conn.execute(
        """
        UPDATE app.tenant_contract
        SET status = %s, updated_ts = now()
        WHERE contract_id = %s AND tenant_id = %s
        """,
        (status, contract_id, tenant_id),
    )
    return cur.rowcount > 0


def insert_contract_document(
    conn: psycopg.Connection[Any],
    *,
    contract_id: UUID,
    tenant_id: str,
    document_kind: str,
    pdf_bytes: bytes,
    meta_json: dict[str, Any],
) -> UUID | None:
    h = sha256_bytes(pdf_bytes)
    sz = len(pdf_bytes)
    row = conn.execute(
        """
        INSERT INTO app.tenant_contract_document (
            contract_id, tenant_id, document_kind, sha256_hex, byte_size, pdf_bytes, meta_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (sha256_hex) DO NOTHING
        RETURNING document_id
        """,
        (contract_id, tenant_id, document_kind, h, sz, pdf_bytes, Json(meta_json)),
    ).fetchone()
    if row is None:
        ex = conn.execute(
            """
            SELECT document_id FROM app.tenant_contract_document
            WHERE sha256_hex = %s AND contract_id = %s AND tenant_id = %s
            """,
            (h, contract_id, tenant_id),
        ).fetchone()
        if ex is None:
            raise RuntimeError("insert_contract_document conflict without row")
        return UUID(str(dict(ex)["document_id"]))
    return UUID(str(dict(row)["document_id"]))


def list_documents_for_contract(
    conn: psycopg.Connection[Any], *, contract_id: UUID, tenant_id: str
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT document_id, document_kind, sha256_hex, byte_size, meta_json, created_ts
        FROM app.tenant_contract_document
        WHERE contract_id = %s AND tenant_id = %s
        ORDER BY created_ts ASC
        """,
        (contract_id, tenant_id),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["document_id"] = str(d["document_id"])
        if d.get("created_ts") is not None:
            d["created_ts"] = d["created_ts"].isoformat()
        out.append(d)
    return out


def fetch_document_row_for_download(
    conn: psycopg.Connection[Any], *, document_id: UUID, tenant_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT document_id, contract_id, document_kind, sha256_hex, byte_size, pdf_bytes, created_ts
        FROM app.tenant_contract_document
        WHERE document_id = %s AND tenant_id = %s
        """,
        (document_id, tenant_id),
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def has_pending_review_for_contract(
    conn: psycopg.Connection[Any], *, contract_id: UUID
) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM app.contract_review_queue
        WHERE contract_id = %s AND queue_status = 'pending_review'
        LIMIT 1
        """,
        (contract_id,),
    ).fetchone()
    return row is not None


def insert_review_queue_item(
    conn: psycopg.Connection[Any],
    *,
    contract_id: UUID,
    tenant_id: str,
    queue_status: str = ContractReviewQueueStatus.PENDING_REVIEW.value,
) -> UUID:
    row = conn.execute(
        """
        INSERT INTO app.contract_review_queue (contract_id, tenant_id, queue_status)
        VALUES (%s, %s, %s)
        RETURNING queue_id
        """,
        (contract_id, tenant_id, queue_status),
    ).fetchone()
    if row is None:
        raise RuntimeError("insert_review_queue_item failed")
    return UUID(str(dict(row)["queue_id"]))


def list_review_queue(
    conn: psycopg.Connection[Any],
    *,
    status_filter: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    lim = max(1, min(limit, 500))
    if status_filter:
        rows = conn.execute(
            """
            SELECT q.queue_id, q.contract_id, q.tenant_id, q.queue_status,
                   q.admin_notes_internal, q.customer_message_public, q.created_ts, q.updated_ts,
                   c.template_key, c.template_version, c.status AS contract_status
            FROM app.contract_review_queue q
            INNER JOIN app.tenant_contract c ON c.contract_id = q.contract_id
            WHERE q.queue_status = %s
            ORDER BY q.created_ts ASC
            LIMIT %s
            """,
            (status_filter, lim),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT q.queue_id, q.contract_id, q.tenant_id, q.queue_status,
                   q.admin_notes_internal, q.customer_message_public, q.created_ts, q.updated_ts,
                   c.template_key, c.template_version, c.status AS contract_status
            FROM app.contract_review_queue q
            INNER JOIN app.tenant_contract c ON c.contract_id = q.contract_id
            WHERE q.queue_status IN ('pending_review', 'needs_customer_info')
            ORDER BY q.created_ts ASC
            LIMIT %s
            """,
            (lim,),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["queue_id"] = str(d["queue_id"])
        d["contract_id"] = str(d["contract_id"])
        for k in ("created_ts", "updated_ts"):
            if d.get(k) is not None:
                d[k] = d[k].isoformat()
        out.append(d)
    return out


def fetch_queue_item_admin(
    conn: psycopg.Connection[Any], *, queue_id: UUID
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT queue_id, contract_id, tenant_id, queue_status,
               admin_notes_internal, customer_message_public, created_ts, updated_ts
        FROM app.contract_review_queue
        WHERE queue_id = %s
        """,
        (queue_id,),
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["queue_id"] = str(d["queue_id"])
    d["contract_id"] = str(d["contract_id"])
    for k in ("created_ts", "updated_ts"):
        if d.get(k) is not None:
            d[k] = d[k].isoformat()
    return d


def patch_review_queue_item(
    conn: psycopg.Connection[Any],
    *,
    queue_id: UUID,
    queue_status: str | None = None,
    admin_notes_internal: str | None = None,
    customer_message_public: str | None = None,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT queue_id, contract_id, tenant_id, queue_status
        FROM app.contract_review_queue
        WHERE queue_id = %s
        FOR UPDATE
        """,
        (queue_id,),
    ).fetchone()
    if row is None:
        return None
    cur = dict(row)
    cid: UUID = cur["contract_id"]
    tid: str = str(cur["tenant_id"])
    new_status = queue_status if queue_status is not None else str(cur["queue_status"])

    conn.execute(
        """
        UPDATE app.contract_review_queue
        SET queue_status = %s,
            admin_notes_internal = COALESCE(%s, admin_notes_internal),
            customer_message_public = COALESCE(%s, customer_message_public),
            updated_ts = now()
        WHERE queue_id = %s
        """,
        (
            new_status,
            admin_notes_internal,
            customer_message_public,
            queue_id,
        ),
    )

    if new_status == ContractReviewQueueStatus.APPROVED_CONTRACT.value:
        conn.execute(
            """
            UPDATE app.tenant_contract
            SET status = %s, updated_ts = now()
            WHERE contract_id = %s AND tenant_id = %s
            """,
            (TenantContractStatus.ADMIN_REVIEW_COMPLETE.value, cid, tid),
        )

    return fetch_queue_item_admin(conn, queue_id=queue_id)


def complete_contract_signing(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    contract_id: UUID,
    envelope_id: str | None,
    signed_pdf_bytes: bytes,
    meta_extra: dict[str, Any],
    lifecycle_actor_label: str,
    reason_code: str,
) -> dict[str, Any]:
    """
    Idempotent: bereits signed_awaiting_admin -> ok ohne doppelte Lifecycle-Aenderung.
    """
    row = conn.execute(
        """
        SELECT contract_id, tenant_id, status, provider_envelope_id, template_key, template_version
        FROM app.tenant_contract
        WHERE contract_id = %s AND tenant_id = %s
        FOR UPDATE
        """,
        (contract_id, tenant_id),
    ).fetchone()
    if row is None:
        raise ValueError("contract_not_found")
    cur = dict(row)
    st = str(cur["status"])
    if envelope_id and cur.get("provider_envelope_id"):
        if str(cur["provider_envelope_id"]) != envelope_id:
            raise ValueError("envelope_mismatch")

    if st == TenantContractStatus.SIGNED_AWAITING_ADMIN.value:
        return {"status": "already_completed", "contract_id": str(contract_id)}

    if st != TenantContractStatus.AWAITING_CUSTOMER_SIGN.value:
        raise ValueError("contract_not_awaiting_sign")

    meta = {
        "generated_at_utc": _utc_iso(),
        **meta_extra,
    }
    insert_contract_document(
        conn,
        contract_id=contract_id,
        tenant_id=tenant_id,
        document_kind=ContractDocumentKind.SIGNED_PDF.value,
        pdf_bytes=signed_pdf_bytes,
        meta_json=meta,
    )

    conn.execute(
        """
        UPDATE app.tenant_contract
        SET status = %s, updated_ts = now()
        WHERE contract_id = %s AND tenant_id = %s
        """,
        (TenantContractStatus.SIGNED_AWAITING_ADMIN.value, contract_id, tenant_id),
    )

    if not has_pending_review_for_contract(conn, contract_id=contract_id):
        insert_review_queue_item(conn, contract_id=contract_id, tenant_id=tenant_id)

    lc = conn.execute(
        """
        SELECT lifecycle_status FROM app.tenant_customer_lifecycle
        WHERE tenant_id = %s
        """,
        (tenant_id,),
    ).fetchone()
    if lc is not None and str(dict(lc)["lifecycle_status"]) == CustomerLifecycleStatus.CONTRACT_PENDING.value:
        transition_lifecycle(
            conn,
            tenant_id=tenant_id,
            to_status=CustomerLifecycleStatus.CONTRACT_SIGNED_WAITING_ADMIN,
            actor=lifecycle_actor_label,
            actor_role=TransitionActor.SYSTEM,
            reason_code=reason_code,
            meta_json={"contract_id": str(contract_id)},
        )

    return {"status": "completed", "contract_id": str(contract_id)}
