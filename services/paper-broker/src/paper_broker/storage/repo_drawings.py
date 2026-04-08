from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import psycopg


def fetch_drawings_by_ids(
    conn: psycopg.Connection[Any], drawing_ids: list[str]
) -> list[dict[str, Any]]:
    if not drawing_ids:
        return []
    ph = ",".join(["%s::uuid"] * len(drawing_ids))
    rows = conn.execute(
        f"""
        SELECT drawing_id::text, type, geometry_json, updated_ts
        FROM app.drawings
        WHERE drawing_id IN ({ph})
        """,
        tuple(drawing_ids),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows or []:
        geo = r[2]
        if isinstance(geo, str):
            try:
                geo = json.loads(geo)
            except json.JSONDecodeError:
                continue
        if isinstance(geo, dict):
            out.append({"drawing_id": r[0], "type": r[1], "geometry": geo})
    return out


def zone_mid(geo: dict[str, Any]) -> Decimal | None:
    try:
        lo = Decimal(str(geo["price_low"]))
        hi = Decimal(str(geo["price_high"]))
        return (lo + hi) / Decimal("2")
    except (KeyError, TypeError, ValueError, ArithmeticError):
        return None
