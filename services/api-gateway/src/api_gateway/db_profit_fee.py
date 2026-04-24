"""Persistenz Gewinnbeteiligung / High-Water-Mark (Prompt 15 / 43: Equity, Cashflow)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID

import psycopg
import psycopg.errors
from psycopg.types.json import Json
from shared_py.profit_fee_engine import (
    PROFIT_FEE_ENGINE_VERSION,
    compute_profit_fee_hwm_statement,
)


def fetch_hwm_cents(
    conn: psycopg.Connection[Any], *, tenant_id: str, trading_mode: str
) -> int:
    row = conn.execute(
        """
        SELECT high_water_mark_cents
        FROM app.profit_fee_hwm_state
        WHERE tenant_id = %s AND trading_mode = %s
        """,
        (tenant_id, trading_mode),
    ).fetchone()
    if row is None:
        return 0
    return int(row["high_water_mark_cents"])


def ensure_hwm_row(
    conn: psycopg.Connection[Any], *, tenant_id: str, trading_mode: str
) -> None:
    conn.execute(
        """
        INSERT INTO app.profit_fee_hwm_state (
            tenant_id, trading_mode, high_water_mark_cents
        )
        VALUES (%s, %s, 0)
        ON CONFLICT (tenant_id, trading_mode) DO NOTHING
        """,
        (tenant_id, trading_mode),
    )


def apply_hwm_external_cashflow_list_usd(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    delta_list_usd: Decimal,
) -> None:
    """
    Verschiebt den gespeicherten HWM in Cent um die gleiche externe Zahlung wie die Wallet
    (Einzahlung +, Auszahlung -), damit keine fiktive Ueberschreitung des bisherigen
    Hoechststands entsteht.
    """
    delta_cents = int(
        (delta_list_usd * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    if delta_cents == 0:
        return
    for mode in ("paper", "live"):
        ensure_hwm_row(conn, tenant_id=tenant_id, trading_mode=mode)
        conn.execute(
            """
            UPDATE app.profit_fee_hwm_state
            SET high_water_mark_cents = GREATEST(0, high_water_mark_cents + %s),
                updated_ts = now()
            WHERE tenant_id = %s AND trading_mode = %s
            """,
            (delta_cents, tenant_id, mode),
        )


def maybe_apply_hwm_cashflow_for_wallet_reason(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    delta_list_usd: Decimal,
    reason_code: str,
) -> None:
    """Koppelt bekannte Ein-/Auszahlungsgruende an HWM-Verschiebung; ignoriert DB-Fehler."""
    r = (reason_code or "").strip()
    is_deposit = r == "payment_deposit" and delta_list_usd > 0
    is_withdrawal = r in (
        "wallet_withdrawal",
        "admin_payout",
        "payout",
        "payment_withdrawal",
    ) and delta_list_usd < 0
    if not (is_deposit or is_withdrawal):
        return
    try:
        apply_hwm_external_cashflow_list_usd(
            conn, tenant_id=tenant_id, delta_list_usd=delta_list_usd
        )
    except psycopg.errors.UndefinedTable:
        return


def insert_calculation_event(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    trading_mode: str,
    period_start: date,
    period_end: date,
    actor: str,
    input_json: dict[str, Any],
    output_json: dict[str, Any],
    statement_id: UUID | None = None,
) -> UUID:
    row = conn.execute(
        """
        INSERT INTO app.profit_fee_calculation_event (
            tenant_id, trading_mode, period_start, period_end, actor,
            engine_version, input_json, output_json, statement_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
        RETURNING event_id
        """,
        (
            tenant_id,
            trading_mode,
            period_start,
            period_end,
            actor[:256],
            PROFIT_FEE_ENGINE_VERSION,
            Json(input_json),
            Json(output_json),
            str(statement_id) if statement_id else None,
        ),
    ).fetchone()
    assert row is not None
    return UUID(str(row["event_id"]))


def _row_statement(r: Any) -> dict[str, Any]:
    d = dict(r)
    d["statement_id"] = str(d["statement_id"])
    if d.get("superseded_by"):
        d["superseded_by"] = str(d["superseded_by"])
    if d.get("corrects_statement_id"):
        d["corrects_statement_id"] = str(d["corrects_statement_id"])
    for k in ("customer_ack_ts", "admin_approved_ts", "created_ts", "updated_ts"):
        v = d.get(k)
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


def fetch_statement(
    conn: psycopg.Connection[Any], *, statement_id: UUID
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM app.profit_fee_statement WHERE statement_id = %s
        """,
        (str(statement_id),),
    ).fetchone()
    return _row_statement(row) if row else None


def list_statements_for_tenant(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    include_draft: bool = False,
    limit: int = 50,
) -> list[dict[str, Any]]:
    lim = max(1, min(limit, 200))
    if include_draft:
        status_filter = ""
        params: tuple[Any, ...] = (tenant_id, lim)
    else:
        status_filter = "AND status IN ('issued','disputed','admin_approved')"
        params = (tenant_id, lim)
    rows = conn.execute(
        f"""
        SELECT * FROM app.profit_fee_statement
        WHERE tenant_id = %s {status_filter}
        ORDER BY period_end DESC, created_ts DESC
        LIMIT %s
        """,
        params,
    ).fetchall()
    return [_row_statement(r) for r in rows]


def list_statements_admin(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str | None,
    status: str | None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    lim = max(1, min(limit, 500))
    conds: list[str] = []
    params: list[Any] = []
    if tenant_id:
        conds.append("tenant_id = %s")
        params.append(tenant_id)
    if status:
        conds.append("status = %s")
        params.append(status[:32])
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    params.append(lim)
    rows = conn.execute(
        f"""
        SELECT * FROM app.profit_fee_statement
        {where}
        ORDER BY updated_ts DESC
        LIMIT %s
        """,
        tuple(params),
    ).fetchall()
    return [_row_statement(r) for r in rows]


def create_draft_statement(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    trading_mode: str,
    period_start: date,
    period_end: date,
    cumulative_realized_pnl_cents: int,
    fee_rate_basis_points: int,
    actor: str,
    currency: str = "USD",
    pnl_source_ref: str | None = None,
    corrects_statement_id: UUID | None = None,
) -> dict[str, Any]:
    ensure_hwm_row(conn, tenant_id=tenant_id, trading_mode=trading_mode)
    hwm_before = fetch_hwm_cents(conn, tenant_id=tenant_id, trading_mode=trading_mode)
    calc = compute_profit_fee_hwm_statement(
        current_equity_value_cents=cumulative_realized_pnl_cents,
        highest_equity_value_before_cents=hwm_before,
        fee_rate_basis_points=fee_rate_basis_points,
    )
    input_json: dict[str, Any] = {
        "current_equity_value_cents": cumulative_realized_pnl_cents,
        "cumulative_realized_pnl_cents": cumulative_realized_pnl_cents,
        "pnl_source_ref": (pnl_source_ref or "")[:512],
        "currency": currency[:8],
    }
    calculation_json = {
        **calc,
        "pnl_source_ref": input_json["pnl_source_ref"],
        "currency": currency,
    }
    row = conn.execute(
        """
        INSERT INTO app.profit_fee_statement (
            tenant_id, trading_mode, period_start, period_end,
            cumulative_realized_pnl_cents, hwm_before_cents, incremental_profit_cents,
            fee_rate_basis_points, fee_amount_cents, currency, status, calculation_json,
            corrects_statement_id
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft', %s::jsonb, %s
        )
        RETURNING statement_id
        """,
        (
            tenant_id,
            trading_mode,
            period_start,
            period_end,
            cumulative_realized_pnl_cents,
            hwm_before,
            calc["incremental_profit_cents"],
            fee_rate_basis_points,
            calc["fee_amount_cents"],
            currency[:8],
            Json(calculation_json),
            str(corrects_statement_id) if corrects_statement_id else None,
        ),
    ).fetchone()
    assert row is not None
    sid = UUID(str(row["statement_id"]))
    insert_calculation_event(
        conn,
        tenant_id=tenant_id,
        trading_mode=trading_mode,
        period_start=period_start,
        period_end=period_end,
        actor=actor,
        input_json=input_json,
        output_json=calc,
        statement_id=sid,
    )
    out = fetch_statement(conn, statement_id=sid)
    assert out is not None
    return out


def issue_statement(
    conn: psycopg.Connection[Any], *, statement_id: UUID
) -> dict[str, Any] | None:
    conn.execute(
        """
        UPDATE app.profit_fee_statement
        SET status = 'issued', updated_ts = now()
        WHERE statement_id = %s AND status = 'draft'
        """,
        (str(statement_id),),
    )
    return fetch_statement(conn, statement_id=statement_id)


def acknowledge_statement(
    conn: psycopg.Connection[Any],
    *,
    statement_id: UUID,
    note: str | None,
) -> dict[str, Any] | None:
    conn.execute(
        """
        UPDATE app.profit_fee_statement
        SET customer_ack_ts = now(),
            customer_ack_note = %s,
            updated_ts = now()
        WHERE statement_id = %s AND status = 'issued'
        """,
        ((note or "")[:2000] or None, str(statement_id)),
    )
    return fetch_statement(conn, statement_id=statement_id)


def dispute_statement(
    conn: psycopg.Connection[Any],
    *,
    statement_id: UUID,
    reason: str,
) -> dict[str, Any] | None:
    conn.execute(
        """
        UPDATE app.profit_fee_statement
        SET status = 'disputed',
            dispute_reason = %s,
            updated_ts = now()
        WHERE statement_id = %s AND status = 'issued'
        """,
        (reason[:4000], str(statement_id)),
    )
    return fetch_statement(conn, statement_id=statement_id)


def void_statement(
    conn: psycopg.Connection[Any],
    *,
    statement_id: UUID,
    reason: str,
) -> dict[str, Any] | None:
    conn.execute(
        """
        UPDATE app.profit_fee_statement
        SET status = 'voided',
            void_reason = %s,
            updated_ts = now()
        WHERE statement_id = %s
          AND status IN ('draft','issued','disputed')
        """,
        (reason[:4000], str(statement_id)),
    )
    return fetch_statement(conn, statement_id=statement_id)


def approve_statement(
    conn: psycopg.Connection[Any],
    *,
    statement_id: UUID,
    admin_actor: str,
) -> dict[str, Any] | None:
    """Atomare HWM-Aktualisierung; Freigabe-Vorbedingungen in der Route pruefen."""
    st = fetch_statement(conn, statement_id=statement_id)
    if not st:
        return None
    if st["status"] not in ("issued", "disputed"):
        return None

    tenant_id = str(st["tenant_id"])
    mode = str(st["trading_mode"])
    hwm_before = int(st["hwm_before_cents"])
    cum_end = int(st["cumulative_realized_pnl_cents"])
    # Drawdown senkt HWM nicht; neuer Hoechststand nur, wenn Equity wieder ansteigt.
    new_hwm = max(hwm_before, cum_end)

    res = conn.execute(
        """
        UPDATE app.profit_fee_hwm_state
        SET high_water_mark_cents = %s,
            updated_ts = now()
        WHERE tenant_id = %s AND trading_mode = %s
          AND high_water_mark_cents = %s
        RETURNING high_water_mark_cents
        """,
        (new_hwm, tenant_id, mode, hwm_before),
    ).fetchone()
    if res is None:
        return None

    conn.execute(
        """
        UPDATE app.profit_fee_statement
        SET status = 'admin_approved',
            admin_approved_ts = now(),
            admin_approved_by = %s,
            updated_ts = now()
        WHERE statement_id = %s AND status IN ('issued','disputed')
        """,
        (admin_actor[:256], str(statement_id)),
    )
    return fetch_statement(conn, statement_id=statement_id)


def reopen_disputed_to_issued(
    conn: psycopg.Connection[Any],
    *,
    statement_id: UUID,
    resolution_note: str,
) -> dict[str, Any] | None:
    conn.execute(
        """
        UPDATE app.profit_fee_statement
        SET status = 'issued',
            dispute_reason = COALESCE(dispute_reason,'') || E'\\n[resolution] ' || %s,
            updated_ts = now()
        WHERE statement_id = %s AND status = 'disputed'
        """,
        (resolution_note[:2000], str(statement_id)),
    )
    return fetch_statement(conn, statement_id=statement_id)


def admin_preview_numbers(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    trading_mode: str,
    cumulative_realized_pnl_cents: int,
    fee_rate_basis_points: int,
) -> dict[str, Any]:
    ensure_hwm_row(conn, tenant_id=tenant_id, trading_mode=trading_mode)
    hwm = fetch_hwm_cents(conn, tenant_id=tenant_id, trading_mode=trading_mode)
    return compute_profit_fee_hwm_statement(
        current_equity_value_cents=cumulative_realized_pnl_cents,
        highest_equity_value_before_cents=hwm,
        fee_rate_basis_points=fee_rate_basis_points,
    )
