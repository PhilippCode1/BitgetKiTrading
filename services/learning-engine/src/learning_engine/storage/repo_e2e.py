from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import psycopg

from learning_engine.e2e.qc import operator_override_from_meta
from learning_engine.e2e.snapshot import (
    E2E_RECORD_SCHEMA_VERSION,
    build_e2e_snapshot_from_signal_row,
    initial_outcomes_json,
)


def _j(d: Any) -> str:
    return json.dumps(d, separators=(",", ":"), ensure_ascii=False, default=str)


def upsert_decision_record_from_signal(conn: psycopg.Connection[Any], signal_row: dict[str, Any]) -> UUID:
    sid = UUID(str(signal_row["signal_id"]))
    snap = build_e2e_snapshot_from_signal_row(signal_row)
    outcomes = initial_outcomes_json(signal_row)
    decision_ts = int(signal_row.get("analysis_ts_ms") or 0)
    conn.execute(
        """
        INSERT INTO learn.e2e_decision_records (
            signal_id, schema_version, decision_ts_ms,
            canonical_instrument_id, symbol, timeframe, market_family,
            playbook_id, playbook_family, regime_label, meta_trade_lane, trade_action,
            snapshot_json, outcomes_json, label_qc_json, operator_mirror_actions_json
        ) VALUES (
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s::jsonb, %s::jsonb, '{}'::jsonb, '[]'::jsonb
        )
        ON CONFLICT (signal_id) DO UPDATE SET
            schema_version = EXCLUDED.schema_version,
            decision_ts_ms = EXCLUDED.decision_ts_ms,
            canonical_instrument_id = EXCLUDED.canonical_instrument_id,
            symbol = EXCLUDED.symbol,
            timeframe = EXCLUDED.timeframe,
            market_family = EXCLUDED.market_family,
            playbook_id = EXCLUDED.playbook_id,
            playbook_family = EXCLUDED.playbook_family,
            regime_label = EXCLUDED.regime_label,
            meta_trade_lane = EXCLUDED.meta_trade_lane,
            trade_action = EXCLUDED.trade_action,
            snapshot_json = EXCLUDED.snapshot_json,
            updated_ts = now()
        """,
        (
            str(sid),
            E2E_RECORD_SCHEMA_VERSION,
            decision_ts,
            signal_row.get("canonical_instrument_id"),
            str(signal_row["symbol"]),
            str(signal_row["timeframe"]),
            str(signal_row.get("market_family") or "unknown"),
            signal_row.get("playbook_id"),
            signal_row.get("playbook_family"),
            signal_row.get("market_regime"),
            signal_row.get("meta_trade_lane"),
            signal_row.get("trade_action"),
            _j(snap),
            _j(outcomes),
        ),
    )
    row = conn.execute(
        "SELECT record_id FROM learn.e2e_decision_records WHERE signal_id = %s",
        (str(sid),),
    ).fetchone()
    return UUID(str(row["record_id"])) if row else sid


def merge_paper_trade_opened(
    conn: psycopg.Connection[Any],
    *,
    signal_id: UUID,
    paper_trade_id: UUID,
    opened_ts_ms: int,
    side: str,
) -> None:
    patch = {
        "paper": {
            "lane": "paper",
            "phase": "open",
            "paper_trade_id": str(paper_trade_id),
            "opened_ts_ms": opened_ts_ms,
            "side": side,
        }
    }
    conn.execute(
        """
        UPDATE learn.e2e_decision_records
        SET paper_trade_id = %s,
            outcomes_json = outcomes_json || %s::jsonb,
            updated_ts = now()
        WHERE signal_id = %s
        """,
        (str(paper_trade_id), _j(patch), str(signal_id)),
    )


def merge_paper_trade_closed(
    conn: psycopg.Connection[Any],
    *,
    signal_id: UUID,
    paper_trade_id: UUID,
    evaluation_id: UUID,
    outcome_paper: dict[str, Any],
    label_qc_patch: dict[str, Any],
    operator_meta: dict[str, Any] | None,
) -> None:
    op_append = "[]"
    if operator_meta:
        hint = operator_override_from_meta(operator_meta)
        if hint:
            op_append = _j([hint])

    outcome_paper_full = dict(outcome_paper)
    outcome_paper_full["phase"] = "closed"
    outcome_paper_full["evaluation_id"] = str(evaluation_id)
    patch = {"paper": outcome_paper_full}

    conn.execute(
        """
        UPDATE learn.e2e_decision_records
        SET paper_trade_id = COALESCE(paper_trade_id, %s),
            trade_evaluation_id = %s,
            outcomes_json = outcomes_json || %s::jsonb,
            label_qc_json = label_qc_json || %s::jsonb,
            operator_mirror_actions_json =
                COALESCE(operator_mirror_actions_json, '[]'::jsonb) || %s::jsonb,
            updated_ts = now()
        WHERE signal_id = %s
        """,
        (
            str(paper_trade_id),
            str(evaluation_id),
            _j(patch),
            _j(label_qc_patch),
            op_append,
            str(signal_id),
        ),
    )


def ensure_record_from_signal_if_missing(
    conn: psycopg.Connection[Any], signal_row: dict[str, Any] | None
) -> None:
    if not signal_row:
        return
    sid = signal_row.get("signal_id")
    if not sid:
        return
    row = conn.execute(
        "SELECT 1 FROM learn.e2e_decision_records WHERE signal_id = %s",
        (str(sid),),
    ).fetchone()
    if row:
        return
    upsert_decision_record_from_signal(conn, signal_row)


def fetch_e2e_records_benchmark_sample(
    conn: psycopg.Connection[Any],
    *,
    symbol: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    """E2E-Zeilen fuer Lane-/Counterfactual-Auswertung (neueste zuerst)."""
    lim = max(1, min(int(limit), 20_000))
    if symbol:
        rows = conn.execute(
            """
            SELECT record_id, signal_id, decision_ts_ms, symbol, snapshot_json, outcomes_json,
                   label_qc_json, meta_trade_lane, trade_action
            FROM learn.e2e_decision_records
            WHERE symbol = %s
            ORDER BY decision_ts_ms DESC
            LIMIT %s
            """,
            (symbol.upper(), lim),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT record_id, signal_id, decision_ts_ms, symbol, snapshot_json, outcomes_json,
                   label_qc_json, meta_trade_lane, trade_action
            FROM learn.e2e_decision_records
            ORDER BY decision_ts_ms DESC
            LIMIT %s
            """,
            (lim,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_recent_e2e(conn: psycopg.Connection[Any], *, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT record_id, signal_id, schema_version, decision_ts_ms,
               canonical_instrument_id, symbol, timeframe, market_family,
               playbook_id, playbook_family, regime_label, meta_trade_lane, trade_action,
               paper_trade_id, trade_evaluation_id,
               snapshot_json, outcomes_json, label_qc_json, operator_mirror_actions_json,
               created_ts, updated_ts
        FROM learn.e2e_decision_records
        ORDER BY decision_ts_ms DESC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]
