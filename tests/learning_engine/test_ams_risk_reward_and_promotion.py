from __future__ import annotations

from unittest.mock import patch

from learning_engine.rl_env.trading_environment import (
    RewardWeights,
    compute_ams_governor_reward,
    compute_step_reward,
)
from learning_engine.registry_v2.champion_promotion_gates import evaluate_champion_promotion_gates
from learning_engine.config import LearningEngineSettings
from learning_engine.stress_test.schemas import AdversarialStressRunResultV1
from shared_py.take_trade_model import TAKE_TRADE_MODEL_NAME


def test_compute_ams_governor_reward_signs() -> None:
    w = RewardWeights()
    assert compute_ams_governor_reward(
        ams_trap_active=True, governor_blocked_trade=True, weights=w
    ) == float(w.ams_governor_block_bonus)
    assert compute_ams_governor_reward(
        ams_trap_active=True, governor_blocked_trade=False, weights=w
    ) == -float(w.ams_false_negative_penalty)
    assert compute_ams_governor_reward(ams_trap_active=False, governor_blocked_trade=True, weights=w) == 0.0


def test_compute_step_reward_includes_ams() -> None:
    base = compute_step_reward(
        realized_pnl_delta=0.0,
        sharpe_before=0.0,
        sharpe_after=0.0,
        drawdown_depth=0.0,
        trade_open_steps=0,
        max_trade_horizon=10,
        risk_violation=False,
        ams_trap_active=False,
        governor_blocked_trade=False,
    )
    boosted = compute_step_reward(
        realized_pnl_delta=0.0,
        sharpe_before=0.0,
        sharpe_after=0.0,
        drawdown_depth=0.0,
        trade_open_steps=0,
        max_trade_horizon=10,
        risk_violation=False,
        ams_trap_active=True,
        governor_blocked_trade=True,
    )
    assert boosted > base


def test_promotion_gate_fails_on_low_resilience() -> None:
    settings = LearningEngineSettings()
    settings.model_promotion_gates_enabled = True
    settings.model_promotion_require_adversarial_stress = True
    settings.risk_toxicity_classifier_model_path = "/tmp/dummy_ams_rf.joblib"

    bad = AdversarialStressRunResultV1(
        attacks_total=1000,
        attacks_high_risk=400,
        attacks_deflected=300,
        resilience_score_0_100=75.0,
        min_resilience_required_0_100=90.0,
        passed=False,
    )
    metrics_json = {
        "cv_summary": {
            "walk_forward_mean_roc_auc": 0.99,
            "purged_kfold_mean_roc_auc": 0.99,
        },
        "roc_auc": 0.99,
        "brier_score": 0.1,
    }

    with patch(
        "learning_engine.stress_test.adversarial_stress_pipeline.run_adversarial_stress_suite",
        return_value=bad,
    ):
        gr = evaluate_champion_promotion_gates(
            model_name=TAKE_TRADE_MODEL_NAME,
            metrics_json=metrics_json,
            metadata_json={},
            settings=settings,
        )
    assert not gr.ok
    assert "adversarial_stress_resilience_below_minimum" in gr.reasons
