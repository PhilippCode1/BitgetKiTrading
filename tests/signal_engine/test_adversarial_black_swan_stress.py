"""
Prompt 71: 100 synthetische Black-Swan-Szenarien — Risk-Governor muss blocken
(Adversarial Block Rate 100 % bei Stress über survival_kernel-Disruption).
"""

from __future__ import annotations

import sys
from pathlib import Path

# signal_engine conftest legt services/signal-engine/src an; adversarial via Root-pyproject
_SERVICE_ADV = (
    Path(__file__).resolve().parents[2] / "services" / "adversarial-engine" / "src"
)
if str(_SERVICE_ADV) not in sys.path:
    sys.path.insert(0, str(_SERVICE_ADV))

from adversarial_engine.market_stresser import (  # noqa: E402
    stress_path_risk_features,
    tensor_paths_to_numpy,
)
from adversarial_engine.models.wgan_gp import (  # noqa: E402
    AdversarialMarketSimulator,
    generate_black_swan_sequence,
)
from signal_engine.risk_governor import assess_risk_governor  # noqa: E402

_STRESS_N = 100


def _stress_signal_row(
    *,
    momentum_score: float,
    market_anomaly_confidence_0_1: float,
    vpin_0_1: float,
) -> dict:
    return {
        "symbol": "BTCUSDT",
        "market_regime": "trend",
        "regime_state": "trend",
        "regime_confidence_0_1": 0.88,
        "model_uncertainty_0_1": 0.12,
        "market_anomaly_confidence_0_1": market_anomaly_confidence_0_1,
        "source_snapshot_json": {
            "feature_snapshot": {
                "primary_tf": {
                    "momentum_score": momentum_score,
                    "market_vpin_score": vpin_0_1,
                }
            },
            "quality_gate": {"passed": True},
        },
    }


def test_adversarial_block_rate_100_on_black_swan_stress(signal_settings) -> None:
    sim = AdversarialMarketSimulator(latent_dim=48, seq_len=160, rho=0.25)
    blocked = 0
    above_kernel = 0
    for i in range(_STRESS_N):
        paths, meta = generate_black_swan_sequence(
            sim, batch=1, toxicity_0_1=0.96, seed=10_000 + i, leptokurtic_mix=0.32
        )
        r, d = tensor_paths_to_numpy(paths)
        fe = stress_path_risk_features(
            r, d, toxicity_0_1=float(meta.get("toxicity", 0.95))
        )
        assert fe["disruption_score"] >= fe["enter_threshold"]
        above_kernel += 1
        row = _stress_signal_row(
            momentum_score=91.0 + (i % 5),
            market_anomaly_confidence_0_1=fe["market_anomaly_confidence_0_1"],
            vpin_0_1=fe["suggested_vpin_0_1"],
        )
        gov = assess_risk_governor(
            settings=signal_settings, signal_row=row, direction="long"
        )
        u = list(gov.get("universal_hard_block_reasons_json") or [])
        if u and (
            "RISK_VPIN_HALT" in u or "risk_governor_market_anomaly_confidence_high" in u
        ):
            blocked += 1
    rate = blocked / float(_STRESS_N)
    assert above_kernel == _STRESS_N
    assert rate == 1.0, f"Adversarial Block Rate={rate:.3f} (erwartet 1.0)"
    print(
        f"\n[adversarial_stress] scenarios={_STRESS_N} "
        f"Adversarial_Block_Rate={rate:.1%} "
        f"disruption>kernel={above_kernel}"
    )
