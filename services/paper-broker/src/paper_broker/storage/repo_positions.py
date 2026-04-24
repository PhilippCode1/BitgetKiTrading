from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import psycopg


def insert_position(
    conn: psycopg.Connection[Any],
    *,
    account_id: UUID,
    tenant_id: str,
    symbol: str,
    side: str,
    qty_base: Decimal,
    entry_price_avg: Decimal,
    leverage: Decimal,
    margin_mode: str,
    isolated_margin: Decimal,
    state: str,
    opened_ts_ms: int,
    updated_ts_ms: int,
    meta: dict[str, Any],
    liq_price_sim: Decimal | None = None,
    signal_id: UUID | None = None,
    canonical_instrument_id: str | None = None,
    market_family: str | None = None,
    product_type: str | None = None,
) -> UUID:
    tid = str(tenant_id).strip() or "default"
    pid = uuid4()
    conn.execute(
        """
        INSERT INTO paper.positions (
            position_id, account_id, tenant_id, symbol, side, qty_base, entry_price_avg,
            leverage, margin_mode, isolated_margin, state,
            opened_ts_ms, updated_ts_ms, closed_ts_ms, liq_price_sim, meta,
            signal_id, canonical_instrument_id, market_family, product_type
        ) VALUES (
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,%s,%s::jsonb,
            %s,%s,%s,%s
        )
        """,
        (
            str(pid),
            str(account_id),
            tid,
            symbol,
            side,
            str(qty_base),
            str(entry_price_avg),
            str(leverage),
            margin_mode,
            str(isolated_margin),
            state,
            opened_ts_ms,
            updated_ts_ms,
            str(liq_price_sim) if liq_price_sim is not None else None,
            __import__("json").dumps(meta, separators=(",", ":"), ensure_ascii=False),
            str(signal_id) if signal_id is not None else None,
            canonical_instrument_id,
            market_family,
            product_type,
        ),
    )
    return pid


def get_position(
    conn: psycopg.Connection[Any], position_id: UUID, *, tenant_id: str
) -> dict[str, Any] | None:
    tid = str(tenant_id).strip() or "default"
    row = conn.execute(
        """
        SELECT * FROM paper.positions
        WHERE position_id = %s AND tenant_id = %s
        """,
        (str(position_id), tid),
    ).fetchone()
    return dict(row) if row else None


def count_open_positions(
    conn: psycopg.Connection[Any], *, tenant_id: str = "default"
) -> int:
    tid = str(tenant_id).strip() or "default"
    row = conn.execute(
        """
        SELECT COUNT(*)::int AS c FROM paper.positions
        WHERE state IN ('open', 'partially_closed')
          AND tenant_id = %s
        """,
        (tid,),
    ).fetchone()
    return int(row["c"]) if row else 0


def list_open_positions(
    conn: psycopg.Connection[Any], *, tenant_id: str = "default"
) -> list[dict[str, Any]]:
    tid = str(tenant_id).strip() or "default"
    rows = conn.execute(
        """
        SELECT * FROM paper.positions
        WHERE state IN ('open', 'partially_closed')
          AND tenant_id = %s
        ORDER BY opened_ts_ms ASC
        """,
        (tid,),
    ).fetchall()
    return [dict(r) for r in rows]


def update_position_qty_state(
    conn: psycopg.Connection[Any],
    position_id: UUID,
    *,
    tenant_id: str,
    qty_base: Decimal,
    entry_price_avg: Decimal,
    isolated_margin: Decimal,
    state: str,
    updated_ts_ms: int,
    closed_ts_ms: int | None,
    meta: dict[str, Any],
) -> None:
    tid = str(tenant_id).strip() or "default"
    conn.execute(
        """
        UPDATE paper.positions SET
            qty_base = %s, entry_price_avg = %s, isolated_margin = %s,
            state = %s, updated_ts_ms = %s, closed_ts_ms = %s, meta = %s::jsonb
        WHERE position_id = %s AND tenant_id = %s
        """,
        (
            str(qty_base),
            str(entry_price_avg),
            str(isolated_margin),
            state,
            updated_ts_ms,
            closed_ts_ms,
            __import__("json").dumps(meta, separators=(",", ":"), ensure_ascii=False),
            str(position_id),
            tid,
        ),
    )


def update_position_plan(
    conn: psycopg.Connection[Any],
    position_id: UUID,
    *,
    tenant_id: str,
    plan_version: str,
    stop_plan_json: dict[str, Any],
    tp_plan_json: dict[str, Any],
    stop_quality_score: int,
    rr_estimate: str | None,
    plan_updated_ts_ms: int,
) -> None:
    import json

    tid = str(tenant_id).strip() or "default"
    conn.execute(
        """
        UPDATE paper.positions SET
            plan_version = %s,
            stop_plan_json = %s::jsonb,
            tp_plan_json = %s::jsonb,
            stop_quality_score = %s,
            rr_estimate = %s,
            plan_updated_ts_ms = %s,
            updated_ts_ms = %s
        WHERE position_id = %s AND tenant_id = %s
        """,
        (
            plan_version,
            json.dumps(stop_plan_json, separators=(",", ":"), ensure_ascii=False),
            json.dumps(tp_plan_json, separators=(",", ":"), ensure_ascii=False),
            stop_quality_score,
            rr_estimate,
            plan_updated_ts_ms,
            plan_updated_ts_ms,
            str(position_id),
            tid,
        ),
    )


def update_tp_plan_only(
    conn: psycopg.Connection[Any],
    position_id: UUID,
    *,
    tenant_id: str,
    tp_plan_json: dict[str, Any],
    plan_updated_ts_ms: int,
) -> None:
    import json

    tid = str(tenant_id).strip() or "default"
    conn.execute(
        """
        UPDATE paper.positions SET
            tp_plan_json = %s::jsonb,
            plan_updated_ts_ms = %s,
            updated_ts_ms = %s
        WHERE position_id = %s AND tenant_id = %s
        """,
        (
            json.dumps(tp_plan_json, separators=(",", ":"), ensure_ascii=False),
            plan_updated_ts_ms,
            plan_updated_ts_ms,
            str(position_id),
            tid,
        ),
    )


def update_stop_plan_only(
    conn: psycopg.Connection[Any],
    position_id: UUID,
    *,
    tenant_id: str,
    stop_plan_json: dict[str, Any],
    plan_updated_ts_ms: int,
) -> None:
    import json

    tid = str(tenant_id).strip() or "default"
    conn.execute(
        """
        UPDATE paper.positions SET
            stop_plan_json = %s::jsonb,
            plan_updated_ts_ms = %s,
            updated_ts_ms = %s
        WHERE position_id = %s AND tenant_id = %s
        """,
        (
            json.dumps(stop_plan_json, separators=(",", ":"), ensure_ascii=False),
            plan_updated_ts_ms,
            plan_updated_ts_ms,
            str(position_id),
            tid,
        ),
    )


def update_position_meta(
    conn: psycopg.Connection[Any],
    position_id: UUID,
    *,
    tenant_id: str,
    meta: dict[str, Any],
    updated_ts_ms: int,
) -> None:
    import json

    tid = str(tenant_id).strip() or "default"
    conn.execute(
        """
        UPDATE paper.positions SET meta = %s::jsonb, updated_ts_ms = %s
        WHERE position_id = %s AND tenant_id = %s
        """,
        (
            json.dumps(meta, separators=(",", ":"), ensure_ascii=False),
            updated_ts_ms,
            str(position_id),
            tid,
        ),
    )


def set_position_liquidated(
    conn: psycopg.Connection[Any],
    position_id: UUID,
    *,
    tenant_id: str,
    updated_ts_ms: int,
    closed_ts_ms: int,
    meta: dict[str, Any],
) -> None:
    tid = str(tenant_id).strip() or "default"
    conn.execute(
        """
        UPDATE paper.positions SET
            qty_base = 0, state = 'liquidated', updated_ts_ms = %s, closed_ts_ms = %s,
            meta = %s::jsonb
        WHERE position_id = %s AND tenant_id = %s
        """,
        (
            updated_ts_ms,
            closed_ts_ms,
            __import__("json").dumps(meta, separators=(",", ":"), ensure_ascii=False),
            str(position_id),
            tid,
        ),
    )
