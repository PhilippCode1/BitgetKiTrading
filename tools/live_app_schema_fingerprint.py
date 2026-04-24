"""
Deterministischer SHA-256 Fingerprint des Schemas `app` (Spalten, Indizes, Constraints)
via PostgreSQL-Kataloge — fuer Abgleich mit config/schema_master.hash (LIVE_APP_SCHEMA).
"""

from __future__ import annotations

import hashlib

from psycopg.rows import tuple_row


def _line(parts: list[object | None]) -> str:
    s = []
    for p in parts:
        if p is None:
            s.append("")
        else:
            t = str(p)
            t = t.replace("\n", " ").replace("\r", " ")
            while "  " in t:
                t = t.replace("  ", " ")
            s.append(t.strip())
    return "|".join(s)


def compute_live_app_schema_sha256_from_conn(conn: object) -> str:
    """
    Hasht: Spalten (information_schema), Indizes (pg_indexes), Integritaets-Constraints
    (pg_get_constraintdef). Relevant nur Schema `app`.
    """
    # tuple_row: Verbindung kann global dict_row haben — Hash muss trotzdem stabil sein
    lines: list[str] = []

    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute(
            """
            SELECT
                table_name,
                column_name,
                ordinal_position,
                data_type,
                is_nullable,
                COALESCE(column_default::text, '')
            FROM information_schema.columns
            WHERE table_schema = 'app'
            ORDER BY table_name, ordinal_position
            """
        )
        for row in cur.fetchall() or ():
            lines.append(
                "C:" + _line([row[i] for i in range(len(row))])
            )
        cur.execute(
            """
            SELECT indexname, tablename, indexdef
            FROM pg_indexes
            WHERE schemaname = 'app'
            ORDER BY indexname, tablename
            """
        )
        for row in cur.fetchall() or ():
            lines.append("I:" + _line([row[i] for i in range(len(row))]))
        cur.execute(
            """
            SELECT
                con.conname,
                c.relname,
                pg_get_constraintdef(con.oid, true)
            FROM pg_constraint con
            JOIN pg_class c ON c.oid = con.conrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'app' AND c.relkind = 'r'
            ORDER BY con.conname, c.relname
            """
        )
        for row in cur.fetchall() or ():
            lines.append("K:" + _line([row[i] for i in range(len(row))]))

    blob = "\n".join(lines) + "\n"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
