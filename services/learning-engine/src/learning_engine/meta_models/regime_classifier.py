from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
from joblib import dump
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, log_loss
from sklearn.preprocessing import LabelEncoder

from learning_engine.config import LearningEngineSettings
from learning_engine.storage import repo_model_runs
from learning_engine.training.cv_leakage_family import build_cv_report_with_leakage_family_audit
from learning_engine.training.cv_runner import (
    mean_fold_metric,
    run_purged_kfold_multiclass_classification,
    run_walk_forward_multiclass_classification,
)
from learning_engine.training.data_version import compute_data_version_hash
from learning_engine.training.example_ranges import label_ranges_for_examples
from learning_engine.training.manifest import build_training_manifest
from learning_engine.training.run_manifest import write_full_run_manifest
from shared_py.model_contracts import MODEL_TARGET_SCHEMA_HASH, normalize_market_regime, stable_json_hash
from shared_py.training_dataset_builder import training_row_metadata
from shared_py.take_trade_model import (
    MARKET_REGIME_CLASSIFIER_MODEL_NAME,
    MARKET_REGIME_TARGET_FIELD,
    REGIME_CLASSIFIER_MODEL_KIND,
    REGIME_MODEL_FEATURE_FIELDS,
    build_regime_model_feature_reference,
    build_regime_model_feature_vector_from_evaluation,
    regime_model_feature_contract_descriptor,
)

_MIN_TEST_ROWS = 16


def train_market_regime_classifier(
    conn: psycopg.Connection[Any],
    settings: LearningEngineSettings,
    *,
    symbol: str | None = None,
    promote: bool = True,
) -> dict[str, Any]:
    rows = repo_model_runs.fetch_regime_training_rows(conn, symbol=symbol)
    examples = [_example_from_row(row) for row in rows]
    examples = [ex for ex in examples if ex is not None]
    if len(examples) < settings.regime_classifier_min_rows:
        raise ValueError(
            "zu wenige Evaluations fuer market_regime_classifier "
            f"({len(examples)} < {settings.regime_classifier_min_rows})"
        )

    counts: dict[str, int] = {}
    for ex in examples:
        r = str(ex["regime"])
        counts[r] = counts.get(r, 0) + 1
    sparse = [r for r, c in counts.items() if c < settings.regime_classifier_min_per_class]
    if sparse:
        raise ValueError(
            "Regime-Klassen unter Mindestanzahl: "
            + ", ".join(f"{s}={counts[s]}" for s in sorted(sparse))
        )

    examples.sort(key=lambda item: item["decision_ts_ms"])
    feat_contract = regime_model_feature_contract_descriptor()
    feature_schema_hash = str(feat_contract["schema_hash"])
    ranges = label_ranges_for_examples(examples)
    X_full, y_str_full = _matrix_and_targets(examples)
    le_preview = LabelEncoder()
    y_enc_full = le_preview.fit_transform(y_str_full)
    k_cv = settings.train_cv_kfolds
    emb = settings.train_cv_embargo_pct
    rs = settings.train_random_state
    make_est = lambda: HistGradientBoostingClassifier(
        learning_rate=0.05,
        max_depth=3,
        max_iter=200,
        min_samples_leaf=10,
        random_state=rs,
    )
    cv_wf = run_walk_forward_multiclass_classification(
        X=X_full,
        y=list(y_enc_full),
        ranges=ranges,
        k_folds=k_cv,
        embargo_pct=emb,
        make_estimator=make_est,
        settings=settings,
    )
    cv_pk = run_purged_kfold_multiclass_classification(
        X=X_full,
        y=list(y_enc_full),
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
            "walk_forward_mean_accuracy": mean_fold_metric(cv_wf, "accuracy"),
            "walk_forward_mean_log_loss": mean_fold_metric(cv_wf, "log_loss"),
            "purged_kfold_mean_accuracy": mean_fold_metric(cv_pk, "accuracy"),
            "purged_kfold_mean_log_loss": mean_fold_metric(cv_pk, "log_loss"),
        },
    )

    train_end = _holdout_start(len(examples))
    train_examples = examples[:train_end]
    test_examples = examples[train_end:]

    le = LabelEncoder()
    train_regimes = [str(ex["regime"]) for ex in train_examples]
    le.fit(train_regimes)
    train_X, _ = _matrix_and_targets(train_examples)
    train_y = le.transform(train_regimes)
    known_test = [ex for ex in test_examples if str(ex["regime"]) in set(le.classes_)]
    metrics: dict[str, Any]
    model = HistGradientBoostingClassifier(
        learning_rate=0.05,
        max_depth=3,
        max_iter=200,
        min_samples_leaf=10,
        random_state=rs,
    )
    model.fit(train_X, train_y)
    if known_test:
        test_X, test_y_str = _matrix_and_targets(known_test)
        test_y = le.transform(test_y_str)
        test_pred = model.predict(test_X)
        metrics = {
            "count": len(test_y),
            "accuracy": float(accuracy_score(test_y, test_pred)),
        }
        try:
            prob = model.predict_proba(test_X)
            metrics["log_loss"] = float(log_loss(test_y, prob, labels=list(model.classes_)))
        except ValueError:
            metrics["log_loss"] = None
    else:
        metrics = {"count": 0, "accuracy": None, "log_loss": None}

    feature_reference = build_regime_model_feature_reference(train_examples)
    run_id = uuid4()
    trained_at_ms = int(time.time() * 1000)
    version = f"hgb-mc-{trained_at_ms}"
    dataset_hash = stable_json_hash(
        {
            "model_name": MARKET_REGIME_CLASSIFIER_MODEL_NAME,
            "symbol": symbol.upper() if symbol else None,
            "feature_schema_hash": feature_schema_hash,
            "target_schema_hash": MODEL_TARGET_SCHEMA_HASH,
            "paper_trade_ids": [item["paper_trade_id"] for item in examples],
            "regimes": [item["regime"] for item in examples],
        }
    )
    data_version_hash = compute_data_version_hash(
        symbol=symbol,
        paper_trade_ids=[item["paper_trade_id"] for item in examples],
        decision_ts_ms=[int(item["decision_ts_ms"]) for item in examples],
        label_digest=[str(item["regime"]) for item in examples],
        feature_schema_hash=feature_schema_hash,
    )

    bundle = {
        "model": model,
        "label_encoder": le,
        "feature_fields": list(REGIME_MODEL_FEATURE_FIELDS),
    }
    artifact_dir = _artifact_dir(settings.regime_classifier_model_artifacts_dir, run_id)
    model_path = artifact_dir / "model.joblib"
    dump(bundle, model_path)

    training_window = {
        "decision_from_ts_ms": int(examples[0]["decision_ts_ms"]),
        "decision_to_ts_ms": int(examples[-1]["decision_ts_ms"]),
    }
    training_manifest = build_training_manifest(
        model_name=MARKET_REGIME_CLASSIFIER_MODEL_NAME,
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
            "regime_class_counts": counts,
            "label_classes": list(le.classes_),
        },
    )
    metadata: dict[str, Any] = {
        "run_id": str(run_id),
        "model_name": MARKET_REGIME_CLASSIFIER_MODEL_NAME,
        "version": version,
        "model_kind": REGIME_CLASSIFIER_MODEL_KIND,
        "target_field": MARKET_REGIME_TARGET_FIELD,
        "output_field": "predicted_market_regime",
        "dataset_hash": dataset_hash,
        "data_version_hash": data_version_hash,
        "trained_at_ms": trained_at_ms,
        "feature_contract": feat_contract,
        "target_schema_hash": MODEL_TARGET_SCHEMA_HASH,
        "train_rows": len(train_examples),
        "test_rows": len(test_examples),
        "decision_from_ts_ms": training_window["decision_from_ts_ms"],
        "decision_to_ts_ms": training_window["decision_to_ts_ms"],
        "regime_counts_train": _regime_counts(train_examples),
        "label_classes": list(le.classes_),
        "feature_reference": feature_reference,
        "metrics": metrics,
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
        model_name=MARKET_REGIME_CLASSIFIER_MODEL_NAME,
        version=version,
        trained_at_ms=trained_at_ms,
        training_manifest=training_manifest,
        metadata=metadata,
        metrics=metrics,
        feature_contract=feat_contract,
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
            "type": "chronological_holdout_multiclass",
            "train_end_exclusive_index": train_end,
        },
        cv_report_summary=cv_report.get("summary"),
    )

    if promote:
        repo_model_runs.clear_promoted_model(conn, model_name=MARKET_REGIME_CLASSIFIER_MODEL_NAME)
    repo_model_runs.insert_model_run(
        conn,
        run_id=run_id,
        model_name=MARKET_REGIME_CLASSIFIER_MODEL_NAME,
        version=version,
        dataset_hash=dataset_hash,
        metrics_json={**metrics, "cv_summary": cv_report["summary"]},
        promoted_bool=promote,
        artifact_path=_artifact_reference(model_path),
        target_name=MARKET_REGIME_TARGET_FIELD,
        output_field="predicted_market_regime",
        calibration_method=None,
        metadata_json=metadata,
    )
    return {
        "run_id": str(run_id),
        "model_name": MARKET_REGIME_CLASSIFIER_MODEL_NAME,
        "version": version,
        "promoted": promote,
        "artifact_path": _artifact_reference(model_path),
        "dataset_hash": dataset_hash,
        "data_version_hash": data_version_hash,
        "metrics": metrics,
        "cv_report": cv_report,
        "rows": {
            "total": len(examples),
            "train": len(train_examples),
            "test": len(test_examples),
        },
    }


def _example_from_row(row: dict[str, Any]) -> dict[str, Any] | None:
    raw = row.get("market_regime")
    regime = normalize_market_regime(raw)
    if regime is None:
        return None
    features = build_regime_model_feature_vector_from_evaluation(row)
    if not features:
        return None
    closed_raw = row.get("closed_ts_ms")
    closed_ts_ms = int(closed_raw) if closed_raw is not None else None
    meta = training_row_metadata(row)
    return {
        "paper_trade_id": str(row.get("paper_trade_id") or ""),
        "decision_ts_ms": int(row.get("decision_ts_ms") or 0),
        "closed_ts_ms": closed_ts_ms,
        "regime": regime,
        "symbol": meta["symbol"],
        "market_family": meta["market_family"],
        "error_labels": meta["error_labels"],
        "features": features,
    }


def _matrix_and_targets(
    examples: list[dict[str, Any]],
) -> tuple[list[list[float]], list[str]]:
    X = [
        [float(ex["features"][field]) for field in REGIME_MODEL_FEATURE_FIELDS] for ex in examples
    ]
    y = [str(ex["regime"]) for ex in examples]
    return X, y


def _regime_counts(examples: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for ex in examples:
        r = str(ex["regime"])
        out[r] = out.get(r, 0) + 1
    return dict(sorted(out.items()))


def _holdout_start(total_rows: int) -> int:
    test_rows = max(_MIN_TEST_ROWS, int(total_rows * 0.2))
    train_rows = total_rows - test_rows
    if train_rows < _MIN_TEST_ROWS:
        raise ValueError("chronologischer Holdout fuer Regime-Klassifikator nicht moeglich")
    return train_rows


def _artifact_dir(base_dir: str | None, run_id: UUID) -> Path:
    if not base_dir:
        raise ValueError("regime_classifier_model_artifacts_dir nicht gesetzt")
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
