from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg

from learning_engine.backtest import metrics as bt_metrics
from learning_engine.backtest.splits import (
    Range,
    purged_kfold_embargo_indices,
    range_bounds_for_indices,
    walk_forward_indices,
)
from learning_engine.backtest.determinism_manifest import build_offline_backtest_manifest
from learning_engine.config import LearningEngineSettings
from learning_engine.storage import repo_backtest
from shared_py.replay_determinism import normalized_timeframes, stable_offline_backtest_run_id

logger = logging.getLogger("learning_engine.backtest.offline")


def _artifact_dir(base: Path, run_id: UUID) -> Path:
    d = base / str(run_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_reports(
    out_dir: Path,
    *,
    run: dict[str, Any],
    folds: list[dict[str, Any]],
) -> None:
    report = {"run": run, "folds": folds}
    (out_dir / "report.json").write_text(
        json.dumps(report, indent=2, default=str),
        encoding="utf-8",
    )
    lines = [
        f"# Backtest {run.get('run_id')}",
        "",
        f"- Symbol: {run.get('symbol')}",
        f"- Zeitraum: {run.get('from_ts_ms')} .. {run.get('to_ts_ms')}",
        f"- CV: {run.get('cv_method')}",
        f"- Status: {run.get('status')}",
        "",
        "## Aggregat-Metriken",
        "",
        "```json",
        json.dumps(run.get("metrics_json", {}), indent=2, default=str),
        "```",
        "",
        "## Folds",
        "",
    ]
    for f in folds:
        lines.append(f"### Fold {f.get('fold_index')}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(f.get("metrics_json", {}), indent=2, default=str))
        lines.append("```")
        lines.append("")
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def run_offline_backtest(
    conn: psycopg.Connection[Any],
    settings: LearningEngineSettings,
    *,
    symbol: str,
    from_ts_ms: int,
    to_ts_ms: int,
    cv_method: str,
    timeframes: list[str] | None = None,
    run_id: UUID | None = None,
    ephemeral_run: bool = False,
) -> UUID:
    if from_ts_ms >= to_ts_ms:
        raise ValueError("from_ts_ms muss kleiner als to_ts_ms sein")
    if cv_method not in ("walk_forward", "purged_kfold_embargo"):
        raise ValueError("cv_method ungueltig")
    tfs = normalized_timeframes(timeframes or ["5m"])
    random.seed(settings.train_random_state)
    k = settings.backtest_kfolds
    embargo = settings.backtest_purged_embargo_pct
    if run_id is not None:
        rid = run_id
    elif ephemeral_run:
        rid = uuid4()
    else:
        rid = stable_offline_backtest_run_id(
            symbol=symbol,
            timeframes=tfs,
            from_ts_ms=from_ts_ms,
            to_ts_ms=to_ts_ms,
            cv_method=cv_method,
            k_folds=k,
            embargo_pct=embargo,
            random_seed=settings.train_random_state,
        )
    manifest = build_offline_backtest_manifest(
        settings, cv_method=cv_method, k_folds=k, embargo_pct=embargo
    )
    params = {
        "k_folds": k,
        "embargo_pct": embargo,
        "cv_method": cv_method,
        "determinism_manifest": manifest,
    }
    base_artifact = Path(settings.backtest_artifacts_dir)
    if not base_artifact.is_absolute():
        # .../repo/services/learning-engine/src/learning_engine/backtest/runner_offline.py
        root = Path(__file__).resolve().parents[5]
        base_artifact = root / base_artifact
    out_dir = _artifact_dir(base_artifact, rid)

    repo_backtest.insert_backtest_run(
        conn,
        run_id=rid,
        symbol=symbol.upper(),
        timeframes_json=tfs,
        mode="offline",
        from_ts_ms=from_ts_ms,
        to_ts_ms=to_ts_ms,
        cv_method=cv_method,
        params_json=params,
        metrics_json={},
        status="running",
    )
    repo_backtest.delete_backtest_folds_for_run(conn, run_id=rid)

    try:
        evals = repo_backtest.fetch_trade_evaluations_window(
            conn, symbol=symbol, from_ts_ms=from_ts_ms, to_ts_ms=to_ts_ms
        )
        ranges = [
            Range(int(e.get("decision_ts_ms") or e["opened_ts_ms"]), int(e["closed_ts_ms"]))
            for e in evals
        ]
        if cv_method == "purged_kfold_embargo":
            idx_splits = purged_kfold_embargo_indices(ranges, k, embargo)
        else:
            idx_splits = walk_forward_indices(ranges, k, embargo)

        fold_rows: list[dict[str, Any]] = []
        for fi, (train_idx, test_idx) in enumerate(idx_splits):
            test_evals = [evals[j] for j in test_idx]
            train_evals = [evals[j] for j in train_idx]
            tm = bt_metrics.backtest_aggregate_metrics(test_evals)
            trm = bt_metrics.backtest_aggregate_metrics(train_evals)
            train_bounds = range_bounds_for_indices(ranges, train_idx)
            test_bounds = range_bounds_for_indices(ranges, test_idx)
            fold_metrics = {
                "test": tm,
                "train": trm,
                "n_train": len(train_idx),
                "n_test": len(test_idx),
            }
            repo_backtest.insert_backtest_fold(
                conn,
                run_id=rid,
                fold_index=fi,
                train_range_json=train_bounds,
                test_range_json=test_bounds,
                metrics_json=fold_metrics,
            )
            fold_rows.append(
                {
                    "fold_index": fi,
                    "train_range_json": train_bounds,
                    "test_range_json": test_bounds,
                    "metrics_json": fold_metrics,
                }
            )

        agg = bt_metrics.backtest_aggregate_metrics(evals)
        repo_backtest.update_backtest_run(
            conn, run_id=rid, metrics_json=agg, status="completed"
        )
        run_row = {
            "run_id": str(rid),
            "symbol": symbol.upper(),
            "timeframes_json": tfs,
            "mode": "offline",
            "from_ts_ms": from_ts_ms,
            "to_ts_ms": to_ts_ms,
            "cv_method": cv_method,
            "params_json": params,
            "metrics_json": agg,
            "status": "completed",
        }
        _write_reports(out_dir, run=run_row, folds=fold_rows)
    except Exception as exc:
        logger.exception("backtest failed")
        repo_backtest.update_backtest_run(
            conn,
            run_id=rid,
            metrics_json={"error": str(exc)},
            status="failed",
        )
        raise
    return rid
