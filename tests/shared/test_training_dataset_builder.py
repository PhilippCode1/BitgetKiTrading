from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
SHARED_SRC = ROOT / "shared" / "python" / "src"
if SHARED_SRC.is_dir() and str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from shared_py.model_contracts import (
    build_feature_snapshot,
    build_model_output_snapshot,
)
from shared_py.training_dataset_builder import (
    TakeTradeDatasetBuildConfig,
    build_take_trade_training_dataset,
    feature_snapshot_asof_ms,
    take_trade_dataset_config_fingerprint,
)


def _feature_row(*, timeframe: str, decision_ts_ms: int) -> dict[str, object]:
    return {
        "canonical_instrument_id": "bitget-futures-btcusdt",
        "market_family": "futures",
        "product_type": "USDT-FUTURES",
        "margin_account_mode": "isolated",
        "instrument_metadata_snapshot_id": "snapshot-1",
        "symbol": "BTCUSDT",
        "timeframe": timeframe,
        "start_ts_ms": decision_ts_ms - 60_000,
        "atr_14": 100.0,
        "atrp_14": 0.1,
        "rsi_14": 50.0,
        "ret_1": 0.0,
        "ret_5": 0.0,
        "momentum_score": 0.0,
        "impulse_body_ratio": 0.5,
        "impulse_upper_wick_ratio": 0.2,
        "impulse_lower_wick_ratio": 0.2,
        "range_score": 50.0,
        "trend_ema_fast": 100_000.0,
        "trend_ema_slow": 99_900.0,
        "trend_slope_proxy": 0.0,
        "trend_dir": 0,
        "confluence_score_0_100": 50.0,
        "vol_z_50": 0.0,
        "spread_bps": 2.0,
        "bid_depth_usdt_top25": 200_000.0,
        "ask_depth_usdt_top25": 200_000.0,
        "orderbook_imbalance": 0.0,
        "depth_balance_ratio": 1.0,
        "depth_to_bar_volume_ratio": 1.0,
        "impact_buy_bps_5000": 2.0,
        "impact_sell_bps_5000": 2.0,
        "impact_buy_bps_10000": 3.0,
        "impact_sell_bps_10000": 3.0,
        "execution_cost_bps": 2.0,
        "volatility_cost_bps": 2.0,
        "funding_rate": 0.0,
        "funding_rate_bps": 1.0,
        "funding_cost_bps_window": 0.0,
        "funding_time_to_next_ms": 600_000,
        "open_interest": 1_000_000.0,
        "open_interest_change_pct": 0.0,
        "mark_index_spread_bps": 0.8,
        "basis_bps": 1.1,
        "session_drift_bps": 9.0,
        "spread_persistence_bps": 2.2,
        "mean_reversion_pressure_0_100": 37.0,
        "breakout_compression_score_0_100": 55.0,
        "realized_vol_cluster_0_100": 44.0,
        "liquidation_distance_bps_max_leverage": 106.0,
        "data_completeness_0_1": 0.9,
        "staleness_score_0_1": 0.2,
        "gap_count_lookback": 0,
        "event_distance_ms": 600_000,
        "feature_quality_status": "ok",
        "orderbook_age_ms": 1_000,
        "funding_age_ms": 10_000,
        "open_interest_age_ms": 10_000,
        "liquidity_source": "orderbook_levels",
        "funding_source": "x",
        "open_interest_source": "y",
        "source_event_id": "e1",
        "computed_ts_ms": decision_ts_ms - 5_000,
    }


def _good_row(*, decision_ts_ms: int = 1_800_000_000_000) -> dict[str, object]:
    tfs = {
        "1m": _feature_row(timeframe="1m", decision_ts_ms=decision_ts_ms),
        "5m": _feature_row(timeframe="5m", decision_ts_ms=decision_ts_ms),
        "15m": _feature_row(timeframe="15m", decision_ts_ms=decision_ts_ms),
        "1H": _feature_row(timeframe="1H", decision_ts_ms=decision_ts_ms),
        "4H": _feature_row(timeframe="4H", decision_ts_ms=decision_ts_ms),
    }
    snap = build_feature_snapshot(
        primary_timeframe="5m", primary_feature=tfs["5m"], features_by_tf=tfs
    )
    signal = build_model_output_snapshot(
        {
            "signal_id": str(uuid4()),
            "symbol": "BTCUSDT",
            "timeframe": "5m",
            "analysis_ts_ms": decision_ts_ms,
            "market_regime": "chop",
            "regime_bias": "neutral",
            "direction": "long",
            "signal_strength_0_100": 55.0,
            "probability_0_1": 0.5,
            "signal_class": "kern",
            "decision_state": "accepted",
        }
    )
    return {
        "paper_trade_id": str(uuid4()),
        "decision_ts_ms": decision_ts_ms,
        "market_regime": "chop",
        "take_trade_label": True,
        "signal_snapshot_json": signal,
        "feature_snapshot_json": snap,
    }


def test_config_fingerprint_stable() -> None:
    a = take_trade_dataset_config_fingerprint(TakeTradeDatasetBuildConfig())
    b = take_trade_dataset_config_fingerprint(
        TakeTradeDatasetBuildConfig(max_feature_age_ms=3_600_000)
    )
    assert a == b


def test_feature_snapshot_asof_ms() -> None:
    row = _good_row()
    assert feature_snapshot_asof_ms(row) == int(row["decision_ts_ms"]) - 5_000


def test_stale_gate_drops_row() -> None:
    row = _good_row(decision_ts_ms=1_800_000_000_000)
    cfg = TakeTradeDatasetBuildConfig(
        max_feature_age_ms=1_000, drop_on_stale_features=True
    )
    examples, report = build_take_trade_training_dataset([dict(row)], cfg)
    assert examples == []
    assert report.dropped.get("stale_features") == 1


def test_future_feature_gate_drops_row() -> None:
    row = dict(_good_row(decision_ts_ms=1_800_000_000_000))
    fs = dict(row["feature_snapshot_json"])
    primary = dict(fs["primary_tf"])
    primary["computed_ts_ms"] = int(row["decision_ts_ms"]) + 400_000
    fs["primary_tf"] = primary
    row["feature_snapshot_json"] = fs
    cfg = TakeTradeDatasetBuildConfig(future_feature_slack_ms=60_000)
    examples, report = build_take_trade_training_dataset([row], cfg)
    assert examples == []
    assert report.dropped.get("feature_ts_after_decision_leak") == 1


def test_leak_key_drops_row() -> None:
    row = dict(_good_row())
    sig = dict(row["signal_snapshot_json"])
    sig["take_trade_prob"] = 0.88
    row["signal_snapshot_json"] = sig
    examples, report = build_take_trade_training_dataset(
        [row], TakeTradeDatasetBuildConfig()
    )
    assert examples == []
    assert report.dropped.get("signal_snapshot_leak_keys") == 1
