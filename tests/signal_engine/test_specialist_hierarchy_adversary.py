from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SE_SRC = ROOT / "services" / "signal-engine" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for p in (SE_SRC, SHARED_SRC):
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from shared_py.bitget.instruments import BitgetInstrumentIdentity
from shared_py.playbook_registry import get_playbook
from shared_py.specialist_ensemble_contract import empty_proposal
from signal_engine.specialist_proposals import run_adversary_check
from signal_engine.specialists import build_specialist_stack


def _inst_fut() -> BitgetInstrumentIdentity:
    return BitgetInstrumentIdentity(
        market_family="futures",
        symbol="BTCUSDT",
        product_type="USDT-FUTURES",
        margin_account_mode="isolated",
        public_ws_inst_type="USDT-FUTURES",
        private_ws_inst_type="USDT-FUTURES",
        metadata_source="test",
        metadata_verified=True,
    )


def test_hierarchy_includes_product_liqvol_symbol_layers() -> None:
    out = build_specialist_stack(
        signal_row={
            "direction": "long",
            "market_regime": "trend",
            "regime_state": "trend",
            "regime_bias": "long",
            "signal_class": "gross",
            "trade_action": "allow_trade",
            "decision_state": "accepted",
            "decision_confidence_0_1": 0.8,
            "expected_return_bps": 12.0,
            "expected_mae_bps": 18.0,
            "expected_mfe_bps": 35.0,
            "model_ood_score_0_1": 0.1,
            "meta_trade_lane": "paper_candidate",
            "timeframe": "5m",
            "source_snapshot_json": {
                "feature_snapshot": {
                    "primary_tf": {
                        "trend_dir": 1,
                        "confluence_score_0_100": 78.0,
                        "feature_quality_status": "ok",
                        "realized_vol_cluster_0_100": 55.0,
                        "liquidity_source": "orderbook_levels",
                        "spread_bps": 1.2,
                        "execution_cost_bps": 2.6,
                        "depth_to_bar_volume_ratio": 0.5,
                        "data_completeness_0_1": 0.95,
                        "staleness_score_0_1": 0.1,
                    }
                }
            },
        },
        instrument=_inst_fut(),
    )
    assert "product_margin_specialist" in out
    assert "liquidity_vol_cluster_specialist" in out
    assert "symbol_specialist" in out
    assert out["symbol_specialist"]["symbol_expert_mode"] == "symbol_active"
    prop = out["base_model"]["proposal"]
    assert prop.get("expected_mae_bps") == 18.0
    assert prop.get("stop_budget_hint_0_1") is not None
    assert len(out.get("ensemble_hierarchy") or []) >= 6


def test_symbol_expert_deferred_to_family_cluster_when_quality_bad() -> None:
    out = build_specialist_stack(
        signal_row={
            "direction": "long",
            "market_regime": "trend",
            "regime_state": "trend",
            "regime_bias": "long",
            "signal_class": "gross",
            "trade_action": "allow_trade",
            "decision_confidence_0_1": 0.75,
            "model_ood_score_0_1": 0.1,
            "timeframe": "5m",
            "source_snapshot_json": {
                "feature_snapshot": {
                    "primary_tf": {
                        "feature_quality_status": "degraded",
                        "data_completeness_0_1": 0.5,
                        "spread_bps": 2.0,
                    }
                }
            },
        },
        instrument=_inst_fut(),
    )
    sid = str(out["symbol_specialist"]["specialist_id"])
    assert sid.startswith("cluster:family_xs:")
    assert out["symbol_specialist"]["symbol_expert_mode"] == "cluster_family_cross_section"


def test_adversary_regime_playbook_mismatch_veto() -> None:
    pb = get_playbook("trend_continuation_core")
    assert pb is not None
    p1 = empty_proposal(role="base", specialist_id="b")
    p1["direction"] = "long"
    p1["no_trade_probability_0_1"] = 0.2
    p1["expected_edge_bps"] = 20.0
    adv = run_adversary_check(
        proposals=[p1],
        signal_row={
            "direction": "long",
            "regime_state": "mean_reverting",
            "market_regime": "chop",
        },
        playbook=pb,
        primary_feature={},
    )
    assert adv.get("regime_mismatch_veto_recommended") is True


def test_adversary_edge_dispersion_veto() -> None:
    props = []
    for i, edge in enumerate((5.0, 70.0, 80.0, 65.0)):
        p = empty_proposal(role="base", specialist_id=f"x{i}")
        p["specialist_role"] = "family" if i else "base"
        p["direction"] = "long"
        p["no_trade_probability_0_1"] = 0.15
        p["expected_edge_bps"] = edge
        props.append(p)
    adv = run_adversary_check(
        proposals=props,
        signal_row={"direction": "long", "model_ood_score_0_1": 0.1},
        playbook=None,
        primary_feature={},
    )
    assert adv.get("edge_dispersion_veto_recommended") is True
