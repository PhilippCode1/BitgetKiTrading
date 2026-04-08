from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
LEARNING_SRC = ROOT / "services" / "learning-engine" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for candidate in (LEARNING_SRC, SHARED_SRC):
    s = str(candidate)
    if candidate.is_dir() and s not in sys.path:
        sys.path.insert(0, s)

from learning_engine.config import LearningEngineSettings
from learning_engine.registry_v2 import service as registry_v2_service
from learning_engine.storage import repo_model_registry_v2, repo_model_runs
from shared_py.take_trade_model import TAKE_TRADE_MODEL_NAME


@pytest.fixture
def settings_gates_on(monkeypatch: pytest.MonkeyPatch) -> LearningEngineSettings:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("MODEL_PROMOTION_GATES_ENABLED", "true")
    monkeypatch.setenv("MODEL_CALIBRATION_REQUIRED", "true")
    return LearningEngineSettings()


def test_assign_champion_rejected_when_gates_fail(
    settings_gates_on: LearningEngineSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rid = uuid4()
    monkeypatch.setattr(
        repo_model_registry_v2,
        "fetch_model_run_by_id",
        lambda _conn, run_id: {
            "model_name": TAKE_TRADE_MODEL_NAME,
            "run_id": str(run_id),
            "calibration_method": "sigmoid",
            "metadata_json": {"artifact_files": {"calibration": "calibration.joblib"}},
            "metrics_json": {
                "cv_summary": {
                    "walk_forward_mean_roc_auc": 0.40,
                    "purged_kfold_mean_roc_auc": 0.41,
                },
                "roc_auc": 0.42,
                "brier_score": 0.20,
            },
        },
    )
    conn = MagicMock()
    with pytest.raises(HTTPException) as exc:
        registry_v2_service.assign_champion(
            conn,
            settings_gates_on,
            model_name=TAKE_TRADE_MODEL_NAME,
            run_id=rid,
        )
    assert exc.value.status_code == 400


def test_try_auto_rollback_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("MODEL_REGISTRY_AUTO_ROLLBACK_ON_DRIFT_HARD_BLOCK", "false")
    s = LearningEngineSettings()
    out = registry_v2_service.try_auto_rollback_on_drift_hard_block(
        MagicMock(),
        s,
        previous_effective_action="warn",
        new_effective_action="hard_block",
    )
    assert out is None


def test_try_auto_rollback_no_checkpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("MODEL_REGISTRY_AUTO_ROLLBACK_ON_DRIFT_HARD_BLOCK", "true")
    s = LearningEngineSettings()
    monkeypatch.setattr(
        "learning_engine.registry_v2.service.repo_model_champion_lifecycle.fetch_stable_checkpoint_run_id",
        lambda *_a, **_k: None,
    )
    out = registry_v2_service.try_auto_rollback_on_drift_hard_block(
        MagicMock(),
        s,
        previous_effective_action="warn",
        new_effective_action="hard_block",
    )
    assert out == {"attempted": True, "applied": False, "detail": "no_stable_checkpoint"}


def test_try_auto_rollback_skips_same_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("MODEL_REGISTRY_AUTO_ROLLBACK_ON_DRIFT_HARD_BLOCK", "true")
    s = LearningEngineSettings()
    out = registry_v2_service.try_auto_rollback_on_drift_hard_block(
        MagicMock(),
        s,
        previous_effective_action="hard_block",
        new_effective_action="hard_block",
    )
    assert out is None


def test_assign_champion_override_passes_weak_cv(
    settings_gates_on: LearningEngineSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rid = uuid4()

    def _fetch(_c, run_id):
        return {
            "model_name": TAKE_TRADE_MODEL_NAME,
            "run_id": str(run_id),
            "calibration_method": "sigmoid",
            "metadata_json": {"artifact_files": {"calibration": "calibration.joblib"}},
            "metrics_json": {
                "cv_summary": {
                    "walk_forward_mean_roc_auc": 0.40,
                    "purged_kfold_mean_roc_auc": 0.41,
                },
                "roc_auc": 0.42,
                "brier_score": 0.20,
            },
        }

    monkeypatch.setattr(repo_model_registry_v2, "fetch_model_run_by_id", _fetch)
    monkeypatch.setattr(repo_model_runs, "clear_promoted_model", MagicMock())
    monkeypatch.setattr(
        repo_model_registry_v2,
        "upsert_registry_slot",
        lambda _conn, **kwargs: {
            "registry_id": str(uuid4()),
            "model_name": kwargs["model_name"],
            "role": kwargs["role"],
            "run_id": str(kwargs["run_id"]),
            "calibration_status": kwargs["calibration_status"],
        },
    )
    monkeypatch.setattr(registry_v2_service, "_close_champion_history_safe", lambda *a, **k: None)
    monkeypatch.setattr(registry_v2_service, "_insert_champion_history_safe", lambda *a, **k: None)
    monkeypatch.setattr(registry_v2_service, "_audit", lambda *a, **k: None)

    conn = MagicMock()
    out = registry_v2_service.assign_champion(
        conn,
        settings_gates_on,
        model_name=TAKE_TRADE_MODEL_NAME,
        run_id=rid,
        promotion_manual_override=True,
        promotion_override_reason="breakglass ticket 12345 approved",
        changed_by="ops_lead",
    )
    assert out["status"] == "ok"
    assert out["promotion_gate_report"].get("manual_override") is True
