from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg

from learning_engine.storage import repo_model_registry_v2, repo_model_runs


def export_rl_artifact_to_registry_v2(
    conn: psycopg.Connection[Any],
    *,
    run_id: UUID,
    model_name: str,
    version: str,
    dataset_hash: str,
    metrics_json: dict[str, Any],
    metadata_json: dict[str, Any],
    artifact_path: str | None = None,
    registry_role: str = "candidate",
    calibration_status: str = "uncalibrated",
    scope_type: str = "global",
    scope_key: str = "",
    notes: str | None = None,
    promoted_bool: bool = False,
) -> dict[str, Any]:
    """
    Persistiert einen RL-Lauf in ``app.model_runs`` und bucht optional einen ``model_registry_v2``-Slot.

    Hinweis: ``target_name`` bleibt fuer RL-Runs ``None`` (kein supervised Label aus
    ``_ALLOWED_TRAINING_TARGET_FIELDS``); Metadaten transportieren Policy-Typ und Hyperparameter.
    """
    repo_model_runs.insert_model_run(
        conn,
        run_id=run_id,
        model_name=model_name,
        version=version,
        dataset_hash=dataset_hash,
        metrics_json=metrics_json,
        promoted_bool=promoted_bool,
        artifact_path=artifact_path,
        target_name=None,
        output_field=None,
        calibration_method="rl_policy",
        metadata_json=metadata_json,
    )
    return repo_model_registry_v2.upsert_registry_slot(
        conn,
        model_name=model_name,
        role=registry_role,
        run_id=run_id,
        calibration_status=calibration_status,
        notes=notes,
        scope_type=scope_type,
        scope_key=scope_key,
    )


def write_rl_checkpoint_local(
    path: Path,
    *,
    policy_state: dict[str, Any],
    consensus_weights: list[float] | None = None,
) -> None:
    """Schreibt ein portables JSON-Checkpoint-Stub (fuer artifact_path in model_runs)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"policy_state": policy_state, "consensus_weights": consensus_weights}
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
