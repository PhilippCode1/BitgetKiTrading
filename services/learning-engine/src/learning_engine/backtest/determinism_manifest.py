"""Reproduktions-Metadaten fuer Replay und Offline-Backtest (Prompt 27)."""

from __future__ import annotations

from typing import Any

from shared_py.model_contracts import FEATURE_SCHEMA_HASH, FEATURE_SCHEMA_VERSION, MODEL_CONTRACT_VERSION
from shared_py.replay_determinism import REPLAY_DETERMINISM_PROTOCOL_VERSION
from shared_py.signal_contracts import SIGNAL_EVENT_SCHEMA_VERSION

from learning_engine.config import LearningEngineSettings


def policy_caps_snapshot(settings: LearningEngineSettings) -> dict[str, Any]:
    """Nicht-sensitive Policy-/Risk-Caps aus BaseServiceSettings (Signal-Engine-Paritaet)."""
    return {
        "risk_hard_gating_enabled": settings.risk_hard_gating_enabled,
        "risk_default_action": str(settings.risk_default_action),
        "risk_min_signal_strength": settings.risk_min_signal_strength,
        "risk_min_probability": settings.risk_min_probability,
        "risk_min_risk_score": settings.risk_min_risk_score,
        "risk_min_expected_return_bps": settings.risk_min_expected_return_bps,
        "risk_max_expected_mae_bps": settings.risk_max_expected_mae_bps,
        "risk_min_projected_rr": settings.risk_min_projected_rr,
        "risk_allowed_leverage_min": settings.risk_allowed_leverage_min,
        "risk_allowed_leverage_max": settings.risk_allowed_leverage_max,
        "risk_require_7x_approval": settings.risk_require_7x_approval,
        "risk_max_position_risk_pct": settings.risk_max_position_risk_pct,
        "risk_max_concurrent_positions": settings.risk_max_concurrent_positions,
    }


def build_replay_manifest(settings: LearningEngineSettings) -> dict[str, Any]:
    return {
        "determinism_protocol_version": REPLAY_DETERMINISM_PROTOCOL_VERSION,
        "model_contract_version": MODEL_CONTRACT_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_schema_hash": FEATURE_SCHEMA_HASH,
        "train_random_state": settings.train_random_state,
        "policy_caps": policy_caps_snapshot(settings),
        # Paritaet Signal-Engine Hybrid/Risk (gleiche Version wie signal_engine.hybrid_decision)
        "hybrid_decision_policy_version": "hybrid-v4",
        "signal_event_schema_version": SIGNAL_EVENT_SCHEMA_VERSION,
    }


def build_offline_backtest_manifest(
    settings: LearningEngineSettings,
    *,
    cv_method: str,
    k_folds: int,
    embargo_pct: float,
) -> dict[str, Any]:
    return {
        **build_replay_manifest(settings),
        "cv_method": cv_method,
        "k_folds": k_folds,
        "embargo_pct": float(embargo_pct),
        "python_random_seed_applied": settings.train_random_state,
    }
