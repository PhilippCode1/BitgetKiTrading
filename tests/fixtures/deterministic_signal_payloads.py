"""
Deterministische Signal-Dicts fuer Risk-/Uncertainty-Unit-Tests.

Liegt unter `tests/fixtures/`. Laedt `tests/conftest.py` per `sys.path`.
"""

from __future__ import annotations

from typing import Any


def base_allow_trade_signal(
    *,
    signal_id: str = "sig-det-1",
    symbol: str = "BTCUSDT",
    allowed_leverage: int = 12,
    recommended_leverage: int = 10,
) -> dict[str, Any]:
    return {
        "signal_id": signal_id,
        "symbol": symbol,
        "direction": "long",
        "trade_action": "allow_trade",
        "decision_state": "accepted",
        "rejection_state": False,
        "signal_strength_0_100": 82,
        "probability_0_1": 0.72,
        "take_trade_prob": 0.72,
        "risk_score_0_100": 76,
        "expected_return_bps": 18.0,
        "expected_mae_bps": 20.0,
        "expected_mfe_bps": 34.0,
        "market_regime": "trend",
        "quality_gate": {"passed": True},
        "allowed_leverage": allowed_leverage,
        "recommended_leverage": recommended_leverage,
        "leverage_policy_version": "int-leverage-v1",
        "leverage_cap_reasons_json": [],
    }


def take_trade_prediction_low_uncertainty(
    *,
    take_trade_prob: float = 0.74,
    confidence_0_1: float = 0.85,
) -> dict[str, Any]:
    return {
        "take_trade_prob": take_trade_prob,
        "take_trade_model_diagnostics": {
            "confidence_0_1": confidence_0_1,
            "ood_score_0_1": 0.0,
            "ood_alert": False,
            "ood_reasons_json": [],
        },
    }


def target_projection_complete(
    *,
    max_bound_proximity_0_1: float = 0.1,
) -> dict[str, Any]:
    return {
        "expected_return_bps": 14.0,
        "expected_mae_bps": 18.0,
        "expected_mfe_bps": 31.0,
        "target_projection_diagnostics": {
            "ood_score_0_1": 0.0,
            "ood_alert": False,
            "ood_reasons_json": [],
            "max_bound_proximity_0_1": max_bound_proximity_0_1,
        },
    }
