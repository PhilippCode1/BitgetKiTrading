from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
from joblib import dump
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score

from learning_engine.config import LearningEngineSettings
from learning_engine.storage import repo_model_runs
from learning_engine.training.cv_leakage_family import build_cv_report_with_leakage_family_audit
from learning_engine.training.cv_runner import (
    mean_fold_metric,
    run_purged_kfold_binary_classification,
    run_walk_forward_binary_classification,
)
from learning_engine.training.trade_relevance_metrics import (
    execution_sensitivity_proxy,
    stop_failure_mode_rates,
    trade_relevance_binary_classification_report,
)
from learning_engine.training.data_version import compute_data_version_hash
from learning_engine.training.example_ranges import label_ranges_for_examples
from learning_engine.training.manifest import build_training_manifest
from learning_engine.training.run_manifest import write_full_run_manifest
from shared_py.model_contracts import MODEL_TARGET_SCHEMA_HASH, stable_json_hash
from shared_py.model_layer_contract import canonical_model_layer_descriptor
from shared_py.take_trade_model import (
    CalibratedTakeTradeProbModel,
    TAKE_TRADE_MODEL_KIND,
    TAKE_TRADE_MODEL_NAME,
    TAKE_TRADE_TARGET_FIELD,
    build_signal_model_feature_reference,
    take_trade_feature_contract_descriptor,
)
from shared_py.training_dataset_builder import (
    TakeTradeDatasetBuildConfig,
    build_take_trade_training_dataset,
    training_feature_matrix,
)

_MIN_SPLIT_ROWS = 8


def train_take_trade_prob_model(
    conn: psycopg.Connection[Any],
    settings: LearningEngineSettings,
    *,
    symbol: str | None = None,
    promote: bool = True,
) -> dict[str, Any]:
    rows = repo_model_runs.fetch_take_trade_training_rows(conn, symbol=symbol)
    ds_config = TakeTradeDatasetBuildConfig(max_feature_age_ms=settings.learn_max_feature_age_ms)
    examples, dataset_build_report = build_take_trade_training_dataset(rows, ds_config)
    if len(examples) < settings.take_trade_model_min_rows:
        raise ValueError(
            "zu wenige Evaluations fuer take_trade_prob "
            f"({len(examples)} < {settings.take_trade_model_min_rows})"
        )

    positives = sum(example["target"] for example in examples)
    negatives = len(examples) - positives
    if positives < settings.take_trade_model_min_positive_rows:
        raise ValueError(
            "zu wenige positive take_trade_label Zeilen "
            f"({positives} < {settings.take_trade_model_min_positive_rows})"
        )
    if negatives < settings.take_trade_model_min_positive_rows:
        raise ValueError(
            "zu wenige negative take_trade_label Zeilen "
            f"({negatives} < {settings.take_trade_model_min_positive_rows})"
        )

    examples.sort(key=lambda item: item["decision_ts_ms"])
    feat_contract = take_trade_feature_contract_descriptor()
    feature_schema_hash = str(feat_contract["schema_hash"])
    ranges = label_ranges_for_examples(examples)
    X_full, y_full = training_feature_matrix(examples)
    k_cv = settings.train_cv_kfolds
    emb = settings.train_cv_embargo_pct
    rs = settings.train_random_state
    make_est = lambda: HistGradientBoostingClassifier(
        learning_rate=0.05,
        max_depth=3,
        max_iter=180,
        min_samples_leaf=10,
        random_state=rs,
    )
    cv_wf = run_walk_forward_binary_classification(
        X=X_full,
        y=y_full,
        ranges=ranges,
        k_folds=k_cv,
        embargo_pct=emb,
        make_estimator=make_est,
    )
    cv_pk = run_purged_kfold_binary_classification(
        X=X_full,
        y=y_full,
        ranges=ranges,
        k_folds=k_cv,
        embargo_pct=emb,
        make_estimator=make_est,
    )
    cv_report = build_cv_report_with_leakage_family_audit(
        cv_wf=cv_wf,
        cv_pk=cv_pk,
        examples=examples,
        ranges=ranges,
        k_folds=k_cv,
        embargo_pct=emb,
        metric_summary={
            "walk_forward_mean_roc_auc": mean_fold_metric(cv_wf, "roc_auc"),
            "walk_forward_mean_log_loss": mean_fold_metric(cv_wf, "log_loss"),
            "purged_kfold_mean_roc_auc": mean_fold_metric(cv_pk, "roc_auc"),
            "purged_kfold_mean_log_loss": mean_fold_metric(cv_pk, "log_loss"),
        },
    )
    train_end, calibration_end = _chronological_split_boundaries(examples)

    train_examples = examples[:train_end]
    calibration_examples = examples[train_end:calibration_end]
    test_examples = examples[calibration_end:]

    train_X, train_y = training_feature_matrix(train_examples)
    calibration_X, calibration_y = training_feature_matrix(calibration_examples)
    test_X, test_y = training_feature_matrix(test_examples)

    base_model = HistGradientBoostingClassifier(
        learning_rate=0.05,
        max_depth=3,
        max_iter=180,
        min_samples_leaf=10,
        random_state=rs,
    )
    base_model.fit(train_X, train_y)

    calibration_method = settings.take_trade_model_calibration_method
    calibration_probs = [float(p[1]) for p in base_model.predict_proba(calibration_X)]
    calibrator = _fit_calibrator(
        calibration_method=calibration_method,
        base_probs=calibration_probs,
        y_true=calibration_y,
        random_state=rs,
    )
    calibrated_model = CalibratedTakeTradeProbModel(
        base_model=base_model,
        calibration_method=calibration_method,
        calibrator=calibrator,
    )

    test_probs = [float(p[1]) for p in calibrated_model.predict_proba(test_X)]
    metrics = _classification_metrics(test_y, test_probs)
    trade_relevance_full = {
        "binary_classification": trade_relevance_binary_classification_report(
            list(test_y), test_probs
        ),
        "stop_failure_mode_counts_test": stop_failure_mode_rates(test_examples),
        "execution_sensitivity": execution_sensitivity_proxy(test_examples, test_probs),
    }
    tr_bin = trade_relevance_full["binary_classification"]
    trade_relevance_summary = {
        "test_count": tr_bin.get("count"),
        "abstention_precision_on_negative_class": tr_bin.get(
            "abstention_precision_on_negative_class"
        ),
        "high_confidence_false_positive_rate": tr_bin.get("high_confidence_false_positive_rate"),
        "top_decile_tail_false_positive_rate": tr_bin.get("top_decile_tail_false_positive_rate"),
        "execution_sensitivity_available": trade_relevance_full["execution_sensitivity"].get(
            "available"
        ),
        "report_file": "trade_relevance_report.json",
    }
    regime_metrics = _regime_metrics(test_examples, test_probs)
    calibration_curve = _calibration_curve(test_y, test_probs)
    feature_reference = build_signal_model_feature_reference(train_examples)

    run_id = uuid4()
    trained_at_ms = int(time.time() * 1000)
    version = f"hgb-cal-{trained_at_ms}"
    dataset_hash = stable_json_hash(
        {
            "model_name": TAKE_TRADE_MODEL_NAME,
            "symbol": symbol.upper() if symbol else None,
            "feature_schema_hash": feature_schema_hash,
            "target_schema_hash": MODEL_TARGET_SCHEMA_HASH,
            "dataset_builder_config_fingerprint": dataset_build_report.config_fingerprint,
            "drop_counts": dataset_build_report.dropped,
            "paper_trade_ids": [item["paper_trade_id"] for item in examples],
            "labels": [item["target"] for item in examples],
        }
    )
    data_version_hash = compute_data_version_hash(
        symbol=symbol,
        paper_trade_ids=[item["paper_trade_id"] for item in examples],
        decision_ts_ms=[int(item["decision_ts_ms"]) for item in examples],
        label_digest=[int(item["target"]) for item in examples],
        feature_schema_hash=feature_schema_hash,
    )

    artifact_dir = _artifact_dir(settings.take_trade_model_artifacts_dir, run_id)
    model_path = artifact_dir / "model.joblib"
    dump(calibrated_model, model_path)
    calibration_path = artifact_dir / "calibration.joblib"
    dump(calibrator, calibration_path)

    training_window = {
        "decision_from_ts_ms": int(examples[0]["decision_ts_ms"]),
        "decision_to_ts_ms": int(examples[-1]["decision_ts_ms"]),
    }
    training_manifest = build_training_manifest(
        model_name=TAKE_TRADE_MODEL_NAME,
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
            "dataset_builder_config_fingerprint": dataset_build_report.config_fingerprint,
            "dataset_drop_counts": dataset_build_report.dropped,
        },
    )

    metadata = {
        "run_id": str(run_id),
        "model_name": TAKE_TRADE_MODEL_NAME,
        "version": version,
        "model_kind": TAKE_TRADE_MODEL_KIND,
        "target_field": TAKE_TRADE_TARGET_FIELD,
        "output_field": "take_trade_prob",
        "calibration_method": calibration_method,
        "dataset_hash": dataset_hash,
        "data_version_hash": data_version_hash,
        "trained_at_ms": trained_at_ms,
        "feature_contract": feat_contract,
        "model_layer_contract": canonical_model_layer_descriptor(include_field_tiers=True),
        "dataset_build_report": {
            "config_fingerprint": dataset_build_report.config_fingerprint,
            "kept_count": dataset_build_report.kept_count,
            "dropped": dataset_build_report.dropped,
            "schema_drift_samples": dataset_build_report.schema_drift_samples,
        },
        "training_rows_raw": len(rows),
        "target_schema_hash": MODEL_TARGET_SCHEMA_HASH,
        "train_rows": len(train_examples),
        "calibration_rows": len(calibration_examples),
        "test_rows": len(test_examples),
        "positive_rate_train": _positive_rate(train_y),
        "positive_rate_calibration": _positive_rate(calibration_y),
        "positive_rate_test": _positive_rate(test_y),
        "decision_from_ts_ms": training_window["decision_from_ts_ms"],
        "decision_to_ts_ms": training_window["decision_to_ts_ms"],
        "regime_counts_train": _regime_counts(train_examples),
        "feature_reference": feature_reference,
        "metrics": metrics,
        "regime_metrics": regime_metrics,
        "calibration_curve": calibration_curve,
        "cv_report": cv_report,
        "trade_relevance_summary": trade_relevance_summary,
        "artifact_files": {
            "model": "model.joblib",
            "calibration": "calibration.joblib",
            "metadata": "metadata.json",
            "training_manifest": "training_manifest.json",
            "cv_report": "cv_report.json",
            "trade_relevance_report": "trade_relevance_report.json",
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
    (artifact_dir / "trade_relevance_report.json").write_text(
        json.dumps(trade_relevance_full, indent=2, default=str),
        encoding="utf-8",
    )
    (artifact_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, default=str),
        encoding="utf-8",
    )
    write_full_run_manifest(
        artifact_dir,
        run_id=run_id,
        model_name=TAKE_TRADE_MODEL_NAME,
        version=version,
        trained_at_ms=trained_at_ms,
        training_manifest=training_manifest,
        metadata=metadata,
        metrics=metrics,
        feature_contract=feat_contract,
        settings=settings,
        row_counts={
            "raw_from_db": len(rows),
            "after_dataset_gates": len(examples),
            "train": len(train_examples),
            "calibration": len(calibration_examples),
            "test": len(test_examples),
        },
        calibration_method=calibration_method,
        artifact_files={
            "model": "model.joblib",
            "calibration": "calibration.joblib",
            "metadata": "metadata.json",
            "training_manifest": "training_manifest.json",
            "cv_report": "cv_report.json",
            "trade_relevance_report": "trade_relevance_report.json",
            "run_manifest": "run_manifest.json",
        },
        split_description={
            "type": "chronological_train_calibration_test",
            "train_end_exclusive_index": train_end,
            "calibration_end_exclusive_index": calibration_end,
        },
        cv_report_summary=cv_report.get("summary"),
    )

    if promote:
        repo_model_runs.clear_promoted_model(conn, model_name=TAKE_TRADE_MODEL_NAME)
    repo_model_runs.insert_model_run(
        conn,
        run_id=run_id,
        model_name=TAKE_TRADE_MODEL_NAME,
        version=version,
        dataset_hash=dataset_hash,
        metrics_json={
            **metrics,
            "regime_metrics": regime_metrics,
            "calibration_curve": calibration_curve,
            "cv_summary": cv_report["summary"],
            "trade_relevance_summary": trade_relevance_summary,
        },
        promoted_bool=promote,
        artifact_path=_artifact_reference(model_path),
        target_name=TAKE_TRADE_TARGET_FIELD,
        output_field="take_trade_prob",
        calibration_method=calibration_method,
        metadata_json=metadata,
    )
    return {
        "run_id": str(run_id),
        "model_name": TAKE_TRADE_MODEL_NAME,
        "version": version,
        "promoted": promote,
        "artifact_path": _artifact_reference(model_path),
        "dataset_hash": dataset_hash,
        "metrics": metrics,
        "regime_metrics": regime_metrics,
        "calibration_curve": calibration_curve,
        "data_version_hash": data_version_hash,
        "cv_report": cv_report,
        "trade_relevance_summary": trade_relevance_summary,
        "rows": {
            "raw_from_db": len(rows),
            "after_dataset_gates": len(examples),
            "total": len(examples),
            "train": len(train_examples),
            "calibration": len(calibration_examples),
            "test": len(test_examples),
        },
    }


def _chronological_split_boundaries(examples: list[dict[str, Any]]) -> tuple[int, int]:
    labels = [int(example["target"]) for example in examples]
    n = len(labels)
    test_start = _find_suffix_start(
        labels,
        approx_start=max(_MIN_SPLIT_ROWS * 2, int(n * 0.8)),
        min_start=max(_MIN_SPLIT_ROWS * 2, int(n * 0.55)),
    )
    calibration_start = _find_middle_start(
        labels[:test_start],
        approx_start=max(_MIN_SPLIT_ROWS, int(test_start * 0.75)),
        min_start=max(_MIN_SPLIT_ROWS, int(n * 0.35)),
    )
    return calibration_start, test_start


def _find_suffix_start(labels: list[int], *, approx_start: int, min_start: int) -> int:
    upper = min(max(approx_start, min_start), len(labels) - _MIN_SPLIT_ROWS)
    for start in range(upper, min_start - 1, -1):
        suffix = labels[start:]
        if len(suffix) < _MIN_SPLIT_ROWS:
            continue
        if _has_both_classes(suffix):
            return start
    raise ValueError("chronologischer Test-Split ohne beide Klassen nicht moeglich")


def _find_middle_start(labels: list[int], *, approx_start: int, min_start: int) -> int:
    upper = min(max(approx_start, min_start), len(labels) - _MIN_SPLIT_ROWS)
    for start in range(upper, min_start - 1, -1):
        train = labels[:start]
        calibration = labels[start:]
        if len(train) < _MIN_SPLIT_ROWS or len(calibration) < _MIN_SPLIT_ROWS:
            continue
        if _has_both_classes(train) and _has_both_classes(calibration):
            return start
    raise ValueError("chronologischer Train/Calibration-Split ohne beide Klassen nicht moeglich")


def _has_both_classes(labels: list[int]) -> bool:
    return any(label == 1 for label in labels) and any(label == 0 for label in labels)


def _fit_calibrator(
    *,
    calibration_method: str,
    base_probs: list[float],
    y_true: list[int],
    random_state: int,
) -> Any:
    if calibration_method == "sigmoid":
        calibrator = LogisticRegression(random_state=random_state)
        calibrator.fit([[prob] for prob in base_probs], y_true)
        return calibrator
    if calibration_method == "isotonic":
        calibrator = IsotonicRegression(out_of_bounds="clip")
        calibrator.fit(base_probs, y_true)
        return calibrator
    raise ValueError(f"unsupported calibration_method: {calibration_method!r}")


def _classification_metrics(y_true: list[int], probs: list[float]) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "count": len(y_true),
        "positive_rate": _positive_rate(y_true),
        "brier_score": float(brier_score_loss(y_true, probs)),
        "log_loss": float(log_loss(y_true, probs, labels=[0, 1])),
        "average_precision": float(average_precision_score(y_true, probs)),
    }
    try:
        metrics["roc_auc"] = float(roc_auc_score(y_true, probs))
    except ValueError:
        metrics["roc_auc"] = None
    return metrics


def _regime_metrics(examples: list[dict[str, Any]], probs: list[float]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for example, prob in zip(examples, probs, strict=True):
        regime = str(example.get("market_regime") or "unknown")
        bucket = grouped.setdefault(regime, {"y_true": [], "probs": []})
        bucket["y_true"].append(int(example["target"]))
        bucket["probs"].append(float(prob))
    out: list[dict[str, Any]] = []
    for regime, payload in grouped.items():
        y_true = payload["y_true"]
        regime_probs = payload["probs"]
        out.append(
            {
                "market_regime": regime,
                "count": len(y_true),
                "positive_rate": _positive_rate(y_true),
                "avg_probability": sum(regime_probs) / len(regime_probs),
                "brier_score": float(brier_score_loss(y_true, regime_probs)),
            }
        )
    out.sort(key=lambda item: str(item["market_regime"]))
    return out


def _calibration_curve(y_true: list[int], probs: list[float], *, bins: int = 5) -> list[dict[str, Any]]:
    buckets = [{"count": 0, "sum_prob": 0.0, "sum_target": 0.0} for _ in range(bins)]
    for truth, prob in zip(y_true, probs, strict=True):
        idx = min(bins - 1, int(prob * bins))
        bucket = buckets[idx]
        bucket["count"] += 1
        bucket["sum_prob"] += float(prob)
        bucket["sum_target"] += float(truth)
    out: list[dict[str, Any]] = []
    for idx, bucket in enumerate(buckets):
        count = int(bucket["count"])
        out.append(
            {
                "bin_index": idx,
                "bin_start": idx / bins,
                "bin_end": (idx + 1) / bins,
                "count": count,
                "avg_probability": bucket["sum_prob"] / count if count else None,
                "empirical_positive_rate": bucket["sum_target"] / count if count else None,
            }
        )
    return out


def _regime_counts(examples: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for example in examples:
        regime = str(example.get("market_regime") or "unknown")
        counts[regime] = counts.get(regime, 0) + 1
    return counts


def _positive_rate(values: list[int]) -> float:
    if not values:
        return 0.0
    return float(sum(values)) / float(len(values))


def _artifact_dir(base_dir: str | None, run_id: UUID) -> Path:
    if not base_dir:
        raise ValueError("take_trade_model_artifacts_dir nicht gesetzt")
    base = Path(base_dir)
    if not base.is_absolute():
        base = Path(__file__).resolve().parents[5] / base
    target = base / str(run_id)
    target.mkdir(parents=True, exist_ok=True)
    return target


def _artifact_reference(path: Path) -> str:
    root = Path(__file__).resolve().parents[5]
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)
