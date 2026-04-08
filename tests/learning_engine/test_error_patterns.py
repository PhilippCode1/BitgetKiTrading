from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEARNING_SRC = ROOT / "services" / "learning-engine" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for candidate in (LEARNING_SRC, SHARED_SRC):
    candidate_str = str(candidate)
    if candidate.is_dir() and candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from learning_engine.analytics.error_patterns import losing_trade_condition_key


def test_losing_trade_condition_key_normalizes_regime_aliases() -> None:
    key = losing_trade_condition_key(
        {
            "market_regime": "RANGE",
            "signal_snapshot_json": {
                "timeframe": "5m",
                "signal_class": "kern",
                "market_regime": "UP",
                "regime_bias": "long",
                "multi_timeframe_score_0_100": 55,
                "structure_score_0_100": 60,
            },
            "feature_snapshot_json": {
                "primary_tf": {
                    "atrp_14": 0.004,
                    "execution_cost_bps": 3.0,
                    "depth_to_bar_volume_ratio": 0.9,
                    "liquidity_source": "orderbook_levels",
                }
            },
        }
    )
    assert "regime=trend" in key
    assert "regime_bias=long" in key
