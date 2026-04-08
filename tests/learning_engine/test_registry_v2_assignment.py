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
from learning_engine.registry_v2.service import assign_champion
from learning_engine.storage import repo_model_registry_v2, repo_model_runs


@pytest.fixture
def settings_cal_req(monkeypatch: pytest.MonkeyPatch) -> LearningEngineSettings:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("MODEL_CALIBRATION_REQUIRED", "true")
    return LearningEngineSettings()


def test_assign_champion_rejects_missing_calibration(
    settings_cal_req: LearningEngineSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rid = uuid4()
    monkeypatch.setattr(
        repo_model_registry_v2,
        "fetch_model_run_by_id",
        lambda _conn, run_id: {
            "model_name": "take_trade_prob",
            "run_id": str(run_id),
            "calibration_method": None,
            "metadata_json": {},
        },
    )
    conn = MagicMock()
    with pytest.raises(HTTPException) as exc:
        assign_champion(conn, settings_cal_req, model_name="take_trade_prob", run_id=rid)
    assert exc.value.status_code == 400


def test_assign_champion_accepts_calibrated_run(
    settings_cal_req: LearningEngineSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rid = uuid4()
    monkeypatch.setattr(
        repo_model_registry_v2,
        "fetch_model_run_by_id",
        lambda _conn, run_id: {
            "model_name": "take_trade_prob",
            "run_id": str(rid),
            "calibration_method": "sigmoid",
            "metadata_json": {"artifact_files": {"calibration": "calibration.joblib"}},
        },
    )
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
    monkeypatch.setattr(
        "learning_engine.registry_v2.service._audit",
        lambda *a, **k: None,
    )
    conn = MagicMock()
    out = assign_champion(conn, settings_cal_req, model_name="take_trade_prob", run_id=rid)
    assert out["status"] == "ok"
    repo_model_runs.clear_promoted_model.assert_called_once()
    conn.execute.assert_called()
