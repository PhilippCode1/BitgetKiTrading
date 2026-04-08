"""Postgres-Helfer fuer kommerzielle Ledger-/Plan-Abfragen."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Json


def fetch_plan_definitions(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT plan_id, display_name, entitlements_json, llm_monthly_token_cap,
               llm_per_1k_tokens_list_usd, transparency_note, created_ts
        FROM app.commercial_plan_definitions
        ORDER BY plan_id
        """
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        if d.get("created_ts") is not None:
            d["created_ts"] = d["created_ts"].isoformat()
        out.append(d)
    return out


def fetch_tenant_state(
    conn: psycopg.Connection[Any], *, tenant_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT tenant_id, plan_id, budget_cap_usd_month, updated_ts
        FROM app.tenant_commercial_state
        WHERE tenant_id = %s
        """,
        (tenant_id,),
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    if d.get("updated_ts") is not None:
        d["updated_ts"] = d["updated_ts"].isoformat()
    return d


def sum_ledger_usd_month(
    conn: psycopg.Connection[Any], *, tenant_id: str
) -> Decimal:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(line_total_list_usd), 0)::numeric AS s
        FROM app.usage_ledger
        WHERE tenant_id = %s
          AND created_ts >= date_trunc('month', now())
        """,
        (tenant_id,),
    ).fetchone()
    if row is None:
        return Decimal("0")
    return Decimal(str(dict(row)["s"]))


def insert_usage_ledger_line(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    event_type: str,
    quantity: Decimal,
    unit: str,
    unit_price_list_usd: Decimal | None,
    line_total_list_usd: Decimal,
    correlation_id: str | None,
    actor: str | None,
    meta_json: dict[str, Any],
) -> UUID:
    row = conn.execute(
        """
        INSERT INTO app.usage_ledger (
            tenant_id, event_type, quantity, unit, unit_price_list_usd,
            line_total_list_usd, platform_markup_factor, correlation_id, actor, meta_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, 1.0, %s, %s, %s::jsonb)
        RETURNING ledger_id
        """,
        (
            tenant_id,
            event_type,
            str(quantity),
            unit,
            str(unit_price_list_usd) if unit_price_list_usd is not None else None,
            str(line_total_list_usd),
            correlation_id,
            actor,
            Json(meta_json),
        ),
    ).fetchone()
    if row is None:
        raise RuntimeError("insert_usage_ledger_line failed")
    return UUID(str(dict(row)["ledger_id"]))


def fetch_ledger_recent(
    conn: psycopg.Connection[Any], *, tenant_id: str, limit: int
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT ledger_id, tenant_id, event_type, quantity, unit, unit_price_list_usd,
               line_total_list_usd, platform_markup_factor, correlation_id, actor,
               meta_json, created_ts
        FROM app.usage_ledger
        WHERE tenant_id = %s
        ORDER BY created_ts DESC
        LIMIT %s
        """,
        (tenant_id, max(1, min(limit, 500))),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["ledger_id"] = str(d["ledger_id"])
        if d.get("created_ts") is not None:
            d["created_ts"] = d["created_ts"].isoformat()
        out.append(d)
    return out


def fetch_plan_for_tenant(
    conn: psycopg.Connection[Any], *, tenant_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT p.plan_id, p.display_name, p.entitlements_json, p.llm_monthly_token_cap,
               p.llm_per_1k_tokens_list_usd, p.transparency_note
        FROM app.tenant_commercial_state t
        INNER JOIN app.commercial_plan_definitions p ON p.plan_id = t.plan_id
        WHERE t.tenant_id = %s
        """,
        (tenant_id,),
    ).fetchone()
    return dict(row) if row else None


def sum_llm_tokens_month(conn: psycopg.Connection[Any], *, tenant_id: str) -> Decimal:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(quantity), 0)::numeric AS s
        FROM app.usage_ledger
        WHERE tenant_id = %s
          AND event_type = 'llm_tokens'
          AND created_ts >= date_trunc('month', now())
        """,
        (tenant_id,),
    ).fetchone()
    if row is None:
        return Decimal("0")
    return Decimal(str(dict(row)["s"]))
