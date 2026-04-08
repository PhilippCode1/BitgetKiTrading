from __future__ import annotations

import pytest

from learning_engine.backtest.determinism_manifest import (
    build_offline_backtest_manifest,
    build_replay_manifest,
    policy_caps_snapshot,
)
from learning_engine.config import LearningEngineSettings


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> LearningEngineSettings:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    return LearningEngineSettings()


def test_build_replay_manifest_has_contract_and_policy_caps(settings: LearningEngineSettings) -> None:
    s = settings
    m = build_replay_manifest(s)
    assert m["determinism_protocol_version"]
    assert m["model_contract_version"]
    assert m["feature_schema_version"]
    assert m["feature_schema_hash"]
    assert m["train_random_state"] == s.train_random_state
    caps = m["policy_caps"]
    assert "risk_hard_gating_enabled" in caps
    assert "risk_allowed_leverage_min" in caps
    assert "risk_allowed_leverage_max" in caps
    assert "risk_require_7x_approval" in caps


def test_policy_caps_snapshot_matches_settings_fields(settings: LearningEngineSettings) -> None:
    s = settings
    caps = policy_caps_snapshot(s)
    assert caps["risk_allowed_leverage_min"] == s.risk_allowed_leverage_min
    assert caps["risk_allowed_leverage_max"] == s.risk_allowed_leverage_max


def test_offline_manifest_extends_replay(settings: LearningEngineSettings) -> None:
    s = settings
    o = build_offline_backtest_manifest(
        s, cv_method="walk_forward", k_folds=3, embargo_pct=0.1
    )
    assert o["cv_method"] == "walk_forward"
    assert o["k_folds"] == 3
    assert o["embargo_pct"] == 0.1
    assert o["python_random_seed_applied"] == s.train_random_state
    assert o["model_contract_version"] == build_replay_manifest(s)["model_contract_version"]
