from __future__ import annotations

from typing import Any

from learning_engine.training.constants import TRAINING_PIPELINE_VERSION


def build_training_manifest(
    *,
    model_name: str,
    training_seed: int,
    cv_kfolds: int,
    cv_embargo_pct: float,
    data_version_hash: str,
    feature_schema_hash: str,
    target_schema_hash: str,
    training_window: dict[str, int],
    dataset_hash: str,
    symbol: str | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "training_pipeline_version": TRAINING_PIPELINE_VERSION,
        "model_name": model_name,
        "training_seed": training_seed,
        "cv": {
            "walk_forward": {"k_folds": cv_kfolds, "embargo_pct": cv_embargo_pct},
            "purged_kfold_embargo": {"k_folds": cv_kfolds, "embargo_pct": cv_embargo_pct},
        },
        "data_version_hash": data_version_hash,
        "feature_schema_hash": feature_schema_hash,
        "target_schema_hash": target_schema_hash,
        "training_window": training_window,
        "dataset_hash": dataset_hash,
        "symbol": symbol.upper() if symbol else None,
    }
    if extra:
        manifest["extra"] = extra
    return manifest
