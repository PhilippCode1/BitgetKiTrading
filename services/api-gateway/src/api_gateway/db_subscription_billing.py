"""Postgres: Prompt-13-Abo, Rechnungen, Finanz-Ledger (append-only)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Json
from shared_py.subscription_billing_pricing import validate_invoice_lines_match_totals

from api_gateway.subscription_billing_amounts import plan_row_to_line_amounts


def _next_invoice_number(conn: psycopg.Connection[Any]) -> str:
    row = conn.execute(
        "SELECT 'INV-' || lpad(nextval('app.billing_invoice_number_seq')::text, 9, '0') AS n"
    ).fetchone()
    if row is None:
        raise RuntimeError("next_invoice_number failed")
    return str(dict(row)["n"])


def insert_ledger_event(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    event_type: str,
    currency: str = "EUR",
    amount_gross_cents: int | None = None,
    invoice_id: UUID | None = None,
    actor: str | None = None,
    meta_json: dict[str, Any] | None = None,
) -> UUID:
    meta_json = meta_json or {}
    row = conn.execute(
        """
        INSERT INTO app.billing_financial_ledger (
            tenant_id, event_type, currency, amount_gross_cents, invoice_id, actor, meta_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
        RETURNING ledger_entry_id
        """,
        (
            tenant_id,
            event_type,
            currency,
            amount_gross_cents,
            invoice_id,
            actor[:500] if actor else None,
            Json(meta_json),
        ),
    ).fetchone()
    if row is None:
        raise RuntimeError("insert_ledger_event failed")
    return UUID(str(dict(row)["ledger_entry_id"]))


def list_active_plans(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT plan_code, billing_interval, display_name_de, net_amount_cents, currency,
               vat_rate_bps, reference_period_days, is_active, created_ts
        FROM app.billing_subscription_plan
        WHERE is_active = true
        ORDER BY reference_period_days ASC
        """
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        if d.get("created_ts") is not None:
            d["created_ts"] = d["created_ts"].isoformat()
        out.append(d)
    return out


def fetch_plan(conn: psycopg.Connection[Any], *, plan_code: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT plan_code, billing_interval, display_name_de, net_amount_cents, currency,
               vat_rate_bps, reference_period_days, is_active
        FROM app.billing_subscription_plan
        WHERE plan_code = %s AND is_active = true
        """,
        (plan_code,),
    ).fetchone()
    return dict(row) if row else None


def fetch_tenant_subscription(
    conn: psycopg.Connection[Any], *, tenant_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT s.tenant_id, s.plan_code, s.status, s.dunning_stage,
               s.current_period_start, s.current_period_end, s.cancel_at_period_end,
               s.meta_json, s.updated_ts,
               p.billing_interval, p.display_name_de, p.net_amount_cents, p.currency, p.vat_rate_bps
        FROM app.tenant_subscription s
        INNER JOIN app.billing_subscription_plan p ON p.plan_code = s.plan_code
        WHERE s.tenant_id = %s
        """,
        (tenant_id,),
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    ut = d.get("updated_ts")
    d["updated_ts"] = ut.isoformat() if ut is not None else None
    for dk in ("current_period_start", "current_period_end"):
        if d.get(dk) is not None:
            d[dk] = str(d[dk])
    return d


def list_invoices_for_tenant(
    conn: psycopg.Connection[Any], *, tenant_id: str, limit: int = 40
) -> list[dict[str, Any]]:
    lim = max(1, min(limit, 200))
    rows = conn.execute(
        """
        SELECT invoice_id, invoice_number, invoice_kind, credits_invoice_id, status, currency,
               total_net_cents, total_vat_cents, total_gross_cents,
               issued_ts, due_ts, paid_ts, created_ts
        FROM app.billing_invoice
        WHERE tenant_id = %s
        ORDER BY created_ts DESC
        LIMIT %s
        """,
        (tenant_id, lim),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["invoice_id"] = str(d["invoice_id"])
        if d.get("credits_invoice_id") is not None:
            d["credits_invoice_id"] = str(d["credits_invoice_id"])
        for tk in ("issued_ts", "due_ts", "paid_ts", "created_ts"):
            if d.get(tk) is not None:
                d[tk] = d[tk].isoformat()
        out.append(d)
    return out


def list_ledger_for_tenant(
    conn: psycopg.Connection[Any], *, tenant_id: str, limit: int = 60
) -> list[dict[str, Any]]:
    lim = max(1, min(limit, 300))
    rows = conn.execute(
        """
        SELECT ledger_entry_id, event_type, currency, amount_gross_cents, invoice_id,
               actor, meta_json, created_ts
        FROM app.billing_financial_ledger
        WHERE tenant_id = %s
        ORDER BY created_ts DESC
        LIMIT %s
        """,
        (tenant_id, lim),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["ledger_entry_id"] = str(d["ledger_entry_id"])
        if d.get("invoice_id") is not None:
            d["invoice_id"] = str(d["invoice_id"])
        ct = d.get("created_ts")
        d["created_ts"] = ct.isoformat() if ct is not None else None
        out.append(d)
    return out


def fetch_invoice_header(
    conn: psycopg.Connection[Any], *, invoice_id: UUID, tenant_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT invoice_id, tenant_id, invoice_number, invoice_kind, credits_invoice_id, status,
               currency, total_net_cents, total_vat_cents, total_gross_cents,
               issued_ts, due_ts, paid_ts, meta_json, created_ts
        FROM app.billing_invoice
        WHERE invoice_id = %s AND tenant_id = %s
        """,
        (invoice_id, tenant_id),
    ).fetchone()
    return dict(row) if row else None


def fetch_invoice_lines(
    conn: psycopg.Connection[Any], *, invoice_id: UUID
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT line_id, line_idx, line_type, description, net_cents, vat_cents, gross_cents,
               meta_json, created_ts
        FROM app.billing_invoice_line
        WHERE invoice_id = %s
        ORDER BY line_idx ASC
        """,
        (invoice_id,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["line_id"] = str(d["line_id"])
        ct = d.get("created_ts")
        d["created_ts"] = ct.isoformat() if ct is not None else None
        out.append(d)
    return out


def list_all_subscriptions_admin(
    conn: psycopg.Connection[Any], *, limit: int = 100
) -> list[dict[str, Any]]:
    lim = max(1, min(limit, 500))
    rows = conn.execute(
        """
        SELECT s.tenant_id, s.plan_code, s.status, s.dunning_stage, s.updated_ts,
               p.display_name_de, p.net_amount_cents, p.billing_interval
        FROM app.tenant_subscription s
        INNER JOIN app.billing_subscription_plan p ON p.plan_code = s.plan_code
        ORDER BY s.updated_ts DESC
        LIMIT %s
        """,
        (lim,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        ut = d.get("updated_ts")
        d["updated_ts"] = ut.isoformat() if ut is not None else None
        out.append(d)
    return out


def issue_subscription_invoice(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    plan_code: str,
    actor: str,
    period_label: str | None = None,
) -> dict[str, Any]:
    plan = fetch_plan(conn, plan_code=plan_code)
    if plan is None:
        raise ValueError("plan_not_found")
    line = plan_row_to_line_amounts(plan, period_label=period_label)
    lines = [line]
    total_net = line["net_cents"]
    total_vat = line["vat_cents"]
    total_gross = line["gross_cents"]
    validate_invoice_lines_match_totals(
        lines,
        total_net_cents=total_net,
        total_vat_cents=total_vat,
        total_gross_cents=total_gross,
    )
    inv_no = _next_invoice_number(conn)
    today = date.today()
    due = today + timedelta(days=14)
    row = conn.execute(
        """
        INSERT INTO app.billing_invoice (
            tenant_id, invoice_number, invoice_kind, status, currency,
            total_net_cents, total_vat_cents, total_gross_cents,
            issued_ts, due_ts, meta_json
        )
        VALUES (%s, %s, 'standard', 'issued', %s, %s, %s, %s, now(), %s, %s::jsonb)
        RETURNING invoice_id
        """,
        (
            tenant_id,
            inv_no,
            plan["currency"],
            total_net,
            total_vat,
            total_gross,
            due,
            Json({"plan_code": plan_code, "issued_by": actor}),
        ),
    ).fetchone()
    if row is None:
        raise RuntimeError("insert invoice failed")
    iid = UUID(str(dict(row)["invoice_id"]))
    conn.execute(
        """
        INSERT INTO app.billing_invoice_line (
            invoice_id, line_idx, line_type, description, net_cents, vat_cents, gross_cents, meta_json
        )
        VALUES (%s, 0, 'subscription', %s, %s, %s, %s, %s::jsonb)
        """,
        (
            iid,
            line["description"],
            line["net_cents"],
            line["vat_cents"],
            line["gross_cents"],
            Json({"plan_code": plan_code}),
        ),
    )
    insert_ledger_event(
        conn,
        tenant_id=tenant_id,
        event_type="invoice_issued",
        currency=str(plan["currency"]),
        amount_gross_cents=total_gross,
        invoice_id=iid,
        actor=actor,
        meta_json={"invoice_number": inv_no, "plan_code": plan_code},
    )
    return {"invoice_id": str(iid), "invoice_number": inv_no}


def issue_full_credit_note(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    credits_invoice_id: UUID,
    actor: str,
) -> dict[str, Any]:
    orig = conn.execute(
        """
        SELECT invoice_id, tenant_id, invoice_number, invoice_kind, status, currency,
               total_net_cents, total_vat_cents, total_gross_cents
        FROM app.billing_invoice
        WHERE invoice_id = %s AND tenant_id = %s
        FOR UPDATE
        """,
        (credits_invoice_id, tenant_id),
    ).fetchone()
    if orig is None:
        raise ValueError("credited_invoice_not_found")
    o = dict(orig)
    if str(o["invoice_kind"]) != "standard":
        raise ValueError("can_only_credit_standard_invoice")
    if str(o["status"]) not in ("issued", "paid", "partially_paid"):
        raise ValueError("invoice_not_creditable_status")
    lines = fetch_invoice_lines(conn, invoice_id=credits_invoice_id)
    if not lines:
        raise ValueError("invoice_has_no_lines")
    neg_lines: list[dict[str, Any]] = []
    for i, L in enumerate(lines):
        neg_lines.append(
            {
                "line_idx": i,
                "line_type": "credit",
                "description": f"Gutschrift zu {o['invoice_number']}: {L['description']}",
                "net_cents": -int(L["net_cents"]),
                "vat_cents": -int(L["vat_cents"]),
                "gross_cents": -int(L["gross_cents"]),
                "meta_json": {"credited_line_idx": L["line_idx"]},
            }
        )
    total_net = sum(int(x["net_cents"]) for x in neg_lines)
    total_vat = sum(int(x["vat_cents"]) for x in neg_lines)
    total_gross = sum(int(x["gross_cents"]) for x in neg_lines)
    validate_invoice_lines_match_totals(
        neg_lines,
        total_net_cents=total_net,
        total_vat_cents=total_vat,
        total_gross_cents=total_gross,
    )
    inv_no = _next_invoice_number(conn)
    row = conn.execute(
        """
        INSERT INTO app.billing_invoice (
            tenant_id, invoice_number, invoice_kind, credits_invoice_id, status, currency,
            total_net_cents, total_vat_cents, total_gross_cents,
            issued_ts, due_ts, meta_json
        )
        VALUES (%s, %s, 'credit', %s, 'issued', %s, %s, %s, %s, now(), NULL, %s::jsonb)
        RETURNING invoice_id
        """,
        (
            tenant_id,
            inv_no,
            credits_invoice_id,
            o["currency"],
            total_net,
            total_vat,
            total_gross,
            Json({"credited_invoice_number": o["invoice_number"], "issued_by": actor}),
        ),
    ).fetchone()
    if row is None:
        raise RuntimeError("insert credit invoice failed")
    new_id = UUID(str(dict(row)["invoice_id"]))
    for L in neg_lines:
        conn.execute(
            """
            INSERT INTO app.billing_invoice_line (
                invoice_id, line_idx, line_type, description, net_cents, vat_cents, gross_cents, meta_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                new_id,
                L["line_idx"],
                L["line_type"],
                L["description"],
                L["net_cents"],
                L["vat_cents"],
                L["gross_cents"],
                Json(L["meta_json"]),
            ),
        )
    insert_ledger_event(
        conn,
        tenant_id=tenant_id,
        event_type="credit_issued",
        currency=str(o["currency"]),
        amount_gross_cents=total_gross,
        invoice_id=new_id,
        actor=actor,
        meta_json={
            "invoice_number": inv_no,
            "credits_invoice_id": str(credits_invoice_id),
            "credited_invoice_number": o["invoice_number"],
        },
    )
    return {"invoice_id": str(new_id), "invoice_number": inv_no}


def update_dunning_stage(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    dunning_stage: str,
    actor: str,
) -> None:
    cur = conn.execute(
        """
        UPDATE app.tenant_subscription
        SET dunning_stage = %s, updated_ts = now()
        WHERE tenant_id = %s
        RETURNING dunning_stage
        """,
        (dunning_stage, tenant_id),
    ).fetchone()
    if cur is None:
        raise ValueError("tenant_subscription_not_found")
    insert_ledger_event(
        conn,
        tenant_id=tenant_id,
        event_type="dunning_updated",
        amount_gross_cents=None,
        invoice_id=None,
        actor=actor,
        meta_json={"dunning_stage": dunning_stage},
    )


def assign_subscription_plan(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    plan_code: str,
    actor: str,
) -> None:
    if fetch_plan(conn, plan_code=plan_code) is None:
        raise ValueError("plan_not_found")
    row = conn.execute(
        "SELECT plan_code FROM app.tenant_subscription WHERE tenant_id = %s FOR UPDATE",
        (tenant_id,),
    ).fetchone()
    prev = dict(row)["plan_code"] if row else None
    if row is None:
        conn.execute(
            """
            INSERT INTO app.tenant_subscription (tenant_id, plan_code, status, dunning_stage)
            VALUES (%s, %s, 'active', 'none')
            """,
            (tenant_id, plan_code),
        )
    else:
        conn.execute(
            """
            UPDATE app.tenant_subscription
            SET plan_code = %s, updated_ts = now()
            WHERE tenant_id = %s
            """,
            (plan_code, tenant_id),
        )
    insert_ledger_event(
        conn,
        tenant_id=tenant_id,
        event_type="plan_changed",
        actor=actor,
        meta_json={"previous_plan_code": prev, "new_plan_code": plan_code},
    )


def cancel_subscription(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    actor: str,
    cancel_at_period_end: bool = False,
) -> None:
    cur = conn.execute(
        """
        UPDATE app.tenant_subscription
        SET status = CASE WHEN %s THEN status ELSE 'canceled' END,
            cancel_at_period_end = %s,
            updated_ts = now()
        WHERE tenant_id = %s
        RETURNING tenant_id
        """,
        (cancel_at_period_end, cancel_at_period_end, tenant_id),
    ).fetchone()
    if cur is None:
        raise ValueError("tenant_subscription_not_found")
    if not cancel_at_period_end:
        insert_ledger_event(
            conn,
            tenant_id=tenant_id,
            event_type="cancellation",
            actor=actor,
            meta_json={"immediate": True},
        )
    else:
        insert_ledger_event(
            conn,
            tenant_id=tenant_id,
            event_type="cancellation",
            actor=actor,
            meta_json={"cancel_at_period_end": True},
        )


def record_renewal_event(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    actor: str,
    meta_json: dict[str, Any] | None = None,
) -> None:
    row = conn.execute(
        "SELECT 1 FROM app.tenant_subscription WHERE tenant_id = %s",
        (tenant_id,),
    ).fetchone()
    if row is None:
        raise ValueError("tenant_subscription_not_found")
    insert_ledger_event(
        conn,
        tenant_id=tenant_id,
        event_type="renewal",
        actor=actor,
        meta_json=meta_json or {},
    )


def record_payment_allocation(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    actor: str,
    amount_gross_cents: int | None = None,
    currency: str = "EUR",
    meta_json: dict[str, Any] | None = None,
) -> None:
    meta = meta_json or {}
    insert_ledger_event(
        conn,
        tenant_id=tenant_id,
        event_type="payment_allocated",
        currency=currency,
        amount_gross_cents=amount_gross_cents,
        actor=actor,
        meta_json=meta,
    )


def list_tenants_for_subscription_prepaid_billing(
    conn: psycopg.Connection[Any],
    *,
    tenant_id_filter: str | None = None,
) -> list[dict[str, Any]]:
    """
    Aktive Abo-Tenants mit bekanntem Plankatalog, deren kommerzieller Vertrag
    abgeschlossen und adminseitig freigegeben ist (608).
    """
    admin_done = "admin_review_complete"
    if tenant_id_filter and tenant_id_filter.strip():
        tid = tenant_id_filter.strip()
        q = (
            """
            SELECT
                s.tenant_id, s.plan_code, s.status,
                p.net_amount_cents, p.vat_rate_bps,
                p.reference_period_days, p.currency, p.billing_interval
            FROM app.tenant_subscription s
            INNER JOIN app.billing_subscription_plan p ON p.plan_code = s.plan_code
            WHERE s.tenant_id = %s
              AND s.status = 'active'
              AND p.is_active = true
              AND EXISTS (
                  SELECT 1
                  FROM app.tenant_contract tc
                  WHERE tc.tenant_id = s.tenant_id
                    AND tc.status = %s
              )
            """
        )
        rows = conn.execute(q, (tid, admin_done)).fetchall()
    else:
        q = (
            """
            SELECT
                s.tenant_id, s.plan_code, s.status,
                p.net_amount_cents, p.vat_rate_bps,
                p.reference_period_days, p.currency, p.billing_interval
            FROM app.tenant_subscription s
            INNER JOIN app.billing_subscription_plan p ON p.plan_code = s.plan_code
            WHERE s.status = 'active'
              AND p.is_active = true
              AND EXISTS (
                  SELECT 1
                  FROM app.tenant_contract tc
                  WHERE tc.tenant_id = s.tenant_id
                    AND tc.status = %s
              )
            ORDER BY s.tenant_id
            """
        )
        rows = conn.execute(q, (admin_done,)).fetchall()
    return [dict(r) for r in rows]


def subscription_ledger_deduction_exists(
    conn: psycopg.Connection[Any], *, tenant_id: str, accrual_date: date
) -> bool:
    r = conn.execute(
        """
        SELECT 1 FROM app.subscription_billing_ledger
        WHERE tenant_id = %s AND accrual_date_utc = %s
        """,
        (tenant_id, accrual_date),
    ).fetchone()
    return r is not None


def insert_subscription_billing_ledger_deduction(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    accrual_date: date,
    plan_code: str,
    net_amount_cents_eur: int,
    amount_list_usd: Decimal,
    vat_rate_bps: int,
    idempotency_key: str,
    meta_json: dict[str, Any],
) -> UUID:
    row = conn.execute(
        """
        INSERT INTO app.subscription_billing_ledger (
            tenant_id, entry_type, accrual_date_utc, plan_code,
            net_amount_cents_eur, amount_list_usd, vat_rate_bps, idempotency_key,
            meta_json
        )
        VALUES (
            %s, 'DEDUCTION', %s, %s, %s, %s, %s, %s, %s::jsonb
        )
        ON CONFLICT (tenant_id, accrual_date_utc) DO NOTHING
        RETURNING entry_id
        """,
        (
            tenant_id,
            accrual_date,
            plan_code,
            int(net_amount_cents_eur),
            str(amount_list_usd),
            int(vat_rate_bps),
            idempotency_key[:500],
            Json(meta_json),
        ),
    ).fetchone()
    if row is not None:
        return UUID(str(dict(row)["entry_id"]))
    r2 = conn.execute(
        """
        SELECT entry_id FROM app.subscription_billing_ledger
        WHERE tenant_id = %s AND accrual_date_utc = %s
        """,
        (tenant_id, accrual_date),
    ).fetchone()
    if r2 is None:
        raise RuntimeError("subscription_ledger_upsert_failed")
    return UUID(str(dict(r2)["entry_id"]))


def set_subscription_suspended_insufficient_funds(
    conn: psycopg.Connection[Any], *, tenant_id: str
) -> None:
    cur = conn.execute(
        """
        UPDATE app.tenant_subscription
        SET status = 'suspended_insufficient_funds', updated_ts = now()
        WHERE tenant_id = %s AND status = 'active'
        RETURNING tenant_id
        """,
        (tenant_id,),
    ).fetchone()
    if cur is not None:
        insert_ledger_event(
            conn,
            tenant_id=tenant_id,
            event_type="dunning_updated",
            actor="billing_engine:subscription_daily",
            meta_json={"dunning": "suspended_insufficient_funds", "source": "prepaid"},
        )
    conn.execute(
        """
        UPDATE app.tenant_modul_mate_gates
        SET subscription_active = false, updated_ts = now()
        WHERE tenant_id = %s
        """,
        (tenant_id,),
    )


def ensure_customer_wallet_row(
    conn: psycopg.Connection[Any], *, tenant_id: str
) -> None:
    """Sicherstellen, dass app.customer_wallet eine Zeile hat (FOR UPDATE/Wallet)."""
    conn.execute(
        """
        INSERT INTO app.customer_wallet (tenant_id, prepaid_balance_list_usd)
        VALUES (%s, 0)
        ON CONFLICT (tenant_id) DO NOTHING
        """,
        (tenant_id,),
    )
