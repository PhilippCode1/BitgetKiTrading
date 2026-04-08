"""Treasury-Konfiguration und Profit-Fee-Settlement (Prompt 16)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Json
from shared_py.settlement_pipeline import (
    SETTLEMENT_PIPELINE_VERSION,
    assert_transition_allowed,
    initial_status,
    is_terminal_status,
    public_audit_payload_trim,
)


def _row_cfg(r: Any) -> dict[str, Any]:
    d = dict(r)
    d["config_id"] = str(d["config_id"])
    for k in ("created_ts", "updated_ts"):
        v = d.get(k)
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


def _row_settlement(r: Any) -> dict[str, Any]:
    d = dict(r)
    d["settlement_id"] = str(d["settlement_id"])
    d["statement_id"] = str(d["statement_id"])
    if d.get("treasury_config_id"):
        d["treasury_config_id"] = str(d["treasury_config_id"])
    for k in (
        "treasury_reviewed_ts",
        "payout_submitted_ts",
        "settled_ts",
        "created_ts",
        "updated_ts",
    ):
        v = d.get(k)
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


def list_treasury_configs(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM app.treasury_settlement_config
        ORDER BY label ASC
        """
    ).fetchall()
    return [_row_cfg(r) for r in rows]


def fetch_treasury_config(
    conn: psycopg.Connection[Any], *, config_id: UUID
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM app.treasury_settlement_config WHERE config_id = %s
        """,
        (str(config_id),),
    ).fetchone()
    return _row_cfg(row) if row else None


def fetch_default_active_treasury_config_id(
    conn: psycopg.Connection[Any],
) -> UUID | None:
    row = conn.execute(
        """
        SELECT config_id FROM app.treasury_settlement_config
        WHERE active = true AND label = 'default'
        LIMIT 1
        """
    ).fetchone()
    if row:
        return UUID(str(row["config_id"]))
    row2 = conn.execute(
        """
        SELECT config_id FROM app.treasury_settlement_config
        WHERE active = true
        ORDER BY label ASC
        LIMIT 1
        """
    ).fetchone()
    return UUID(str(row2["config_id"])) if row2 else None


def update_treasury_config(
    conn: psycopg.Connection[Any],
    *,
    config_id: UUID,
    target_asset: str | None = None,
    network: str | None = None,
    destination_hint_public: str | None = None,
    daily_limit_major_units: str | None = None,
    monthly_limit_major_units: str | None = None,
    active: bool | None = None,
    manual_execution_only: bool | None = None,
) -> dict[str, Any] | None:
    cur = fetch_treasury_config(conn, config_id=config_id)
    if not cur:
        return None
    sets: list[str] = []
    params: list[Any] = []
    if target_asset is not None:
        sets.append("target_asset = %s")
        params.append(target_asset[:32])
    if network is not None:
        sets.append("network = %s")
        params.append(network[:64])
    if destination_hint_public is not None:
        sets.append("destination_hint_public = %s")
        params.append(destination_hint_public[:2000] or None)
    if daily_limit_major_units is not None:
        sets.append("daily_limit_major_units = %s")
        params.append(daily_limit_major_units)
    if monthly_limit_major_units is not None:
        sets.append("monthly_limit_major_units = %s")
        params.append(monthly_limit_major_units)
    if active is not None:
        sets.append("active = %s")
        params.append(active)
    if manual_execution_only is not None:
        sets.append("manual_execution_only = %s")
        params.append(manual_execution_only)
    if not sets:
        return cur
    sets.append("updated_ts = now()")
    params.append(str(config_id))
    conn.execute(
        f"""
        UPDATE app.treasury_settlement_config
        SET {", ".join(sets)}
        WHERE config_id = %s
        """,
        tuple(params),
    )
    return fetch_treasury_config(conn, config_id=config_id)


def append_settlement_audit(
    conn: psycopg.Connection[Any],
    *,
    settlement_id: UUID,
    event_type: str,
    actor: str,
    payload: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO app.profit_fee_settlement_audit (
            settlement_id, event_type, actor, payload_json
        )
        VALUES (%s, %s, %s, %s::jsonb)
        """,
        (
            str(settlement_id),
            event_type[:64],
            actor[:256],
            Json(public_audit_payload_trim(payload)),
        ),
    )


def fetch_settlement(
    conn: psycopg.Connection[Any], *, settlement_id: UUID
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM app.profit_fee_settlement_request WHERE settlement_id = %s
        """,
        (str(settlement_id),),
    ).fetchone()
    return _row_settlement(row) if row else None


def fetch_settlement_by_statement(
    conn: psycopg.Connection[Any], *, statement_id: UUID
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM app.profit_fee_settlement_request
        WHERE statement_id = %s
        ORDER BY created_ts DESC
        LIMIT 1
        """,
        (str(statement_id),),
    ).fetchone()
    return _row_settlement(row) if row else None


def list_settlements_admin(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str | None,
    status: str | None,
    limit: int,
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
        SELECT * FROM app.profit_fee_settlement_request
        {where}
        ORDER BY updated_ts DESC
        LIMIT %s
        """,
        tuple(params),
    ).fetchall()
    return [_row_settlement(r) for r in rows]


def list_settlements_for_tenant(
    conn: psycopg.Connection[Any], *, tenant_id: str, limit: int
) -> list[dict[str, Any]]:
    lim = max(1, min(limit, 100))
    rows = conn.execute(
        """
        SELECT settlement_id, statement_id, status, fee_amount_cents, currency,
               external_submission_ref, confirmation_ref, created_ts, updated_ts
        FROM app.profit_fee_settlement_request
        WHERE tenant_id = %s
        ORDER BY updated_ts DESC
        LIMIT %s
        """,
        (tenant_id, lim),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["settlement_id"] = str(d["settlement_id"])
        d["statement_id"] = str(d["statement_id"])
        for k in ("created_ts", "updated_ts"):
            v = d.get(k)
            d[k] = v.isoformat() if hasattr(v, "isoformat") else v
        out.append(d)
    return out


def list_settlement_audit(
    conn: psycopg.Connection[Any], *, settlement_id: UUID, limit: int
) -> list[dict[str, Any]]:
    lim = max(1, min(limit, 500))
    rows = conn.execute(
        """
        SELECT audit_id, event_type, actor, payload_json, created_ts
        FROM app.profit_fee_settlement_audit
        WHERE settlement_id = %s
        ORDER BY created_ts ASC
        LIMIT %s
        """,
        (str(settlement_id), lim),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["audit_id"] = str(d["audit_id"])
        ct = d.get("created_ts")
        d["created_ts"] = ct.isoformat() if hasattr(ct, "isoformat") else ct
        out.append(d)
    return out


def create_settlement_request(
    conn: psycopg.Connection[Any],
    *,
    statement_id: UUID,
    treasury_config_id: UUID | None,
    actor: str,
    secondary_treasury_approval_required: bool,
) -> dict[str, Any] | None:
    st = conn.execute(
        """
        SELECT tenant_id, status, fee_amount_cents, currency
        FROM app.profit_fee_statement
        WHERE statement_id = %s
        """,
        (str(statement_id),),
    ).fetchone()
    if not st:
        return None
    if str(st["status"]) != "admin_approved":
        return None
    fee = int(st["fee_amount_cents"])
    if fee <= 0:
        return None

    tid = str(st["tenant_id"])
    cur = str(st["currency"] or "USD")

    cfg_id = treasury_config_id
    if cfg_id is None:
        raw = fetch_default_active_treasury_config_id(conn)
        if raw is None:
            return None
        cfg_id = raw

    start = initial_status(
        secondary_treasury_approval_required=secondary_treasury_approval_required
    )

    row = conn.execute(
        """
        INSERT INTO app.profit_fee_settlement_request (
            statement_id, treasury_config_id, tenant_id,
            fee_amount_cents, currency, status, pipeline_version
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING settlement_id
        """,
        (
            str(statement_id),
            str(cfg_id),
            tid,
            fee,
            cur[:8],
            start,
            SETTLEMENT_PIPELINE_VERSION,
        ),
    ).fetchone()
    if not row:
        return None
    sid = UUID(str(row["settlement_id"]))
    append_settlement_audit(
        conn,
        settlement_id=sid,
        event_type="settlement_created",
        actor=actor,
        payload={
            "statement_id": str(statement_id),
            "treasury_config_id": str(cfg_id),
            "initial_status": start,
            "fee_amount_cents": fee,
        },
    )
    return fetch_settlement(conn, settlement_id=sid)


def _current_status(
    conn: psycopg.Connection[Any], settlement_id: UUID
) -> str | None:
    row = conn.execute(
        """
        SELECT status FROM app.profit_fee_settlement_request
        WHERE settlement_id = %s
        """,
        (str(settlement_id),),
    ).fetchone()
    return str(row["status"]) if row else None


def treasury_approve_settlement(
    conn: psycopg.Connection[Any],
    *,
    settlement_id: UUID,
    actor: str,
) -> dict[str, Any] | None:
    cur = _current_status(conn, settlement_id)
    if cur is None or is_terminal_status(cur):
        return None
    try:
        nxt = assert_transition_allowed(cur, "treasury_approve")
    except ValueError:
        return None
    upd = conn.execute(
        """
        UPDATE app.profit_fee_settlement_request
        SET status = %s,
            treasury_reviewed_ts = now(),
            treasury_reviewed_by = %s,
            updated_ts = now()
        WHERE settlement_id = %s AND status = %s
        RETURNING settlement_id
        """,
        (nxt, actor[:256], str(settlement_id), cur),
    ).fetchone()
    if not upd:
        return None
    append_settlement_audit(
        conn,
        settlement_id=settlement_id,
        event_type="treasury_approve",
        actor=actor,
        payload={"from_status": cur, "to_status": nxt},
    )
    return fetch_settlement(conn, settlement_id=settlement_id)


def record_payout_submission(
    conn: psycopg.Connection[Any],
    *,
    settlement_id: UUID,
    actor: str,
    external_submission_ref: str,
    note: str | None,
) -> dict[str, Any] | None:
    cur = _current_status(conn, settlement_id)
    if cur is None or is_terminal_status(cur):
        return None
    try:
        nxt = assert_transition_allowed(cur, "record_payout")
    except ValueError:
        return None
    ref = external_submission_ref[:512]
    note_s = (note or "")[:4000] or None
    upd = conn.execute(
        """
        UPDATE app.profit_fee_settlement_request
        SET status = %s,
            payout_submitted_ts = now(),
            payout_submitted_by = %s,
            external_submission_ref = %s,
            payout_submission_note = %s,
            updated_ts = now()
        WHERE settlement_id = %s AND status = %s
        RETURNING settlement_id
        """,
        (nxt, actor[:256], ref, note_s, str(settlement_id), cur),
    ).fetchone()
    if not upd:
        return None
    append_settlement_audit(
        conn,
        settlement_id=settlement_id,
        event_type="record_payout",
        actor=actor,
        payload={
            "from_status": cur,
            "to_status": nxt,
            "external_submission_ref": ref,
        },
    )
    return fetch_settlement(conn, settlement_id=settlement_id)


def confirm_settlement_settled(
    conn: psycopg.Connection[Any],
    *,
    settlement_id: UUID,
    actor: str,
    confirmation_ref: str,
    note: str | None,
) -> dict[str, Any] | None:
    cur = _current_status(conn, settlement_id)
    if cur is None or is_terminal_status(cur):
        return None
    try:
        nxt = assert_transition_allowed(cur, "confirm_settled")
    except ValueError:
        return None
    cref = confirmation_ref[:512]
    note_s = (note or "")[:4000] or None
    upd = conn.execute(
        """
        UPDATE app.profit_fee_settlement_request
        SET status = %s,
            settled_ts = now(),
            settled_by = %s,
            confirmation_ref = %s,
            settlement_note = %s,
            updated_ts = now()
        WHERE settlement_id = %s AND status = %s
        RETURNING settlement_id
        """,
        (nxt, actor[:256], cref, note_s, str(settlement_id), cur),
    ).fetchone()
    if not upd:
        return None
    append_settlement_audit(
        conn,
        settlement_id=settlement_id,
        event_type="confirm_settled",
        actor=actor,
        payload={"from_status": cur, "to_status": nxt, "confirmation_ref": cref},
    )
    return fetch_settlement(conn, settlement_id=settlement_id)


def cancel_settlement_request(
    conn: psycopg.Connection[Any],
    *,
    settlement_id: UUID,
    actor: str,
    reason: str,
) -> dict[str, Any] | None:
    cur = _current_status(conn, settlement_id)
    if cur is None or is_terminal_status(cur):
        return None
    try:
        nxt = assert_transition_allowed(cur, "cancel")
    except ValueError:
        return None
    rs = reason[:4000]
    upd = conn.execute(
        """
        UPDATE app.profit_fee_settlement_request
        SET status = %s,
            cancellation_reason = %s,
            updated_ts = now()
        WHERE settlement_id = %s AND status = %s
        RETURNING settlement_id
        """,
        (nxt, rs, str(settlement_id), cur),
    ).fetchone()
    if not upd:
        return None
    append_settlement_audit(
        conn,
        settlement_id=settlement_id,
        event_type="cancel",
        actor=actor,
        payload={"from_status": cur, "to_status": nxt, "reason": rs},
    )
    return fetch_settlement(conn, settlement_id=settlement_id)


def fail_settlement_request(
    conn: psycopg.Connection[Any],
    *,
    settlement_id: UUID,
    actor: str,
    reason: str,
) -> dict[str, Any] | None:
    cur = _current_status(conn, settlement_id)
    if cur is None or is_terminal_status(cur):
        return None
    try:
        nxt = assert_transition_allowed(cur, "fail")
    except ValueError:
        return None
    rs = reason[:4000]
    upd = conn.execute(
        """
        UPDATE app.profit_fee_settlement_request
        SET status = %s,
            failure_reason = %s,
            updated_ts = now()
        WHERE settlement_id = %s AND status = %s
        RETURNING settlement_id
        """,
        (nxt, rs, str(settlement_id), cur),
    ).fetchone()
    if not upd:
        return None
    append_settlement_audit(
        conn,
        settlement_id=settlement_id,
        event_type="fail",
        actor=actor,
        payload={"from_status": cur, "to_status": nxt, "reason": rs},
    )
    return fetch_settlement(conn, settlement_id=settlement_id)
