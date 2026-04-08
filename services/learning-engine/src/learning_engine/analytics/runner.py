from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg

from learning_engine.analytics import error_patterns, recommendations, strategy_metrics
from learning_engine.config import LearningEngineSettings
from learning_engine.drift.adwin_detector import SimpleAdwin
from learning_engine.meta_models import train_expected_bps_models, train_take_trade_prob_model
from learning_engine.mlflow_tracking.tracker import log_learning_run
from learning_engine.storage import repo_learning_v1

logger = logging.getLogger("learning_engine.analytics")


def parse_windows(settings: LearningEngineSettings) -> list[str]:
    parts = [p.strip() for p in settings.learning_window_list.split(",")]
    out = [p for p in parts if p]
    for w in out:
        repo_learning_v1.window_to_ms(w)
    return out


def _series_for_adwin(rows: list[dict[str, Any]], metric: str) -> list[float]:
    ordered = sorted(rows, key=lambda r: int(r["closed_ts_ms"]))
    if metric == "pnl_net_usdt":
        return [float(Decimal(str(r.get("pnl_net_usdt", "0")))) for r in ordered]
    if metric == "win_rate":
        return [1.0 if bool(r.get("direction_correct")) else 0.0 for r in ordered]
    raise ValueError(metric)


def _adwin_insert_drifts(
    conn: psycopg.Connection[Any],
    *,
    values: list[float],
    metric_name: str,
    window: str,
    strategy_name: str | None,
    strategy_id: UUID | None,
) -> int:
    adwin = SimpleAdwin()
    prev_fire = False
    n = 0
    for i, v in enumerate(values):
        drift_now = adwin.update(v)
        rising = drift_now and not prev_fire
        prev_fire = drift_now
        if rising:
            repo_learning_v1.insert_drift_event(
                conn,
                metric_name=metric_name,
                severity="medium",
                details_json={
                    "window": window,
                    "strategy_name": strategy_name,
                    "strategy_id": str(strategy_id) if strategy_id else None,
                    "index": i,
                    "value": v,
                    "detector": "simple_adwin_v1",
                },
            )
            n += 1
    return n


def run_learning_analytics(conn: psycopg.Connection[Any], settings: LearningEngineSettings) -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    windows = parse_windows(settings)
    report: dict[str, Any] = {"windows": {}, "drift_events": 0, "recommendations": 0}
    rec_count = 0
    drift_total = 0

    for window in windows:
        wms = repo_learning_v1.window_to_ms(window)
        since = now_ms - wms
        rows = repo_learning_v1.fetch_evaluations_since_ms(conn, since_closed_ts_ms=since)

        repo_learning_v1.clear_error_patterns_for_window(conn, window=window)
        for p in error_patterns.aggregate_error_patterns(rows)[:50]:
            repo_learning_v1.insert_error_pattern(
                conn,
                window=window,
                pattern_key=p["pattern_key"],
                count=p["count"],
                examples_json=p["examples"],
            )

        strategies = repo_learning_v1.list_registry_strategies(conn)
        agg = strategy_metrics.compute_trade_metrics(rows)
        losing_conds = error_patterns.top_losing_conditions(rows, limit=10)

        win_block: dict[str, Any] = {
            "aggregate_metrics": agg,
            "strategies": [],
            "top_losing_conditions": losing_conds,
        }

        for st in strategies:
            sid = UUID(str(st["strategy_id"]))
            name = str(st["name"])
            srows = [r for r in rows if strategy_metrics.infer_strategy_name(r) == name]
            m = strategy_metrics.compute_trade_metrics(srows)
            repo_learning_v1.upsert_strategy_metrics(
                conn,
                strategy_id=sid,
                window=window,
                metrics_json={**m, "strategy_name": name, "window": window},
            )
            win_block["strategies"].append({"strategy_id": str(sid), "strategy_name": name, "metrics": m})

            for pr in recommendations.build_promotion_recommendations(
                str(sid), name, m, settings
            ):
                repo_learning_v1.insert_recommendation(
                    conn,
                    rec_type=pr["type"],
                    payload_json={**pr["payload"], "window": window},
                )
                rec_count += 1

            if settings.learning_enable_adwin and len(srows) >= 20:
                try:
                    vals = _series_for_adwin(srows, settings.learning_adwin_metric)
                    drift_total += _adwin_insert_drifts(
                        conn,
                        values=vals,
                        metric_name=f"{settings.learning_adwin_metric}@{name}",
                        window=window,
                        strategy_name=name,
                        strategy_id=sid,
                    )
                except Exception as exc:
                    logger.warning("adwin strategy=%s: %s", name, exc)

        for rec in recommendations.build_signal_and_risk_recommendations(rows, settings):
            repo_learning_v1.insert_recommendation(
                conn,
                rec_type=rec["type"],
                payload_json={**rec["payload"], "window": window},
            )
            rec_count += 1

        if settings.learning_enable_adwin and len(rows) >= 20:
            try:
                vals = _series_for_adwin(rows, settings.learning_adwin_metric)
                drift_total += _adwin_insert_drifts(
                    conn,
                    values=vals,
                    metric_name=f"{settings.learning_adwin_metric}@global",
                    window=window,
                    strategy_name=None,
                    strategy_id=None,
                )
            except Exception as exc:
                logger.warning("adwin global: %s", exc)

        report["windows"][window] = win_block

    report["drift_events"] = drift_total
    report["recommendations"] = rec_count
    try:
        report["take_trade_model"] = train_take_trade_prob_model(conn, settings)
    except Exception as exc:
        logger.warning("take_trade_model: %s", exc)
        report["take_trade_model"] = {"status": "skipped", "reason": str(exc)}
    try:
        report["expected_bps_models"] = train_expected_bps_models(conn, settings)
    except Exception as exc:
        logger.warning("expected_bps_models: %s", exc)
        report["expected_bps_models"] = {"status": "skipped", "reason": str(exc)}
    try:
        log_learning_run(settings, report)
    except Exception as exc:
        logger.warning("mlflow: %s", exc)
    if settings.online_drift_evaluate_on_analytics_run:
        try:
            from learning_engine.drift.online_evaluator import run_online_drift_evaluation

            report["online_drift"] = run_online_drift_evaluation(conn, settings)
        except Exception as exc:
            logger.warning("online_drift: %s", exc)
            report["online_drift"] = {"status": "skipped", "reason": str(exc)}
    return report
