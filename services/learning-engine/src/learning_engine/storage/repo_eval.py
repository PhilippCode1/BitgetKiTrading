from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg


def upsert_trade_evaluation(conn: psycopg.Connection[Any], row: dict[str, Any]) -> UUID:
    """ON CONFLICT paper_trade_id UPDATE — idempotent."""
    pid = UUID(str(row["paper_trade_id"]))

    def j(d: Any) -> str:
        if d is None:
            return "{}"
        return json.dumps(d, separators=(",", ":"), ensure_ascii=False, default=str)

    def ja(d: Any) -> str:
        if d is None:
            return "[]"
        return json.dumps(d, separators=(",", ":"), ensure_ascii=False, default=str)

    conn.execute(
        """
        INSERT INTO learn.trade_evaluations (
            paper_trade_id, signal_id, symbol, timeframe,
            decision_ts_ms, opened_ts_ms, closed_ts_ms, side, qty_base,
            entry_price_avg, exit_price_avg,
            pnl_gross_usdt, fees_total_usdt, funding_total_usdt, pnl_net_usdt,
            direction_correct, stop_hit, tp1_hit, tp2_hit, tp3_hit,
            time_to_tp1_ms, time_to_stop_ms,
            stop_quality_score, stop_distance_atr_mult,
            slippage_bps_entry, slippage_bps_exit,
            market_regime,
            take_trade_label, expected_return_bps, expected_return_gross_bps,
            expected_mae_bps, expected_mfe_bps,
            liquidation_proximity_bps, liquidation_risk,
            news_context_json, signal_snapshot_json, feature_snapshot_json,
            structure_snapshot_json, error_labels_json, model_contract_json
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s,
            %s, %s,
            %s, %s,
            %s,
            %s, %s, %s,
            %s, %s,
            %s, %s,
            %s::jsonb, %s::jsonb, %s::jsonb,
            %s::jsonb, %s::jsonb, %s::jsonb
        )
        ON CONFLICT (paper_trade_id) DO UPDATE SET
            signal_id = EXCLUDED.signal_id,
            symbol = EXCLUDED.symbol,
            timeframe = EXCLUDED.timeframe,
            decision_ts_ms = EXCLUDED.decision_ts_ms,
            closed_ts_ms = EXCLUDED.closed_ts_ms,
            exit_price_avg = EXCLUDED.exit_price_avg,
            pnl_gross_usdt = EXCLUDED.pnl_gross_usdt,
            fees_total_usdt = EXCLUDED.fees_total_usdt,
            funding_total_usdt = EXCLUDED.funding_total_usdt,
            pnl_net_usdt = EXCLUDED.pnl_net_usdt,
            direction_correct = EXCLUDED.direction_correct,
            stop_hit = EXCLUDED.stop_hit,
            tp1_hit = EXCLUDED.tp1_hit,
            tp2_hit = EXCLUDED.tp2_hit,
            tp3_hit = EXCLUDED.tp3_hit,
            time_to_tp1_ms = EXCLUDED.time_to_tp1_ms,
            time_to_stop_ms = EXCLUDED.time_to_stop_ms,
            stop_quality_score = EXCLUDED.stop_quality_score,
            stop_distance_atr_mult = EXCLUDED.stop_distance_atr_mult,
            slippage_bps_entry = EXCLUDED.slippage_bps_entry,
            slippage_bps_exit = EXCLUDED.slippage_bps_exit,
            market_regime = EXCLUDED.market_regime,
            take_trade_label = EXCLUDED.take_trade_label,
            expected_return_bps = EXCLUDED.expected_return_bps,
            expected_return_gross_bps = EXCLUDED.expected_return_gross_bps,
            expected_mae_bps = EXCLUDED.expected_mae_bps,
            expected_mfe_bps = EXCLUDED.expected_mfe_bps,
            liquidation_proximity_bps = EXCLUDED.liquidation_proximity_bps,
            liquidation_risk = EXCLUDED.liquidation_risk,
            news_context_json = EXCLUDED.news_context_json,
            signal_snapshot_json = EXCLUDED.signal_snapshot_json,
            feature_snapshot_json = EXCLUDED.feature_snapshot_json,
            structure_snapshot_json = EXCLUDED.structure_snapshot_json,
            error_labels_json = EXCLUDED.error_labels_json,
            model_contract_json = EXCLUDED.model_contract_json,
            created_ts = now()
        """,
        (
            str(pid),
            str(row["signal_id"]) if row.get("signal_id") else None,
            row["symbol"],
            row["timeframe"],
            int(row.get("decision_ts_ms") or row["opened_ts_ms"]),
            int(row["opened_ts_ms"]),
            int(row["closed_ts_ms"]),
            row["side"],
            str(row["qty_base"]),
            str(row["entry_price_avg"]),
            str(row["exit_price_avg"]) if row.get("exit_price_avg") is not None else None,
            str(row["pnl_gross_usdt"]),
            str(row["fees_total_usdt"]),
            str(row["funding_total_usdt"]),
            str(row["pnl_net_usdt"]),
            bool(row["direction_correct"]),
            bool(row["stop_hit"]),
            bool(row["tp1_hit"]),
            bool(row["tp2_hit"]),
            bool(row["tp3_hit"]),
            row.get("time_to_tp1_ms"),
            row.get("time_to_stop_ms"),
            row.get("stop_quality_score"),
            str(row["stop_distance_atr_mult"]) if row.get("stop_distance_atr_mult") is not None else None,
            str(row["slippage_bps_entry"]) if row.get("slippage_bps_entry") is not None else None,
            str(row["slippage_bps_exit"]) if row.get("slippage_bps_exit") is not None else None,
            row.get("market_regime"),
            bool(row["take_trade_label"]) if row.get("take_trade_label") is not None else None,
            str(row["expected_return_bps"]) if row.get("expected_return_bps") is not None else None,
            str(row["expected_return_gross_bps"]) if row.get("expected_return_gross_bps") is not None else None,
            str(row["expected_mae_bps"]) if row.get("expected_mae_bps") is not None else None,
            str(row["expected_mfe_bps"]) if row.get("expected_mfe_bps") is not None else None,
            str(row["liquidation_proximity_bps"]) if row.get("liquidation_proximity_bps") is not None else None,
            bool(row["liquidation_risk"]) if row.get("liquidation_risk") is not None else None,
            ja(row.get("news_context_json")),
            j(row.get("signal_snapshot_json")),
            j(row.get("feature_snapshot_json")),
            j(row.get("structure_snapshot_json")),
            ja(row.get("error_labels_json")),
            j(row.get("model_contract_json")),
        ),
    )
    out = conn.execute(
        "SELECT evaluation_id FROM learn.trade_evaluations WHERE paper_trade_id = %s",
        (str(pid),),
    ).fetchone()
    return UUID(str(out["evaluation_id"])) if out else pid


def list_recent_evaluations(conn: psycopg.Connection[Any], *, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM learn.trade_evaluations
        ORDER BY created_ts DESC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_evaluation_by_trade_id(
    conn: psycopg.Connection[Any], paper_trade_id: UUID
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM learn.trade_evaluations WHERE paper_trade_id = %s",
        (str(paper_trade_id),),
    ).fetchone()
    return dict(row) if row else None


def summary_window(conn: psycopg.Connection[Any], *, window_days: int) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
            COUNT(*)::bigint AS n,
            COALESCE(SUM(CASE WHEN direction_correct THEN 1 ELSE 0 END), 0)::bigint AS wins,
            COALESCE(AVG(pnl_net_usdt), 0) AS avg_pnl_net,
            COALESCE(SUM(pnl_net_usdt), 0) AS sum_pnl_net
        FROM learn.trade_evaluations
        WHERE created_ts >= timezone('utc', now()) - CAST(%s AS interval)
        """,
        (f"{int(window_days)} days",),
    ).fetchone()
    if not row:
        return {"count": 0, "wins": 0, "avg_pnl_net": Decimal("0"), "sum_pnl_net": Decimal("0")}
    n = int(row["n"])
    wins = int(row["wins"])
    return {
        "count": n,
        "wins": wins,
        "losses": n - wins,
        "win_rate": float(wins) / n if n else 0.0,
        "avg_pnl_net": row["avg_pnl_net"],
        "sum_pnl_net": row["sum_pnl_net"],
    }


def upsert_signal_outcome(
    conn: psycopg.Connection[Any],
    *,
    signal_id: UUID,
    direction_correct: bool,
) -> None:
    conn.execute(
        """
        INSERT INTO learn.signal_outcomes (signal_id, evaluations_count, wins, losses, updated_ts)
        VALUES (%s, 1, %s, %s, now())
        ON CONFLICT (signal_id) DO UPDATE SET
            evaluations_count = learn.signal_outcomes.evaluations_count + 1,
            wins = learn.signal_outcomes.wins + EXCLUDED.wins,
            losses = learn.signal_outcomes.losses + EXCLUDED.losses,
            updated_ts = now()
        """,
        (
            str(signal_id),
            1 if direction_correct else 0,
            0 if direction_correct else 1,
        ),
    )
