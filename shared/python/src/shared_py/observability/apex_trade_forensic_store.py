"""
Persistenz + Hash-Kette fuer app.apex_trade_forensics
(Spec: SHA256(prev || utf8) wie apex_audit_ledger).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg import errors as pg_errors
from psycopg.types.json import Json

from shared_py.audit_ledger_chain import (
    GENESIS_CHAIN_HASH,
    canonical_json_bytes,
    ledger_chain_digest,
)

logger = logging.getLogger("shared_py.apex_trade_forensic_store")

_TRADE_FORENSIC_ADVISORY_LOCK_KEY = 902_410_720


def upsert_apex_trade_forensic(
    conn: psycopg.Connection[Any],
    *,
    execution_id: str,
    signal_id: str | None,
    golden_record: dict[str, Any],
    tenant_id: str = "default",
) -> dict[str, Any] | None:
    """INSERT ON CONFLICT DO NOTHING. None bei Duplikat; sonst Kettendaten."""
    eid = UUID(str(execution_id))
    tid = (tenant_id or "default").strip() or "default"
    sid: str | None = None
    if signal_id:
        try:
            sid = str(UUID(str(signal_id)))
        except (TypeError, ValueError):
            sid = None

    canon = canonical_json_bytes(golden_record)
    with conn.transaction():
        conn.execute(
            "SELECT pg_advisory_xact_lock(%s)",
            (_TRADE_FORENSIC_ADVISORY_LOCK_KEY,),
        )
        row = conn.execute(
            "SELECT chain_checksum FROM app.apex_trade_forensics "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
        prev = row[0] if row and row[0] is not None else GENESIS_CHAIN_HASH
        if isinstance(prev, memoryview):
            prev = prev.tobytes()
        if len(prev) != 32:
            raise RuntimeError("apex_trade_forensics: letzter chain_hash ungueltig")
        ch = ledger_chain_digest(prev, canon)
        try:
            r_ins = conn.execute(
                """
                INSERT INTO app.apex_trade_forensics (
                    execution_id, signal_id, prev_chain_checksum,
                    chain_checksum, golden_record, tenant_id
                ) VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                ON CONFLICT (execution_id) DO NOTHING
                RETURNING id, prev_chain_checksum, chain_checksum
                """,
                (str(eid), sid, prev, ch, Json(golden_record), tid),
            ).fetchone()
        except pg_errors.UndefinedTable:
            logger.warning("apex_trade_forensics: Tabelle fehlt (Migration 626)")
            return None
    if r_ins is None:
        return {
            "inserted": False,
            "reason": "duplicate_or_skip",
            "execution_id": str(eid),
        }
    d = dict(r_ins)
    p = d.get("prev_chain_checksum")
    c = d.get("chain_checksum")
    if isinstance(p, memoryview):
        p = p.tobytes()
    if isinstance(c, memoryview):
        c = c.tobytes()
    return {
        "inserted": True,
        "id": int(d["id"]),
        "execution_id": str(eid),
        "prev_chain_checksum_hex": p.hex() if p else None,
        "chain_checksum_hex": c.hex() if c else None,
    }


def fetch_apex_trade_forensic_row(
    conn: psycopg.Connection[Any], *, execution_id: str
) -> dict[str, Any] | None:
    try:
        r = conn.execute(
            """
            SELECT id, execution_id, signal_id, created_at,
                   prev_chain_checksum, chain_checksum, golden_record, tenant_id
            FROM app.apex_trade_forensics
            WHERE execution_id = %s::uuid
            """,
            (execution_id,),
        ).fetchone()
    except pg_errors.UndefinedTable:
        return None
    if r is None:
        return None
    d = dict(r)
    eid = d.get("execution_id")
    d["execution_id"] = str(eid) if eid is not None else None
    s = d.get("signal_id")
    d["signal_id"] = str(s) if s is not None else None
    for k in ("prev_chain_checksum", "chain_checksum"):
        v = d.get(k)
        if isinstance(v, memoryview):
            d[k] = v.tobytes()
    ca = d.get("created_at")
    if isinstance(ca, object) and hasattr(ca, "isoformat"):
        d["created_at"] = ca.isoformat()
    return d


def fetch_apex_rows_tenant_time_window(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    t_from: datetime,
    t_to: datetime,
) -> list[dict[str, Any]]:
    """
    Liest Forensik-Zeilen (global sortiert via id) fuer Report-Zeitraege.
    ``t_from``/``t_to`` inklusiv; Zeiten sollen timestamptz-kompatibel sein.
    """
    tid = (tenant_id or "").strip() or "default"
    try:
        out = conn.execute(
            """
            SELECT id, execution_id, signal_id, created_at,
                   prev_chain_checksum, chain_checksum, golden_record, tenant_id
            FROM app.apex_trade_forensics
            WHERE tenant_id = %s
              AND created_at >= %s
              AND created_at <= %s
            ORDER BY id ASC
            """,
            (tid, t_from, t_to),
        ).fetchall()
    except pg_errors.UndefinedTable:
        return []
    except pg_errors.UndefinedColumn:
        logger.warning("apex_trade_forensics: tenant_id fehlt (Migration 629)?")
        return []
    rows: list[dict[str, Any]] = []
    for r0 in out or []:
        d = dict(r0)
        eid = d.get("execution_id")
        d["execution_id"] = str(eid) if eid is not None else None
        s = d.get("signal_id")
        d["signal_id"] = str(s) if s is not None else None
        for k in ("prev_chain_checksum", "chain_checksum"):
            v = d.get(k)
            if isinstance(v, memoryview):
                d[k] = v.tobytes()
        ca = d.get("created_at")
        if isinstance(ca, object) and hasattr(ca, "isoformat"):
            d["created_at"] = ca.isoformat()
        rows.append(d)
    return rows


def fetch_global_apex_chain_tip_hash_hex(
    conn: psycopg.Connection[Any],
) -> str | None:
    """Aktueller Kettenspitzen-``chain_checksum`` (gesamter Forensik-Ledger, hex)."""
    try:
        pr = conn.execute(
            "SELECT chain_checksum FROM app.apex_trade_forensics ORDER BY id DESC LIMIT 1"
        ).fetchone()
    except (pg_errors.UndefinedTable, pg_errors.Error):
        return None
    if not pr or pr[0] is None:
        return None
    p = pr[0]
    b = p.tobytes() if isinstance(p, memoryview) else bytes(p)
    return b.hex() if b else None


def verify_apex_row_with_ledger(
    conn: psycopg.Connection[Any], row: dict[str, Any]
) -> dict[str, Any]:
    """Berechnet Vorgaenger-Hash laut id-Reihenfolge und wendet ``verify_row_integrity`` an."""
    try:
        rid = int(row["id"])
    except (TypeError, KeyError, ValueError):
        return {**row, "verification": {"is_verified": False, "reason": "id_fehlt"}}
    try:
        expect = expected_previous_chain_for_row(conn, row_id=rid)
        v = verify_row_integrity(row, expected_prev_link=expect)
    except (OSError, pg_errors.Error) as e:
        return {**row, "verification": {"is_verified": False, "reason": str(e)[:120]}}
    return {**row, "verification": v}


def verify_row_integrity(
    row: dict[str, Any], *, expected_prev_link: bytes | None
) -> dict[str, Any]:
    """Lokale Payload-Integritaet + optionaler Kettengleichlauf mit Vorgaenger."""
    gr = row.get("golden_record")
    if not isinstance(gr, dict):
        return {
            "is_verified": False,
            "local_integrity_ok": False,
            "chain_link_ok": False,
            "reason": "golden_record_fehlt",
        }
    prev = row.get("prev_chain_checksum")
    ch = row.get("chain_checksum")
    p_ok = isinstance(prev, bytes | memoryview)
    c_ok = isinstance(ch, bytes | memoryview)
    if not p_ok or not c_ok:
        return {
            "is_verified": False,
            "local_integrity_ok": False,
            "chain_link_ok": False,
            "reason": "hash_spalten_fehlen",
        }
    if isinstance(prev, memoryview):
        prev = prev.tobytes()
    if isinstance(ch, memoryview):
        ch = ch.tobytes()
    canon = canonical_json_bytes(gr)
    local_ok = ledger_chain_digest(prev, canon) == ch
    if expected_prev_link is None:
        link_ok = prev == GENESIS_CHAIN_HASH
    else:
        link_ok = prev == expected_prev_link
    is_v = bool(local_ok and link_ok)
    return {
        "is_verified": is_v,
        "local_integrity_ok": local_ok,
        "chain_link_ok": link_ok,
    }


def expected_previous_chain_for_row(
    conn: psycopg.Connection[Any], *, row_id: int
) -> bytes:
    if row_id <= 1:
        return GENESIS_CHAIN_HASH
    try:
        pr = conn.execute(
            "SELECT chain_checksum FROM app.apex_trade_forensics WHERE id = %s",
            (row_id - 1,),
        ).fetchone()
    except pg_errors.UndefinedTable:
        return GENESIS_CHAIN_HASH
    if not pr or pr[0] is None:
        return GENESIS_CHAIN_HASH
    p = pr[0]
    return p.tobytes() if isinstance(p, memoryview) else bytes(p)
