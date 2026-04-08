from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import UUID

import pytest

ROOT = Path(__file__).resolve().parents[2]
LEARNING_SRC = ROOT / "services" / "learning-engine" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for candidate in (LEARNING_SRC, SHARED_SRC):
    s = str(candidate)
    if candidate.is_dir() and s not in sys.path:
        sys.path.insert(0, s)


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    from learning_engine.config import LearningEngineSettings

    return LearningEngineSettings()


def test_learning_engine_source_bundle_hash_stable() -> None:
    from learning_engine.training.reproducibility import learning_engine_source_bundle_hash

    a = learning_engine_source_bundle_hash()
    b = learning_engine_source_bundle_hash()
    assert len(a) == 40
    assert a == b


def test_write_full_run_manifest_file_shape(settings, tmp_path: Path) -> None:
    from learning_engine.training.manifest import build_training_manifest
    from learning_engine.training.run_manifest import write_full_run_manifest

    adir = tmp_path / "run"
    adir.mkdir()
    tm = build_training_manifest(
        model_name="test_model",
        training_seed=42,
        cv_kfolds=5,
        cv_embargo_pct=0.05,
        data_version_hash="dv1",
        feature_schema_hash="fs1",
        target_schema_hash="ts1",
        training_window={"decision_from_ts_ms": 1, "decision_to_ts_ms": 2},
        dataset_hash="ds1",
        symbol="BTCUSDT",
    )
    meta = {"run_id": "x", "metrics": {"a": 1}}
    write_full_run_manifest(
        adir,
        run_id=UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
        model_name="test_model",
        version="v-test",
        trained_at_ms=123,
        training_manifest=tm,
        metadata=meta,
        metrics={"roc_auc": 0.7},
        feature_contract={"schema_hash": "fs1", "fields": []},
        settings=settings,
        row_counts={"train": 10, "test": 2},
        calibration_method="sigmoid",
        artifact_files={"model": "model.joblib", "run_manifest": "run_manifest.json"},
        split_description={"type": "unit"},
        cv_report_summary={"mean": 1.0},
    )
    path = adir / "run_manifest.json"
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["run_manifest_version"] == "1.0"
    assert data["training_pipeline_version"]
    assert data["dataset"]["data_version_hash"] == "dv1"
    assert data["feature_schema"]["schema_hash"] == "fs1"
    assert data["artifacts"]["files_relative"]["model"] == "model.joblib"
    assert data["reproducibility"]["learning_engine_source_bundle_sha256_40"]
    assert "training_manifest_embedded" in data
