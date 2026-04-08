from __future__ import annotations

from shared_py.bitget.instruments import BitgetInstrumentIdentity
from signal_engine.specialists import build_specialist_stack


def test_ensemble_adversary_ood_vetoes_allow_trade() -> None:
    instrument = BitgetInstrumentIdentity(
        market_family="futures",
        symbol="BTCUSDT",
        product_type="USDT-FUTURES",
        margin_account_mode="isolated",
        public_ws_inst_type="USDT-FUTURES",
        private_ws_inst_type="USDT-FUTURES",
        metadata_source="test",
        metadata_verified=True,
    )
    out = build_specialist_stack(
        signal_row={
            "direction": "long",
            "market_regime": "trend",
            "regime_state": "trend",
            "regime_bias": "long",
            "regime_confidence_0_1": 0.8,
            "signal_class": "gross",
            "trade_action": "allow_trade",
            "decision_state": "accepted",
            "decision_confidence_0_1": 0.82,
            "model_ood_score_0_1": 0.91,
            "model_ood_alert": False,
            "model_uncertainty_0_1": 0.25,
            "meta_trade_lane": "paper_candidate",
            "timeframe": "5m",
            "source_snapshot_json": {
                "feature_snapshot": {
                    "primary_tf": {
                        "trend_dir": 1,
                        "confluence_score_0_100": 78.0,
                        "feature_quality_status": "ok",
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
        instrument=instrument,
    )
    assert out["adversary_check"]["hard_veto_recommended"] is True
    assert out["router_arbitration"]["pre_adversary_trade_action"] == "allow_trade"
    assert out["router_arbitration"]["selected_trade_action"] == "do_not_trade"
    assert "ensemble_adversary_ood_veto" in out["router_arbitration"]["reasons"]
    assert out["base_model"]["proposal"]["specialist_role"] == "base"


def test_ensemble_adversary_directional_veto_regime_vs_base() -> None:
    instrument = BitgetInstrumentIdentity(
        market_family="futures",
        symbol="BTCUSDT",
        product_type="USDT-FUTURES",
        margin_account_mode="isolated",
        public_ws_inst_type="USDT-FUTURES",
        private_ws_inst_type="USDT-FUTURES",
        metadata_source="test",
        metadata_verified=True,
    )
    out = build_specialist_stack(
        signal_row={
            "direction": "long",
            "market_regime": "trend",
            "regime_state": "trend",
            "regime_bias": "short",
            "regime_confidence_0_1": 0.74,
            "signal_class": "gross",
            "trade_action": "allow_trade",
            "decision_state": "accepted",
            "decision_confidence_0_1": 0.78,
            "model_ood_score_0_1": 0.2,
            "model_uncertainty_0_1": 0.3,
            "meta_trade_lane": "paper_candidate",
            "timeframe": "5m",
            "source_snapshot_json": {
                "feature_snapshot": {
                    "primary_tf": {
                        "trend_dir": 1,
                        "confluence_score_0_100": 72.0,
                        "feature_quality_status": "ok",
                        "liquidity_source": "orderbook_levels",
                        "spread_bps": 1.1,
                        "execution_cost_bps": 2.4,
                        "depth_to_bar_volume_ratio": 0.48,
                        "data_completeness_0_1": 0.94,
                        "staleness_score_0_1": 0.09,
                    }
                }
            },
        },
        instrument=instrument,
    )
    adv = out["adversary_check"]
    assert adv.get("directional_veto_recommended") or adv.get("regime_bias_conflict_veto_recommended")
    assert out["router_arbitration"]["selected_trade_action"] == "do_not_trade"
    rsn = out["router_arbitration"]["reasons"]
    assert (
        "ensemble_adversary_directional_veto" in rsn
        or "ensemble_adversary_regime_bias_conflict" in rsn
    )
