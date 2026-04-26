from __future__ import annotations

from shared_py.exit_family_resolver import (
    EXIT_FAMILY_RESOLUTION_VERSION,
    extract_exit_execution_hints_from_trace,
    resolve_exit_family_resolution,
)


def test_resolve_exit_family_resolution_merges_news_and_mfe_mae() -> None:
    db_row: dict = {
        "news_score_0_100": 75.0,
        "expected_mfe_bps": 50.0,
        "expected_mae_bps": 10.0,
        "market_family": "futures",
        "playbook_family": "mean_reversion",
        "source_snapshot_json": {
            "feature_snapshot": {
                "primary_tf": {
                    "spread_bps": 12.0,
                    "depth_to_bar_volume_ratio": 0.2,
                    "funding_cost_bps_window": 2.0,
                    "mark_index_spread_bps": 20.0,
                }
            }
        },
    }
    binding = {
        "exit_family_primary": "scale_out",
        "exit_families_ranked": ["runner", "time_stop"],
    }
    res = resolve_exit_family_resolution(db_row=db_row, end_decision_binding=binding)
    assert res["version"] == EXIT_FAMILY_RESOLUTION_VERSION
    assert res["primary"] == "news_risk_flatten"
    ranked = res["ranked"]
    assert "news_risk_flatten" in ranked
    assert "trend_follow_runner" in ranked
    assert "liquidity_target" in ranked
    assert "basis_funding_unwind" in ranked
    assert "mean_reversion_snapback" in ranked
    assert "driver_news_score_ge_70" in res["drivers"]
    hints = res["execution_hints"]
    assert hints.get("take_pct_profile") == "flatten_fast"


def test_extract_exit_execution_hints_from_nested_dcf() -> None:
    trace = {
        "decision_control_flow": {
            "exit_family_resolution": {
                "execution_hints": {
                    "take_pct_profile": "runner_heavy",
                    "runner_enabled": True,
                }
            }
        }
    }
    h = extract_exit_execution_hints_from_trace(trace)
    assert h is not None
    assert h.get("take_pct_profile") == "runner_heavy"
