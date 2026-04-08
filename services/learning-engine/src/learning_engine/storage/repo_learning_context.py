from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import psycopg

_ALLOWED_SOURCE_KINDS = frozenset(
    {
        "shadow",
        "paper",
        "post_trade_review",
        "operator_context",
        "live_outcome",
    }
)


def insert_learning_context_signal(
    conn: psycopg.Connection[Any],
    *,
    source_kind: str,
    reference_json: dict[str, Any],
    payload_redacted_json: dict[str, Any],
    policy_rewrite_forbidden: bool,
    curriculum_version: str,
) -> UUID:
    sk = (source_kind or "").strip().lower()
    if sk not in _ALLOWED_SOURCE_KINDS:
        raise ValueError(f"source_kind ungueltig: {source_kind!r}")
    if sk == "operator_context":
        policy_rewrite_forbidden = True
    row = conn.execute(
        """
        INSERT INTO learn.learning_context_signals (
            source_kind, reference_json, payload_redacted_json,
            policy_rewrite_forbidden, curriculum_version
        )
        VALUES (%s, %s::jsonb, %s::jsonb, %s, %s)
        RETURNING context_signal_id
        """,
        (
            sk,
            json.dumps(reference_json or {}, default=str),
            json.dumps(payload_redacted_json or {}, default=str),
            policy_rewrite_forbidden,
            (curriculum_version or "specialist-curriculum-v1").strip(),
        ),
    ).fetchone()
    if row is None:
        raise RuntimeError("insert_learning_context_signal: no row")
    return UUID(str(dict(row)["context_signal_id"]))


def fetch_recent_context_signals(
    conn: psycopg.Connection[Any],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT context_signal_id, source_kind, reference_json, payload_redacted_json,
               policy_rewrite_forbidden, curriculum_version, created_ts
        FROM learn.learning_context_signals
        ORDER BY created_ts DESC
        LIMIT %s
        """,
        (max(1, min(limit, 500)),),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["context_signal_id"] = str(d["context_signal_id"])
        if d.get("created_ts") is not None:
            d["created_ts"] = d["created_ts"].isoformat()
        out.append(d)
    return out
