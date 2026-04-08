"""Postgres-Zugriff: app.ai_strategy_proposal_draft."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json


def insert_proposal_draft(
    conn: psycopg.Connection[Any],
    *,
    operator_actor: str,
    signal_id: str | None,
    symbol: str,
    timeframe: str,
    proposal_payload: dict[str, Any],
) -> UUID:
    row = conn.execute(
        """
        INSERT INTO app.ai_strategy_proposal_draft (
            operator_actor, signal_id, symbol, timeframe,
            lifecycle_status, proposal_payload_jsonb
        )
        VALUES (%(actor)s, %(signal_id)s, %(symbol)s, %(timeframe)s, 'draft', %(payload)s)
        RETURNING draft_id
        """,
        {
            "actor": operator_actor[:256],
            "signal_id": signal_id[:128] if signal_id else None,
            "symbol": symbol[:64],
            "timeframe": timeframe[:32],
            "payload": Json(proposal_payload),
        },
    ).fetchone()
    if row is None:
        raise RuntimeError("insert_proposal_draft: no draft_id returned")
    return row["draft_id"]


def fetch_draft(conn: psycopg.Connection[Any], draft_id: UUID) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT draft_id, created_ts, operator_actor, signal_id, symbol, timeframe,
               lifecycle_status, proposal_payload_jsonb, validation_report_jsonb,
               promotion_target_requested, human_promotion_ack, human_promotion_ack_ts
        FROM app.ai_strategy_proposal_draft
        WHERE draft_id = %(id)s
        """,
        {"id": draft_id},
    ).fetchone()


def list_drafts_for_signal(
    conn: psycopg.Connection[Any],
    *,
    signal_id: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    lim = max(1, min(limit, 50))
    if signal_id:
        rows = conn.execute(
            """
            SELECT draft_id, created_ts, signal_id, symbol, timeframe, lifecycle_status,
                   promotion_target_requested, human_promotion_ack
            FROM app.ai_strategy_proposal_draft
            WHERE signal_id = %(sid)s
            ORDER BY created_ts DESC
            LIMIT %(lim)s
            """,
            {"sid": signal_id[:128], "lim": lim},
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT draft_id, created_ts, signal_id, symbol, timeframe, lifecycle_status,
                   promotion_target_requested, human_promotion_ack
            FROM app.ai_strategy_proposal_draft
            ORDER BY created_ts DESC
            LIMIT %(lim)s
            """,
            {"lim": lim},
        ).fetchall()
    return [dict(r) for r in rows]


def update_validation(
    conn: psycopg.Connection[Any],
    *,
    draft_id: UUID,
    passed: bool,
    report: dict[str, Any],
) -> None:
    status = "validation_passed" if passed else "validation_failed"
    conn.execute(
        """
        UPDATE app.ai_strategy_proposal_draft
        SET lifecycle_status = %(st)s,
            validation_report_jsonb = %(rep)s
        WHERE draft_id = %(id)s
        """,
        {"st": status, "rep": Json(report), "id": draft_id},
    )


def update_promotion_request(
    conn: psycopg.Connection[Any],
    *,
    draft_id: UUID,
    promotion_target: str,
) -> None:
    conn.execute(
        """
        UPDATE app.ai_strategy_proposal_draft
        SET lifecycle_status = 'promotion_requested',
            promotion_target_requested = %(pt)s,
            human_promotion_ack = true,
            human_promotion_ack_ts = now()
        WHERE draft_id = %(id)s
        """,
        {"pt": promotion_target, "id": draft_id},
    )


def connect_drafts() -> psycopg.Connection[Any]:
    from api_gateway.db import get_database_url

    return psycopg.connect(get_database_url(), row_factory=dict_row, connect_timeout=8)
