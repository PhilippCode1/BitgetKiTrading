"""Append-only Kunden-Domain-Events mit Idempotenz und Read-Model-Cursor (Prompt 22)."""

from __future__ import annotations

import re
from typing import Any

import psycopg
from psycopg.types.json import Json

_IDEM_RE = re.compile(r"^[\w.\-:@]{1,256}$")


def _sanitize_idempotency_key(raw: str) -> str:
    s = (raw or "").strip()
    if not s or len(s) > 256 or not _IDEM_RE.match(s):
        raise ValueError("invalid_idempotency_key")
    return s


def append_customer_domain_event(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    aggregate_type: str,
    event_type: str,
    payload: dict[str, Any],
    idempotency_key: str,
    correlation_id: str | None = None,
    source: str = "gateway",
) -> tuple[bool, int]:
    """
    Fuegt ein Ereignis ein. Idempotent: bei gleichem (tenant_id, idempotency_key)
    wird nichts eingefuegt.

    Returns:
        (inserted, seq): inserted False bei Replay; seq ist die gueltige Sequenznummer.
    """
    key = _sanitize_idempotency_key(idempotency_key)
    row = conn.execute(
        """
        INSERT INTO app.customer_domain_event (
            tenant_id, aggregate_type, event_type, payload_json,
            correlation_id, idempotency_key, source
        )
        VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s)
        ON CONFLICT (tenant_id, idempotency_key) DO NOTHING
        RETURNING seq
        """,
        (
            tenant_id,
            aggregate_type[:64],
            event_type[:128],
            Json(payload),
            (correlation_id[:256] if correlation_id else None),
            key,
            source[:64],
        ),
    ).fetchone()
    if row is not None:
        seq = int(dict(row)["seq"])
        bump_portal_read_cursor(conn, tenant_id=tenant_id, seq=seq)
        return True, seq
    ex = conn.execute(
        """
        SELECT seq FROM app.customer_domain_event
        WHERE tenant_id = %s AND idempotency_key = %s
        """,
        (tenant_id, key),
    ).fetchone()
    if ex is None:
        raise RuntimeError("domain_event_idempotent_lookup_failed")
    return False, int(dict(ex)["seq"])


def bump_portal_read_cursor(
    conn: psycopg.Connection[Any], *, tenant_id: str, seq: int
) -> None:
    conn.execute(
        """
        INSERT INTO app.customer_read_model_state (tenant_id, portal_seq_applied, updated_ts)
        VALUES (%s, %s, now())
        ON CONFLICT (tenant_id) DO UPDATE SET
            portal_seq_applied = GREATEST(
                app.customer_read_model_state.portal_seq_applied,
                EXCLUDED.portal_seq_applied
            ),
            updated_ts = now()
        """,
        (tenant_id, seq),
    )


def fetch_read_model_state(
    conn: psycopg.Connection[Any], *, tenant_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT tenant_id, portal_seq_applied, updated_ts
        FROM app.customer_read_model_state
        WHERE tenant_id = %s
        """,
        (tenant_id,),
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    ut = d.get("updated_ts")
    d["updated_ts"] = ut.isoformat() if ut is not None else None
    d["portal_seq_applied"] = int(d["portal_seq_applied"])
    max_row = conn.execute(
        """
        SELECT COALESCE(MAX(seq), 0)::bigint AS m
        FROM app.customer_domain_event
        WHERE tenant_id = %s
        """,
        (tenant_id,),
    ).fetchone()
    d["domain_event_seq_max"] = int(dict(max_row or {"m": 0})["m"])
    gap = d["domain_event_seq_max"] - d["portal_seq_applied"]
    d["read_model_gap_seq"] = max(0, gap)
    return d


def fetch_domain_events_customer_safe(
    conn: psycopg.Connection[Any], *, tenant_id: str, limit: int
) -> list[dict[str, Any]]:
    lim = max(1, min(limit, 200))
    rows = conn.execute(
        """
        SELECT seq, aggregate_type, event_type, payload_json, recorded_ts
        FROM app.customer_domain_event
        WHERE tenant_id = %s
        ORDER BY seq DESC
        LIMIT %s
        """,
        (tenant_id, lim),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["seq"] = int(d["seq"])
        rt = d.get("recorded_ts")
        d["recorded_ts"] = rt.isoformat() if rt is not None else None
        out.append(d)
    return out


def fetch_domain_events_admin(
    conn: psycopg.Connection[Any], *, tenant_id: str, limit: int, after_seq: int = 0
) -> list[dict[str, Any]]:
    lim = max(1, min(limit, 500))
    rows = conn.execute(
        """
        SELECT seq, tenant_id, aggregate_type, event_type, payload_json,
               correlation_id, idempotency_key, source, recorded_ts
        FROM app.customer_domain_event
        WHERE tenant_id = %s AND seq > %s
        ORDER BY seq ASC
        LIMIT %s
        """,
        (tenant_id, max(0, after_seq), lim),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["seq"] = int(d["seq"])
        rt = d.get("recorded_ts")
        d["recorded_ts"] = rt.isoformat() if rt is not None else None
        out.append(d)
    return out


def admin_catch_up_read_cursor(
    conn: psycopg.Connection[Any], *, tenant_id: str
) -> dict[str, Any]:
    """Setzt portal_seq_applied auf MAX(seq) — nach manueller Nachbearbeitung / Recovery."""
    row = conn.execute(
        """
        SELECT COALESCE(MAX(seq), 0)::bigint AS m
        FROM app.customer_domain_event
        WHERE tenant_id = %s
        """,
        (tenant_id,),
    ).fetchone()
    m = int(dict(row or {"m": 0})["m"])
    conn.execute(
        """
        INSERT INTO app.customer_read_model_state (tenant_id, portal_seq_applied, updated_ts)
        VALUES (%s, %s, now())
        ON CONFLICT (tenant_id) DO UPDATE SET
            portal_seq_applied = GREATEST(
                app.customer_read_model_state.portal_seq_applied,
                EXCLUDED.portal_seq_applied
            ),
            updated_ts = now()
        """,
        (tenant_id, m),
    )
    return {"tenant_id": tenant_id, "portal_seq_applied": m}
