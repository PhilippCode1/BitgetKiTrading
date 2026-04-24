from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Json


def insert_post_trade_review(
    conn: psycopg.Connection[Any],
    row: dict[str, Any],
) -> UUID:
    """Persistiert learn.post_trade_review (Prompt 70)."""
    pay = {**row}
    pay["review_json"] = Json(pay["review_json"])
    pay["attribution_meta_json"] = Json(pay.get("attribution_meta_json") or {})
    te = pay["trade_evaluation_id"]
    if isinstance(te, UUID):
        pay["trade_evaluation_id"] = str(te)
    sig = pay.get("signal_id")
    if isinstance(sig, UUID):
        pay["signal_id"] = str(sig)
    ex = pay.get("execution_id")
    if isinstance(ex, UUID):
        pay["execution_id"] = str(ex)
    rid = conn.execute(
        """
        INSERT INTO learn.post_trade_review (
            signal_id, execution_id, trade_evaluation_id,
            scenario_excerpt_de, reference_price, reference_role,
            thesis_holds, window_start_ts_ms, window_end_ts_ms,
            pnl_net_usdt, side, reasoning_accuracy_0_1, quality_label,
            review_json, attribution_meta_json
        ) VALUES (
            %(signal_id)s, %(execution_id)s, %(trade_evaluation_id)s,
            %(scenario_excerpt_de)s, %(reference_price)s, %(reference_role)s,
            %(thesis_holds)s, %(window_start_ts_ms)s, %(window_end_ts_ms)s,
            %(pnl_net_usdt)s, %(side)s, %(reasoning_accuracy_0_1)s, %(quality_label)s,
            %(review_json)s, %(attribution_meta_json)s
        )
        ON CONFLICT (trade_evaluation_id) DO UPDATE SET
            scenario_excerpt_de = EXCLUDED.scenario_excerpt_de,
            reference_price = EXCLUDED.reference_price,
            reference_role = EXCLUDED.reference_role,
            thesis_holds = EXCLUDED.thesis_holds,
            window_start_ts_ms = EXCLUDED.window_start_ts_ms,
            window_end_ts_ms = EXCLUDED.window_end_ts_ms,
            pnl_net_usdt = EXCLUDED.pnl_net_usdt,
            side = EXCLUDED.side,
            reasoning_accuracy_0_1 = EXCLUDED.reasoning_accuracy_0_1,
            quality_label = EXCLUDED.quality_label,
            review_json = EXCLUDED.review_json,
            attribution_meta_json = EXCLUDED.attribution_meta_json,
            created_ts = now()
        RETURNING review_id
        """,
        pay,
    ).fetchone()
    return UUID(str(rid["review_id"]))


def fetch_recent_post_trade_reviews(
    conn: psycopg.Connection[Any], *, limit: int = 10
) -> list[dict[str, Any]]:
    lim = max(1, min(100, int(limit)))
    rows = conn.execute(
        """
        SELECT review_id, signal_id, execution_id, trade_evaluation_id,
               scenario_excerpt_de, reference_price, reference_role, thesis_holds,
               window_start_ts_ms, window_end_ts_ms, pnl_net_usdt, side,
               reasoning_accuracy_0_1, quality_label, review_json, attribution_meta_json, created_ts
        FROM learn.post_trade_review
        ORDER BY created_ts DESC
        LIMIT %s
        """,
        (lim,),
    ).fetchall()
    return [dict(r) for r in rows]
