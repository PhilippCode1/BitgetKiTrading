from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.base import clone
from sklearn.metrics import accuracy_score, log_loss, mean_absolute_error, roc_auc_score

from learning_engine.backtest.splits import (
    Range,
    purged_kfold_embargo_indices,
    walk_forward_indices,
)
from learning_engine.config import LearningEngineSettings
from learning_engine.training.cv_split_policy import (
    make_training_purged_kfold_splits,
    make_training_walk_forward_splits,
)


def _splits_walk_forward(
    ranges: list[Range],
    k_folds: int,
    embargo_pct: float,
    settings: LearningEngineSettings | None,
) -> list[tuple[list[int], list[int]]]:
    if settings is not None:
        return make_training_walk_forward_splits(ranges, settings)
    return walk_forward_indices(ranges, k_folds, embargo_pct)


def _splits_purged_kfold(
    ranges: list[Range],
    k_folds: int,
    embargo_pct: float,
    settings: LearningEngineSettings | None,
) -> list[tuple[list[int], list[int]]]:
    if settings is not None:
        return make_training_purged_kfold_splits(ranges, settings)
    return purged_kfold_embargo_indices(ranges, k_folds, embargo_pct)


@dataclass(frozen=True)
class FoldMetric:
    fold_index: int
    train_n: int
    test_n: int
    metrics: dict[str, Any]
    skipped_reason: str | None = None


def _binary_metrics(y_true: list[int], probs_pos: list[float]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "count": len(y_true),
        "positive_rate": float(sum(y_true)) / len(y_true) if y_true else 0.0,
    }
    try:
        out["roc_auc"] = float(roc_auc_score(y_true, probs_pos))
    except ValueError:
        out["roc_auc"] = None
    try:
        out["log_loss"] = float(log_loss(y_true, probs_pos, labels=[0, 1]))
    except ValueError:
        out["log_loss"] = None
    return out


def run_walk_forward_binary_classification(
    *,
    X: Sequence[Sequence[float]],
    y: Sequence[int],
    ranges: list[Range],
    k_folds: int,
    embargo_pct: float,
    make_estimator: Callable[[], Any],
    settings: LearningEngineSettings | None = None,
) -> list[FoldMetric]:
    splits = _splits_walk_forward(ranges, k_folds, embargo_pct, settings)
    return _eval_binary_folds(X, y, splits, make_estimator)


def run_purged_kfold_binary_classification(
    *,
    X: Sequence[Sequence[float]],
    y: Sequence[int],
    ranges: list[Range],
    k_folds: int,
    embargo_pct: float,
    make_estimator: Callable[[], Any],
    settings: LearningEngineSettings | None = None,
) -> list[FoldMetric]:
    splits = _splits_purged_kfold(ranges, k_folds, embargo_pct, settings)
    return _eval_binary_folds(X, y, splits, make_estimator)


def _eval_binary_folds(
    X: Sequence[Sequence[float]],
    y: Sequence[int],
    splits: list[tuple[list[int], list[int]]],
    make_estimator: Callable[[], Any],
) -> list[FoldMetric]:
    out: list[FoldMetric] = []
    for fi, (tr_idx, te_idx) in enumerate(splits):
        if not te_idx:
            continue
        y_tr = [y[i] for i in tr_idx]
        y_te = [y[i] for i in te_idx]
        if len(set(y_tr)) < 2:
            out.append(
                FoldMetric(
                    fold_index=fi,
                    train_n=len(tr_idx),
                    test_n=len(te_idx),
                    metrics={},
                    skipped_reason="train_single_class",
                )
            )
            continue
        if len(set(y_te)) < 2:
            out.append(
                FoldMetric(
                    fold_index=fi,
                    train_n=len(tr_idx),
                    test_n=len(te_idx),
                    metrics={},
                    skipped_reason="test_single_class",
                )
            )
            continue
        est = clone(make_estimator())
        X_tr = [list(X[i]) for i in tr_idx]
        X_te = [list(X[i]) for i in te_idx]
        est.fit(X_tr, y_tr)
        prob_rows = est.predict_proba(X_te)
        probs_pos = [float(row[1]) for row in prob_rows]
        metrics = _binary_metrics(list(y_te), probs_pos)
        out.append(
            FoldMetric(
                fold_index=fi,
                train_n=len(tr_idx),
                test_n=len(te_idx),
                metrics=metrics,
            )
        )
    return out


def run_walk_forward_regression(
    *,
    X: Sequence[Sequence[float]],
    y: Sequence[float],
    ranges: list[Range],
    k_folds: int,
    embargo_pct: float,
    make_estimator: Callable[[], Any],
    settings: LearningEngineSettings | None = None,
) -> list[FoldMetric]:
    splits = _splits_walk_forward(ranges, k_folds, embargo_pct, settings)
    return _eval_regression_folds(X, y, splits, make_estimator)


def run_purged_kfold_regression(
    *,
    X: Sequence[Sequence[float]],
    y: Sequence[float],
    ranges: list[Range],
    k_folds: int,
    embargo_pct: float,
    make_estimator: Callable[[], Any],
    settings: LearningEngineSettings | None = None,
) -> list[FoldMetric]:
    splits = _splits_purged_kfold(ranges, k_folds, embargo_pct, settings)
    return _eval_regression_folds(X, y, splits, make_estimator)


def _eval_regression_folds(
    X: Sequence[Sequence[float]],
    y: Sequence[float],
    splits: list[tuple[list[int], list[int]]],
    make_estimator: Callable[[], Any],
) -> list[FoldMetric]:
    out: list[FoldMetric] = []
    for fi, (tr_idx, te_idx) in enumerate(splits):
        if not te_idx or not tr_idx:
            out.append(
                FoldMetric(
                    fold_index=fi,
                    train_n=len(tr_idx),
                    test_n=len(te_idx),
                    metrics={},
                    skipped_reason="empty_train_or_test",
                )
            )
            continue
        est = clone(make_estimator())
        X_tr = [list(X[i]) for i in tr_idx]
        X_te = [list(X[i]) for i in te_idx]
        y_tr = [float(y[i]) for i in tr_idx]
        y_te = [float(y[i]) for i in te_idx]
        est.fit(X_tr, y_tr)
        pred = [float(p) for p in est.predict(X_te)]
        mae = float(mean_absolute_error(y_te, pred))
        out.append(
            FoldMetric(
                fold_index=fi,
                train_n=len(tr_idx),
                test_n=len(te_idx),
                metrics={"mae_bps": mae, "count": len(y_te)},
            )
        )
    return out


def run_walk_forward_multiclass_classification(
    *,
    X: Sequence[Sequence[float]],
    y: Sequence[int],
    ranges: list[Range],
    k_folds: int,
    embargo_pct: float,
    make_estimator: Callable[[], Any],
    settings: LearningEngineSettings | None = None,
) -> list[FoldMetric]:
    splits = _splits_walk_forward(ranges, k_folds, embargo_pct, settings)
    return _eval_multiclass_folds(X, y, splits, make_estimator)


def run_purged_kfold_multiclass_classification(
    *,
    X: Sequence[Sequence[float]],
    y: Sequence[int],
    ranges: list[Range],
    k_folds: int,
    embargo_pct: float,
    make_estimator: Callable[[], Any],
    settings: LearningEngineSettings | None = None,
) -> list[FoldMetric]:
    splits = _splits_purged_kfold(ranges, k_folds, embargo_pct, settings)
    return _eval_multiclass_folds(X, y, splits, make_estimator)


def _eval_multiclass_folds(
    X: Sequence[Sequence[float]],
    y: Sequence[int],
    splits: list[tuple[list[int], list[int]]],
    make_estimator: Callable[[], Any],
) -> list[FoldMetric]:
    out: list[FoldMetric] = []
    for fi, (tr_idx, te_idx) in enumerate(splits):
        if not te_idx or not tr_idx:
            out.append(
                FoldMetric(
                    fold_index=fi,
                    train_n=len(tr_idx),
                    test_n=len(te_idx),
                    metrics={},
                    skipped_reason="empty_train_or_test",
                )
            )
            continue
        y_tr = [y[i] for i in tr_idx]
        present_tr = set(y_tr)
        if len(present_tr) < 2:
            out.append(
                FoldMetric(
                    fold_index=fi,
                    train_n=len(tr_idx),
                    test_n=len(te_idx),
                    metrics={},
                    skipped_reason="train_single_class",
                )
            )
            continue
        est = clone(make_estimator())
        X_tr = [list(X[i]) for i in tr_idx]
        X_te = [list(X[i]) for i in te_idx]
        y_te = [y[i] for i in te_idx]
        est.fit(X_tr, y_tr)
        prob = est.predict_proba(X_te)
        pred_idx = np.argmax(prob, axis=1)
        y_pred = [int(pred_idx[i]) for i in range(len(pred_idx))]
        metrics: dict[str, Any] = {
            "accuracy": float(accuracy_score(y_te, y_pred)),
            "count": len(y_te),
        }
        try:
            metrics["log_loss"] = float(log_loss(y_te, prob, labels=list(est.classes_)))
        except ValueError:
            metrics["log_loss"] = None
        out.append(
            FoldMetric(
                fold_index=fi,
                train_n=len(tr_idx),
                test_n=len(te_idx),
                metrics=metrics,
            )
        )
    return out


def folds_to_jsonable(folds: list[FoldMetric]) -> list[dict[str, Any]]:
    return [
        {
            "fold_index": f.fold_index,
            "train_n": f.train_n,
            "test_n": f.test_n,
            "metrics": f.metrics,
            "skipped_reason": f.skipped_reason,
        }
        for f in folds
    ]


def mean_fold_metric(folds: list[FoldMetric], key: str) -> float | None:
    vals: list[float] = []
    for f in folds:
        if f.skipped_reason:
            continue
        v = f.metrics.get(key)
        if v is None:
            continue
        vals.append(float(v))
    if not vals:
        return None
    return float(sum(vals) / len(vals))
