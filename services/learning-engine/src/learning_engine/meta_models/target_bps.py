from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import numpy as np
import psycopg
from joblib import dump
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, median_absolute_error, r2_score

from learning_engine.config import LearningEngineSettings
from learning_engine.storage import repo_model_runs
from learning_engine.training.cv_leakage_family import build_cv_report_with_leakage_family_audit
from learning_engine.training.cv_runner import (
    mean_fold_metric,
    run_purged_kfold_regression,
    run_walk_forward_regression,
)
from learning_engine.training.data_version import compute_data_version_hash
from learning_engine.training.example_ranges import label_ranges_for_examples
from learning_engine.training.manifest import build_training_manifest
from learning_engine.training.run_manifest import write_full_run_manifest
from shared_py.model_contracts import MODEL_TARGET_SCHEMA_HASH, stable_json_hash
from shared_py.training_dataset_builder import training_row_metadata
from shared_py.take_trade_model import (
    BPS_REGRESSION_MODEL_KIND,
    EXPECTED_MAE_BPS_MODEL_NAME,
    EXPECTED_MFE_BPS_MODEL_NAME,
    EXPECTED_RETURN_BPS_MODEL_NAME,
    SIGNAL_MODEL_FEATURE_FIELDS,
    BoundedRegressionModel,
    build_signal_model_feature_reference,
    build_signal_model_feature_vector_from_evaluation,
    signal_model_feature_contract_descriptor,
)

_MIN_TEST_ROWS = 16


@dataclass(frozen=True)
class BpsRegressionSpec:
    model_name: str
    target_field: str
    output_field: str
    scaling_method: str
    nonnegative: bool
    lower_quantile: float
    upper_quantile: float


_BPS_REGRESSION_SPECS = (
    BpsRegressionSpec(
        model_name=EXPECTED_RETURN_BPS_MODEL_NAME,
        target_field="expected_return_bps",
        output_field="expected_return_bps",
        scaling_method="asinh_clip",
        nonnegative=False,
        lower_quantile=0.005,
        upper_quantile=0.995,
    ),
    BpsRegressionSpec(
        model_name=EXPECTED_MAE_BPS_MODEL_NAME,
        target_field="expected_mae_bps",
        output_field="expected_mae_bps",
        scaling_method="log1p_clip",
        nonnegative=True,
        lower_quantile=0.0,
        upper_quantile=0.995,
    ),
    BpsRegressionSpec(
        model_name=EXPECTED_MFE_BPS_MODEL_NAME,
        target_field="expected_mfe_bps",
        output_field="expected_mfe_bps",
        scaling_method="log1p_clip",
        nonnegative=True,
        lower_quantile=0.0,
        upper_quantile=0.995,
    ),
)


def train_expected_bps_models(
    conn: psycopg.Connection[Any],
    settings: LearningEngineSettings,
    *,
    symbol: str | None = None,
    promote: bool = True,
) -> dict[str, Any]:
    reports: dict[str, Any] = {}
    for spec in _BPS_REGRESSION_SPECS:
        reports[spec.output_field] = train_expected_bps_model(
            conn,
            settings,
            spec=spec,
            symbol=symbol,
            promote=promote,
        )
    return {"models": reports}


def train_expected_bps_model(
    conn: psycopg.Connection[Any],
    settings: LearningEngineSettings,
    *,
    spec: BpsRegressionSpec,
    symbol: str | None = None,
    promote: bool = True,
) -> dict[str, Any]:
    rows = repo_model_runs.fetch_target_training_rows(conn, target_field=spec.target_field, symbol=symbol)
    examples = [_example_from_row(row, target_field=spec.target_field) for row in rows]
    examples = [example for example in examples if example is not None]
    if len(examples) < settings.expected_bps_model_min_rows:
        raise ValueError(
            f"zu wenige Evaluations fuer {spec.output_field} "
            f"({len(examples)} < {settings.expected_bps_model_min_rows})"
        )

    examples.sort(key=lambda item: item["decision_ts_ms"])
    ranges = label_ranges_for_examples(examples)
    X_full, y_full_list = _matrix_and_target(examples)
    y_full = [float(v) for v in y_full_list]
    k_cv = settings.train_cv_kfolds
    emb = settings.train_cv_embargo_pct
    rs = settings.train_random_state
    make_est = lambda: _build_regressor(spec.scaling_method, random_state=rs)
    cv_wf = run_walk_forward_regression(
        X=X_full,
        y=y_full,
        ranges=ranges,
        k_folds=k_cv,
        embargo_pct=emb,
        make_estimator=make_est,
        settings=settings,
    )
    cv_pk = run_purged_kfold_regression(
        X=X_full,
        y=y_full,
        ranges=ranges,
        k_folds=k_cv,
        embargo_pct=emb,
        make_estimator=make_est,
        settings=settings,
    )
    cv_report = build_cv_report_with_leakage_family_audit(
        cv_wf=cv_wf,
        cv_pk=cv_pk,
        examples=examples,
        ranges=ranges,
        k_folds=k_cv,
        embargo_pct=emb,
        settings=settings,
        metric_summary={
            "walk_forward_mean_mae_bps": mean_fold_metric(cv_wf, "mae_bps"),
            "purged_kfold_mean_mae_bps": mean_fold_metric(cv_pk, "mae_bps"),
        },
    )
    train_end = _holdout_start(len(examples))
    train_examples = examples[:train_end]
    test_examples = examples[train_end:]

    train_X, train_y_raw = _matrix_and_target(train_examples)
    test_X, test_y = _matrix_and_target(test_examples)

    lower_bound, upper_bound = _prediction_bounds(train_y_raw, spec=spec)
    train_y = [float(np.clip(value, lower_bound, upper_bound)) for value in train_y_raw]

    base_model = _build_regressor(spec.scaling_method, random_state=rs)
    base_model.fit(train_X, train_y)
    model = BoundedRegressionModel(
        base_model=base_model,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
    )

    test_predictions = [float(value) for value in model.predict(test_X)]
    metrics = _regression_metrics(test_y, test_predictions)
    regime_metrics = _regime_metrics(test_examples, test_predictions)
    target_summary = _target_summary(train_y_raw)
    feature_reference = build_signal_model_feature_reference(train_examples)

    run_id = uuid4()
    trained_at_ms = int(time.time() * 1000)
    version = f"hgb-reg-{trained_at_ms}"
    feature_contract = signal_model_feature_contract_descriptor(
        model_name=spec.model_name,
        target_field=spec.target_field,
        output_field=spec.output_field,
        model_kind=BPS_REGRESSION_MODEL_KIND,
        scaling_method=spec.scaling_method,
    )
    feature_schema_hash = str(feature_contract["schema_hash"])
    dataset_hash = stable_json_hash(
        {
            "model_name": spec.model_name,
            "symbol": symbol.upper() if symbol else None,
            "feature_schema_hash": feature_schema_hash,
            "target_schema_hash": MODEL_TARGET_SCHEMA_HASH,
            "paper_trade_ids": [item["paper_trade_id"] for item in examples],
            "targets": [item["target"] for item in examples],
        }
    )
    data_version_hash = compute_data_version_hash(
        symbol=symbol,
        paper_trade_ids=[item["paper_trade_id"] for item in examples],
        decision_ts_ms=[int(item["decision_ts_ms"]) for item in examples],
        label_digest=[float(item["target"]) for item in examples],
        feature_schema_hash=feature_schema_hash,
    )

    artifact_dir = _artifact_dir(settings.expected_bps_model_artifacts_dir, spec.model_name, run_id)
    model_path = artifact_dir / "model.joblib"
    dump(model, model_path)

    training_window = {
        "decision_from_ts_ms": int(examples[0]["decision_ts_ms"]),
        "decision_to_ts_ms": int(examples[-1]["decision_ts_ms"]),
    }
    training_manifest = build_training_manifest(
        model_name=spec.model_name,
        training_seed=rs,
        cv_kfolds=k_cv,
        cv_embargo_pct=emb,
        data_version_hash=data_version_hash,
        feature_schema_hash=feature_schema_hash,
        target_schema_hash=MODEL_TARGET_SCHEMA_HASH,
        training_window=training_window,
        dataset_hash=dataset_hash,
        symbol=symbol,
        extra={
            "model_artifacts_dir": settings.model_artifacts_dir,
            "scaling_method": spec.scaling_method,
        },
    )

    metadata = {
        "run_id": str(run_id),
        "model_name": spec.model_name,
        "version": version,
        "model_kind": BPS_REGRESSION_MODEL_KIND,
        "target_field": spec.target_field,
        "output_field": spec.output_field,
        "scaling_method": spec.scaling_method,
        "prediction_lower_bound_bps": lower_bound,
        "prediction_upper_bound_bps": upper_bound,
        "dataset_hash": dataset_hash,
        "data_version_hash": data_version_hash,
        "trained_at_ms": trained_at_ms,
        "feature_contract": feature_contract,
        "target_schema_hash": MODEL_TARGET_SCHEMA_HASH,
        "train_rows": len(train_examples),
        "test_rows": len(test_examples),
        "decision_from_ts_ms": training_window["decision_from_ts_ms"],
        "decision_to_ts_ms": training_window["decision_to_ts_ms"],
        "target_summary_train": target_summary,
        "regime_counts_train": _regime_counts(train_examples),
        "feature_reference": feature_reference,
        "metrics": metrics,
        "regime_metrics": regime_metrics,
        "cv_report": cv_report,
        "artifact_files": {
            "model": "model.joblib",
            "metadata": "metadata.json",
            "training_manifest": "training_manifest.json",
            "cv_report": "cv_report.json",
            "run_manifest": "run_manifest.json",
        },
    }
    (artifact_dir / "training_manifest.json").write_text(
        json.dumps(training_manifest, indent=2, default=str),
        encoding="utf-8",
    )
    (artifact_dir / "cv_report.json").write_text(
        json.dumps(cv_report, indent=2, default=str),
        encoding="utf-8",
    )
    (artifact_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, default=str),
        encoding="utf-8",
    )
    write_full_run_manifest(
        artifact_dir,
        run_id=run_id,
        model_name=spec.model_name,
        version=version,
        trained_at_ms=trained_at_ms,
        training_manifest=training_manifest,
        metadata=metadata,
        metrics=metrics,
        feature_contract=feature_contract,
        settings=settings,
        row_counts={
            "total": len(examples),
            "train": len(train_examples),
            "test": len(test_examples),
        },
        calibration_method=None,
        artifact_files={
            "model": "model.joblib",
            "metadata": "metadata.json",
            "training_manifest": "training_manifest.json",
            "cv_report": "cv_report.json",
            "run_manifest": "run_manifest.json",
        },
        split_description={
            "type": "chronological_holdout_regression",
            "train_end_exclusive_index": train_end,
        },
        cv_report_summary=cv_report.get("summary"),
    )

    if promote:
        repo_model_runs.clear_promoted_model(conn, model_name=spec.model_name)
    repo_model_runs.insert_model_run(
        conn,
        run_id=run_id,
        model_name=spec.model_name,
        version=version,
        dataset_hash=dataset_hash,
        metrics_json={**metrics, "regime_metrics": regime_metrics, "cv_summary": cv_report["summary"]},
        promoted_bool=promote,
        artifact_path=_artifact_reference(model_path),
        target_name=spec.target_field,
        output_field=spec.output_field,
        calibration_method=None,
        metadata_json=metadata,
    )
    return {
        "run_id": str(run_id),
        "model_name": spec.model_name,
        "version": version,
        "promoted": promote,
        "artifact_path": _artifact_reference(model_path),
        "dataset_hash": dataset_hash,
        "data_version_hash": data_version_hash,
        "metrics": metrics,
        "regime_metrics": regime_metrics,
        "cv_report": cv_report,
        "rows": {
            "total": len(examples),
            "train": len(train_examples),
            "test": len(test_examples),
        },
        "prediction_bounds_bps": {
            "lower": lower_bound,
            "upper": upper_bound,
        },
    }


def _example_from_row(
    row: dict[str, Any],
    *,
    target_field: str,
) -> dict[str, Any] | None:
    raw_target = row.get(target_field)
    if raw_target is None:
        return None
    try:
        target = float(raw_target)
    except (TypeError, ValueError):
        return None
    features = build_signal_model_feature_vector_from_evaluation(row)
    if not features:
        return None
    closed_raw = row.get("closed_ts_ms")
    closed_ts_ms = int(closed_raw) if closed_raw is not None else None
    meta = training_row_metadata(row)
    return {
        "paper_trade_id": str(row.get("paper_trade_id") or ""),
        "decision_ts_ms": int(row.get("decision_ts_ms") or 0),
        "closed_ts_ms": closed_ts_ms,
        "market_regime": str(row.get("market_regime") or "unknown"),
        "symbol": meta["symbol"],
        "market_family": meta["market_family"],
        "error_labels": meta["error_labels"],
        "features": features,
        "target": target,
    }


def _matrix_and_target(examples: list[dict[str, Any]]) -> tuple[list[list[float]], list[float]]:
    X = [[example["features"][field] for field in SIGNAL_MODEL_FEATURE_FIELDS] for example in examples]
    y = [float(example["target"]) for example in examples]
    return X, y


def _holdout_start(total_rows: int) -> int:
    test_rows = max(_MIN_TEST_ROWS, int(total_rows * 0.2))
    train_rows = total_rows - test_rows
    if train_rows < _MIN_TEST_ROWS:
        raise ValueError("chronologischer Holdout fuer Regressionsmodell nicht moeglich")
    return train_rows


def _prediction_bounds(train_targets: list[float], *, spec: BpsRegressionSpec) -> tuple[float, float]:
    values = np.asarray(train_targets, dtype=float)
    if values.size == 0:
        raise ValueError("keine Train-Targets fuer Bps-Regressionsmodell")
    if spec.nonnegative:
        values = np.clip(values, 0.0, None)
        lower = 0.0
        upper = float(np.quantile(values, spec.upper_quantile))
    else:
        lower = float(np.quantile(values, spec.lower_quantile))
        upper = float(np.quantile(values, spec.upper_quantile))
    if not math.isfinite(lower):
        lower = float(np.min(values))
    if not math.isfinite(upper):
        upper = float(np.max(values))
    if spec.nonnegative:
        lower = max(0.0, lower)
    if upper <= lower:
        pad = max(1.0, abs(upper) * 0.1 or 1.0)
        upper = lower + pad
    return lower, upper


def _build_regressor(scaling_method: str, *, random_state: int) -> TransformedTargetRegressor:
    regressor = HistGradientBoostingRegressor(
        learning_rate=0.05,
        max_depth=3,
        max_iter=220,
        min_samples_leaf=10,
        random_state=random_state,
        loss="absolute_error",
    )
    if scaling_method == "asinh_clip":
        return TransformedTargetRegressor(
            regressor=regressor,
            func=np.arcsinh,
            inverse_func=np.sinh,
            check_inverse=False,
        )
    if scaling_method == "log1p_clip":
        return TransformedTargetRegressor(
            regressor=regressor,
            func=np.log1p,
            inverse_func=np.expm1,
            check_inverse=False,
        )
    raise ValueError(f"unsupported scaling_method: {scaling_method!r}")


def _regression_metrics(y_true: list[float], y_pred: list[float]) -> dict[str, Any]:
    rmse = math.sqrt(mean_squared_error(y_true, y_pred))
    metrics: dict[str, Any] = {
        "count": len(y_true),
        "target_mean_bps": sum(y_true) / len(y_true) if y_true else 0.0,
        "prediction_mean_bps": sum(y_pred) / len(y_pred) if y_pred else 0.0,
        "mae_bps": float(mean_absolute_error(y_true, y_pred)),
        "rmse_bps": float(rmse),
        "median_absolute_error_bps": float(median_absolute_error(y_true, y_pred)),
    }
    try:
        metrics["r2"] = float(r2_score(y_true, y_pred))
    except ValueError:
        metrics["r2"] = None
    return metrics


def _regime_metrics(examples: list[dict[str, Any]], preds: list[float]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for example, pred in zip(examples, preds, strict=True):
        regime = str(example.get("market_regime") or "unknown")
        bucket = grouped.setdefault(regime, {"y_true": [], "y_pred": []})
        bucket["y_true"].append(float(example["target"]))
        bucket["y_pred"].append(float(pred))
    out: list[dict[str, Any]] = []
    for regime, payload in grouped.items():
        y_true = payload["y_true"]
        y_pred = payload["y_pred"]
        out.append(
            {
                "market_regime": regime,
                "count": len(y_true),
                "actual_mean_bps": sum(y_true) / len(y_true),
                "predicted_mean_bps": sum(y_pred) / len(y_pred),
                "mae_bps": float(mean_absolute_error(y_true, y_pred)),
            }
        )
    out.sort(key=lambda item: str(item["market_regime"]))
    return out


def _target_summary(values: list[float]) -> dict[str, Any]:
    arr = np.asarray(values, dtype=float)
    mu = float(np.mean(arr))
    sd = float(np.std(arr))
    skew = 0.0 if sd < 1e-12 else float(np.mean(((arr - mu) / sd) ** 3))
    return {
        "count": int(arr.size),
        "mean_bps": mu,
        "median_bps": float(np.median(arr)),
        "p05_bps": float(np.quantile(arr, 0.05)),
        "p95_bps": float(np.quantile(arr, 0.95)),
        "min_bps": float(np.min(arr)),
        "max_bps": float(np.max(arr)),
        "skewness": skew,
    }


def _regime_counts(examples: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for example in examples:
        regime = str(example.get("market_regime") or "unknown")
        counts[regime] = counts.get(regime, 0) + 1
    return counts


def _artifact_dir(base_dir: str | None, model_name: str, run_id: UUID) -> Path:
    if not base_dir:
        raise ValueError("expected_bps_model_artifacts_dir nicht gesetzt")
    base = Path(base_dir)
    if not base.is_absolute():
        base = Path(__file__).resolve().parents[5] / base
    target = base / model_name / str(run_id)
    target.mkdir(parents=True, exist_ok=True)
    return target


def _artifact_reference(path: Path) -> str:
    root = Path(__file__).resolve().parents[5]
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)
