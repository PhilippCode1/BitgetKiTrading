from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LEARNING_SRC = ROOT / "services" / "learning-engine" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for candidate in (LEARNING_SRC, SHARED_SRC):
    s = str(candidate)
    if candidate.is_dir() and s not in sys.path:
        sys.path.insert(0, s)

from learning_engine.config import LearningEngineSettings
from learning_engine.registry_v2.champion_promotion_gates import evaluate_champion_promotion_gates
from shared_py.take_trade_model import MARKET_REGIME_CLASSIFIER_MODEL_NAME, TAKE_TRADE_MODEL_NAME


@pytest.fixture
def settings_gates_on(monkeypatch: pytest.MonkeyPatch) -> LearningEngineSettings:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("MODEL_PROMOTION_GATES_ENABLED", "true")
    return LearningEngineSettings()


def test_take_trade_passes_with_strong_cv_and_test(settings_gates_on: LearningEngineSettings) -> None:
    mj = {
        "cv_summary": {
            "walk_forward_mean_roc_auc": 0.75,
            "purged_kfold_mean_roc_auc": 0.74,
        },
        "roc_auc": 0.72,
        "brier_score": 0.18,
    }
    r = evaluate_champion_promotion_gates(
        model_name=TAKE_TRADE_MODEL_NAME,
        metrics_json=mj,
        metadata_json={},
        settings=settings_gates_on,
    )
    assert r.ok
    assert not r.reasons


def test_take_trade_fails_low_walk_forward(settings_gates_on: LearningEngineSettings) -> None:
    mj = {
        "cv_summary": {
            "walk_forward_mean_roc_auc": 0.40,
            "purged_kfold_mean_roc_auc": 0.74,
        },
        "roc_auc": 0.72,
        "brier_score": 0.18,
    }
    r = evaluate_champion_promotion_gates(
        model_name=TAKE_TRADE_MODEL_NAME,
        metrics_json=mj,
        metadata_json={},
        settings=settings_gates_on,
    )
    assert not r.ok
    assert "walk_forward_mean_roc_auc_below_minimum" in r.reasons


def test_regime_passes(settings_gates_on: LearningEngineSettings) -> None:
    mj = {
        "cv_summary": {
            "walk_forward_mean_accuracy": 0.55,
            "purged_kfold_mean_accuracy": 0.54,
        },
    }
    r = evaluate_champion_promotion_gates(
        model_name=MARKET_REGIME_CLASSIFIER_MODEL_NAME,
        metrics_json=mj,
        metadata_json={},
        settings=settings_gates_on,
    )
    assert r.ok


def test_shadow_evidence_required_fails_without_meta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("MODEL_PROMOTION_GATES_ENABLED", "true")
    monkeypatch.setenv("MODEL_PROMOTION_REQUIRE_SHADOW_EVIDENCE", "true")
    s = LearningEngineSettings()
    mj = {
        "cv_summary": {"walk_forward_mean_roc_auc": 0.9, "purged_kfold_mean_roc_auc": 0.9},
        "roc_auc": 0.88,
        "brier_score": 0.15,
    }
    r = evaluate_champion_promotion_gates(
        model_name=TAKE_TRADE_MODEL_NAME,
        metrics_json=mj,
        metadata_json={},
        settings=s,
    )
    assert not r.ok
    assert "shadow_evidence_missing_or_failed" in r.reasons


def test_shadow_evidence_passes_with_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("MODEL_PROMOTION_GATES_ENABLED", "true")
    monkeypatch.setenv("MODEL_PROMOTION_REQUIRE_SHADOW_EVIDENCE", "true")
    s = LearningEngineSettings()
    mj = {
        "cv_summary": {"walk_forward_mean_roc_auc": 0.9, "purged_kfold_mean_roc_auc": 0.9},
        "roc_auc": 0.88,
        "brier_score": 0.15,
    }
    r = evaluate_champion_promotion_gates(
        model_name=TAKE_TRADE_MODEL_NAME,
        metrics_json=mj,
        metadata_json={"shadow_validation": {"passed": True}},
        settings=s,
    )
    assert r.ok


def test_cv_symbol_leakage_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("MODEL_PROMOTION_GATES_ENABLED", "true")
    monkeypatch.setenv("MODEL_PROMOTION_FAIL_ON_CV_SYMBOL_LEAKAGE_TAKE_TRADE", "true")
    monkeypatch.setenv("MODEL_PROMOTION_MAX_CV_SYMBOL_OVERLAP_FOLDS_TAKE_TRADE", "0")
    s = LearningEngineSettings()
    mj = {
        "cv_summary": {
            "walk_forward_mean_roc_auc": 0.75,
            "purged_kfold_mean_roc_auc": 0.74,
            "symbol_leakage_walk_forward": {"folds_with_symbol_overlap": 1},
            "symbol_leakage_purged_kfold_embargo": {"folds_with_symbol_overlap": 0},
        },
        "roc_auc": 0.72,
        "brier_score": 0.18,
    }
    r = evaluate_champion_promotion_gates(
        model_name=TAKE_TRADE_MODEL_NAME,
        metrics_json=mj,
        metadata_json={},
        settings=s,
    )
    assert not r.ok
    assert "walk_forward_cv_symbol_overlap_exceeds_maximum" in r.reasons


def test_governance_artifacts_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("MODEL_PROMOTION_GATES_ENABLED", "true")
    monkeypatch.setenv("MODEL_PROMOTION_REQUIRE_GOVERNANCE_ARTIFACTS", "true")
    s = LearningEngineSettings()
    mj = {
        "cv_summary": {"walk_forward_mean_roc_auc": 0.75, "purged_kfold_mean_roc_auc": 0.74},
        "roc_auc": 0.72,
        "brier_score": 0.18,
    }
    r = evaluate_champion_promotion_gates(
        model_name=TAKE_TRADE_MODEL_NAME,
        metrics_json=mj,
        metadata_json={},
        settings=s,
    )
    assert not r.ok
    assert "governance_data_version_hash_missing" in r.reasons


def test_online_drift_blocks_global_take_trade_promotion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("MODEL_PROMOTION_GATES_ENABLED", "true")
    monkeypatch.setenv("MODEL_PROMOTION_APPLY_ONLINE_DRIFT_GATE", "true")
    s = LearningEngineSettings()
    mj = {
        "cv_summary": {"walk_forward_mean_roc_auc": 0.75, "purged_kfold_mean_roc_auc": 0.74},
        "roc_auc": 0.72,
        "brier_score": 0.18,
    }
    meta = {
        "data_version_hash": "dv",
        "dataset_hash": "ds",
        "feature_contract": {"schema_hash": "sh"},
        "artifact_files": {"training_manifest": "training_manifest.json"},
        "calibration_curve": [{"bin": 0}],
    }
    r = evaluate_champion_promotion_gates(
        model_name=TAKE_TRADE_MODEL_NAME,
        metrics_json=mj,
        metadata_json=meta,
        settings=s,
        online_drift_effective_action="shadow_only",
        promotion_scope_type="global",
        promotion_scope_key="",
    )
    assert not r.ok
    assert "online_drift_blocks_champion_promotion" in r.reasons


def test_symbol_scope_requires_train_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("MODEL_PROMOTION_GATES_ENABLED", "true")
    monkeypatch.setenv("SPECIALIST_SYMBOL_MIN_ROWS", "100")
    s = LearningEngineSettings()
    mj = {
        "cv_summary": {"walk_forward_mean_roc_auc": 0.75, "purged_kfold_mean_roc_auc": 0.74},
        "roc_auc": 0.72,
        "brier_score": 0.18,
    }
    meta = {"train_rows": 12}
    r = evaluate_champion_promotion_gates(
        model_name=TAKE_TRADE_MODEL_NAME,
        metrics_json=mj,
        metadata_json=meta,
        settings=s,
        promotion_scope_type="symbol",
        promotion_scope_key="BTCUSDT",
    )
    assert not r.ok
    assert "symbol_scope_insufficient_train_rows" in r.reasons


def test_trade_relevance_high_conf_fp_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("MODEL_PROMOTION_GATES_ENABLED", "true")
    monkeypatch.setenv("MODEL_PROMOTION_REQUIRE_TRADE_RELEVANCE_GATES_TAKE_TRADE", "true")
    monkeypatch.setenv("MODEL_PROMOTION_TRADE_RELEVANCE_MAX_HIGH_CONF_FP_RATE", "0.2")
    s = LearningEngineSettings()
    mj = {
        "cv_summary": {"walk_forward_mean_roc_auc": 0.75, "purged_kfold_mean_roc_auc": 0.74},
        "roc_auc": 0.72,
        "brier_score": 0.18,
        "trade_relevance_summary": {"high_confidence_false_positive_rate": 0.5},
    }
    r = evaluate_champion_promotion_gates(
        model_name=TAKE_TRADE_MODEL_NAME,
        metrics_json=mj,
        metadata_json={},
        settings=s,
    )
    assert not r.ok
    assert "trade_relevance_high_conf_fp_above_cap" in r.reasons
