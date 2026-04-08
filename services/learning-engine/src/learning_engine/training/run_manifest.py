"""
Vollstaendiges Run-Manifest pro Trainingslauf (neben training_manifest.json).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from learning_engine.config import LearningEngineSettings
from learning_engine.training.constants import TRAINING_PIPELINE_VERSION

RUN_MANIFEST_VERSION = "1.0"


def snapshot_training_parameters(settings: LearningEngineSettings) -> dict[str, Any]:
    return {
        "train_cv_kfolds": settings.train_cv_kfolds,
        "train_cv_embargo_pct": settings.train_cv_embargo_pct,
        "train_random_state": settings.train_random_state,
        "specialist_family_min_rows": settings.specialist_family_min_rows,
        "specialist_cluster_min_rows": settings.specialist_cluster_min_rows,
        "specialist_regime_min_rows": settings.specialist_regime_min_rows,
        "specialist_playbook_min_rows": settings.specialist_playbook_min_rows,
        "specialist_symbol_min_rows": settings.specialist_symbol_min_rows,
        "take_trade_model_calibration_method": settings.take_trade_model_calibration_method,
        "learn_max_feature_age_ms": settings.learn_max_feature_age_ms,
        "take_trade_model_min_rows": settings.take_trade_model_min_rows,
        "take_trade_model_min_positive_rows": settings.take_trade_model_min_positive_rows,
        "expected_bps_model_min_rows": settings.expected_bps_model_min_rows,
        "regime_classifier_min_rows": settings.regime_classifier_min_rows,
        "regime_classifier_min_per_class": settings.regime_classifier_min_per_class,
        "model_artifacts_dir": settings.model_artifacts_dir,
        "take_trade_model_artifacts_dir": settings.take_trade_model_artifacts_dir,
        "expected_bps_model_artifacts_dir": settings.expected_bps_model_artifacts_dir,
        "regime_classifier_model_artifacts_dir": settings.regime_classifier_model_artifacts_dir,
        "model_calibration_required": settings.model_calibration_required,
        "model_champion_name": settings.model_champion_name,
        "model_registry_mutation_secret_configured": bool(
            (settings.model_registry_mutation_secret or "").strip()
        ),
        "model_promotion_fail_on_cv_symbol_leakage_take_trade": settings.model_promotion_fail_on_cv_symbol_leakage_take_trade,
        "model_promotion_require_trade_relevance_gates_take_trade": settings.model_promotion_require_trade_relevance_gates_take_trade,
    }


def build_run_manifest(
    *,
    run_id: UUID,
    model_name: str,
    version: str,
    trained_at_ms: int,
    training_manifest: dict[str, Any],
    metadata: dict[str, Any],
    metrics: dict[str, Any],
    feature_contract: dict[str, Any],
    settings: LearningEngineSettings,
    row_counts: dict[str, Any],
    calibration_method: str | None,
    split_description: dict[str, Any] | None,
    cv_report_summary: dict[str, Any] | None,
    reproducibility: dict[str, Any],
    artifact_files: dict[str, str],
    artifact_dir: Path,
) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[5]
    try:
        artifact_dir_resolved = artifact_dir.resolve()
        artifacts_relative = str(artifact_dir_resolved.relative_to(root)).replace("\\", "/")
    except ValueError:
        artifact_dir_resolved = artifact_dir.resolve()
        artifacts_relative = str(artifact_dir_resolved).replace("\\", "/")

    files_resolved = {
        name: str((artifact_dir / rel).resolve()).replace("\\", "/")
        for name, rel in artifact_files.items()
    }

    return {
        "run_manifest_version": RUN_MANIFEST_VERSION,
        "training_pipeline_version": TRAINING_PIPELINE_VERSION,
        "run_id": str(run_id),
        "model_name": model_name,
        "model_version": version,
        "trained_at_ms": trained_at_ms,
        "dataset": {
            "data_version_hash": training_manifest.get("data_version_hash"),
            "dataset_hash": training_manifest.get("dataset_hash"),
            "training_window": training_manifest.get("training_window"),
            "symbol": training_manifest.get("symbol"),
            "row_counts": row_counts,
        },
        "feature_schema": {
            "schema_hash": training_manifest.get("feature_schema_hash"),
            "target_schema_hash": training_manifest.get("target_schema_hash"),
            "contract": feature_contract,
        },
        "splits_and_evaluation": {
            "cv": training_manifest.get("cv"),
            "split_description": split_description or {},
            "cv_report_summary": cv_report_summary or {},
        },
        "calibration": {
            "method": calibration_method,
            "applied": calibration_method is not None,
        },
        "metrics": metrics,
        "parameters": snapshot_training_parameters(settings),
        "training_manifest_embedded": training_manifest,
        "metadata_embedded_keys": sorted(metadata.keys()),
        "artifacts": {
            "directory_relative_repo": artifacts_relative,
            "directory_absolute": str(artifact_dir_resolved).replace("\\", "/"),
            "files_relative": artifact_files,
            "files_absolute": files_resolved,
        },
        "reproducibility": reproducibility,
    }


def write_run_manifest_file(artifact_dir: Path, manifest: dict[str, Any]) -> Path:
    path = artifact_dir / "run_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return path


def write_full_run_manifest(
    artifact_dir: Path,
    *,
    run_id: UUID,
    model_name: str,
    version: str,
    trained_at_ms: int,
    training_manifest: dict[str, Any],
    metadata: dict[str, Any],
    metrics: dict[str, Any],
    feature_contract: dict[str, Any],
    settings: LearningEngineSettings,
    row_counts: dict[str, Any],
    calibration_method: str | None,
    artifact_files: dict[str, str],
    split_description: dict[str, Any] | None = None,
    cv_report_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from learning_engine.training.reproducibility import collect_reproducibility_context

    repro = collect_reproducibility_context()
    manifest = build_run_manifest(
        run_id=run_id,
        model_name=model_name,
        version=version,
        trained_at_ms=trained_at_ms,
        training_manifest=training_manifest,
        metadata=metadata,
        metrics=metrics,
        feature_contract=feature_contract,
        settings=settings,
        row_counts=row_counts,
        calibration_method=calibration_method,
        split_description=split_description,
        cv_report_summary=cv_report_summary,
        reproducibility=repro,
        artifact_files=artifact_files,
        artifact_dir=artifact_dir,
    )
    write_run_manifest_file(artifact_dir, manifest)
    return manifest
