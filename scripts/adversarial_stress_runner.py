#!/usr/bin/env python3
"""
CLI: Prompt 71 — 100 (oder --n) Black-Swan-Szenarien, Metrik „Adversarial Block Rate“.

PYTHONPATH muss shared/python/src und services/adversarial-engine/src enthalten
(oder von Repo-Root: ``python scripts/adversarial_stress_runner.py``).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (
    _ROOT,
    _ROOT / "shared" / "python" / "src",
    _ROOT / "services" / "adversarial-engine" / "src",
    _ROOT / "services" / "signal-engine" / "src",
):
    s = str(_p)
    if s not in sys.path:
        sys.path.insert(0, s)

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@127.0.0.1:5432/test")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")

from adversarial_engine.market_stresser import stress_path_risk_features, tensor_paths_to_numpy  # noqa: E402
from adversarial_engine.models.wgan_gp import (  # noqa: E402
    AdversarialMarketSimulator,
    generate_black_swan_sequence,
)
from signal_engine.config import SignalEngineSettings  # noqa: E402
from signal_engine.risk_governor import assess_risk_governor  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100, help="Anzahl Stress-Szenarien")
    args = ap.parse_args()
    n = max(1, int(args.n))
    settings = SignalEngineSettings()
    sim = AdversarialMarketSimulator(latent_dim=48, seq_len=160, rho=0.25)
    blocked = 0
    for i in range(n):
        paths, meta = generate_black_swan_sequence(
            sim, batch=1, toxicity_0_1=0.96, seed=20_000 + i, leptokurtic_mix=0.32
        )
        r, d = tensor_paths_to_numpy(paths)
        fe = stress_path_risk_features(r, d, toxicity_0_1=float(meta.get("toxicity", 0.95)))
        row = {
            "symbol": "BTCUSDT",
            "market_regime": "trend",
            "regime_state": "trend",
            "regime_confidence_0_1": 0.88,
            "model_uncertainty_0_1": 0.12,
            "market_anomaly_confidence_0_1": fe["market_anomaly_confidence_0_1"],
            "source_snapshot_json": {
                "feature_snapshot": {
                    "primary_tf": {
                        "momentum_score": 90.0 + (i % 7),
                        "market_vpin_score": fe["suggested_vpin_0_1"],
                    }
                },
                "quality_gate": {"passed": True},
            },
        }
        gov = assess_risk_governor(settings=settings, signal_row=row, direction="long")
        u = list(gov.get("universal_hard_block_reasons_json") or [])
        if u and (
            "RISK_VPIN_HALT" in u
            or "risk_governor_market_anomaly_confidence_high" in u
        ):
            blocked += 1
        print(
            f"scenario {i+1:04d}/{n} disruption={fe['disruption_score']:.2f} "
            f">= kernel {fe['enter_threshold']:.2f} block_ok="
            f"{(u and ('RISK_VPIN_HALT' in u or 'risk_governor_market_anomaly_confidence_high' in u))}"
        )
    rate = blocked / float(n)
    print("---")
    print(f"Adversarial Block Rate: {rate:.1%} ({blocked}/{n})")
    if rate < 1.0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
