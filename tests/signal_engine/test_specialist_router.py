from __future__ import annotations

from shared_py.bitget.instruments import BitgetInstrumentIdentity
from signal_engine.specialists import build_specialist_stack


def test_specialist_router_blocks_spot_short() -> None:
    instrument = BitgetInstrumentIdentity(
        market_family="spot",
        symbol="BTCUSDT",
        margin_account_mode="cash",
        public_ws_inst_type="SPOT",
        private_ws_inst_type="SPOT",
        metadata_source="test",
        metadata_verified=True,
    )
    out = build_specialist_stack(
        signal_row={
            "direction": "short",
            "market_regime": "trend",
            "regime_state": "trend",
            "signal_class": "gross",
            "trade_action": "allow_trade",
            "meta_trade_lane": "candidate_for_live",
        },
        instrument=instrument,
    )
    assert "spot_short_not_supported" in out["family_specialist"]["blockers"]
    assert out["router_arbitration"]["selected_trade_action"] == "do_not_trade"
    assert out["playbook_context"]["decision_mode"] in {"selected", "playbookless"}


def test_specialist_router_selects_trend_playbook_for_futures() -> None:
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
            "signal_class": "gross",
            "trade_action": "allow_trade",
            "meta_trade_lane": "candidate_for_live",
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
    assert out["playbook_specialist"]["playbook_id"] == "trend_continuation_core"
    assert out["playbook_specialist"]["playbook_family"] == "trend_continuation"
    assert out["router_arbitration"]["operator_gate_required"] is True


def test_specialist_router_selects_carry_playbook_for_futures_funding_edge() -> None:
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
            "market_regime": "chop",
            "regime_state": "funding_skewed",
            "regime_bias": "neutral",
            "signal_class": "kern",
            "trade_action": "allow_trade",
            "timeframe": "1H",
            "analysis_ts_ms": 1_700_000_000_000,
            "source_snapshot_json": {
                "feature_snapshot": {
                    "primary_tf": {
                        "funding_rate_bps": 2.4,
                        "basis_bps": 3.1,
                        "event_distance_ms": 900000,
                        "feature_quality_status": "ok",
                        "liquidity_source": "orderbook_levels",
                        "spread_bps": 1.1,
                        "execution_cost_bps": 2.4,
                        "depth_to_bar_volume_ratio": 0.45,
                        "data_completeness_0_1": 0.92,
                        "staleness_score_0_1": 0.08,
                    }
                }
            },
        },
        instrument=instrument,
    )
    assert out["playbook_specialist"]["playbook_id"] == "carry_funding_capture"
    assert out["playbook_specialist"]["playbook_family"] == "carry_funding"
    assert out["playbook_context"]["benchmark_rule_ids"]


def test_specialist_router_blocks_trade_when_no_registered_playbook_fits() -> None:
    instrument = BitgetInstrumentIdentity(
        market_family="margin",
        symbol="BTCUSDT",
        margin_account_mode="isolated",
        public_ws_inst_type="MARGIN",
        private_ws_inst_type="MARGIN",
        metadata_source="test",
        metadata_verified=True,
        supports_leverage=True,
    )
    out = build_specialist_stack(
        signal_row={
            "direction": "neutral",
            "market_regime": "unknown",
            "regime_state": "unknown",
            "signal_class": "warnung",
            "trade_action": "allow_trade",
            "timeframe": "4H",
            "source_snapshot_json": {
                "feature_snapshot": {
                    "primary_tf": {
                        "feature_quality_status": "degraded",
                        "spread_bps": 1.0,
                        "execution_cost_bps": 2.0,
                        "depth_to_bar_volume_ratio": 0.5,
                        "data_completeness_0_1": 0.9,
                        "staleness_score_0_1": 0.9,
                    }
                }
            },
        },
        instrument=instrument,
    )
    assert out["playbook_context"]["decision_mode"] == "playbookless"
    assert out["router_arbitration"]["selected_trade_action"] == "do_not_trade"
    assert (
        "playbook_selection_missing_for_trade" in out["router_arbitration"]["reasons"]
    )
