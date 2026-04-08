from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED_SRC = ROOT / "shared" / "python" / "src"
if SHARED_SRC.is_dir() and str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from shared_py.projection_adjustment import (
    apply_projection_cost_adjustment,
    cap_from_liquidation_stress,
    liquidation_proximity_stress_0_1,
)


def test_apply_projection_subtracts_round_trip_and_inflates_mae() -> None:
    primary = {
        "spread_bps": 4.0,
        "execution_cost_bps": 3.0,
        "volatility_cost_bps": 2.0,
        "impact_buy_bps_10000": 6.0,
        "impact_sell_bps_10000": 5.0,
    }
    out = apply_projection_cost_adjustment(
        raw_return_bps=20.0,
        raw_mae_bps=30.0,
        raw_mfe_bps=50.0,
        direction="long",
        primary_tf=primary,
    )
    assert out["round_trip_cost_bps"] > 0
    eff = out["effective_bps"]
    assert eff["expected_return_bps"] is not None
    assert eff["expected_return_bps"] < 20.0
    assert eff["expected_mae_bps"] is not None
    assert eff["expected_mae_bps"] >= 30.0
    assert eff["expected_mfe_bps"] is not None
    assert eff["expected_mfe_bps"] <= 50.0
    assert out["safety_stop_buffer_bps"] is not None
    assert out["model_raw_bps"]["expected_return_bps"] == 20.0


def test_liquidation_stress_increases_with_leverage_and_mae() -> None:
    s_low = liquidation_proximity_stress_0_1(effective_adverse_bps=100.0, preview_leverage=10)
    s_high_lev = liquidation_proximity_stress_0_1(effective_adverse_bps=100.0, preview_leverage=40)
    assert s_low is not None and s_high_lev is not None
    assert s_high_lev > s_low


def test_cap_from_liquidation_stress_reduces_at_high_stress() -> None:
    loose = cap_from_liquidation_stress(stress_0_1=0.5, risk_max=75)
    tight = cap_from_liquidation_stress(stress_0_1=0.95, risk_max=75)
    assert loose == 75
    assert tight is not None and tight < 75
