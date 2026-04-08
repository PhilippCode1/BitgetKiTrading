from __future__ import annotations

import sys
from pathlib import Path

from joblib import dump

ROOT = Path(__file__).resolve().parents[2]
SERVICE_SRC = ROOT / "services" / "signal-engine" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for candidate in (SERVICE_SRC, SHARED_SRC):
    candidate_str = str(candidate)
    if candidate.is_dir() and candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from signal_engine.take_trade_model import TakeTradeModelScorer

from shared_py.model_contracts import build_feature_snapshot


class _DummyPredictor:
    def predict_proba(self, X):
        scores = []
        for row in X:
            base = float(row[0]) / 100.0
            prob = min(0.95, max(0.05, 0.2 + base * 0.7))
            scores.append([1.0 - prob, prob])
        return scores


class _FakeRepo:
    def __init__(self, row):
        self._row = row

    def fetch_latest_promoted_model_run(self, *, model_name: str):
        assert model_name == "take_trade_prob"
        return dict(self._row)

    def fetch_production_model_run(self, *, model_name: str, **kwargs: object):
        return self.fetch_latest_promoted_model_run(model_name=model_name)


def test_take_trade_model_scorer_loads_promoted_artifact(tmp_path: Path) -> None:
    model_path = tmp_path / "model.joblib"
    dump(_DummyPredictor(), model_path)
    repo = _FakeRepo(
        {
            "run_id": "00000000-0000-4000-8000-0000000000aa",
            "model_name": "take_trade_prob",
            "version": "hgb-cal-1700000000000",
            "dataset_hash": "abc123",
            "artifact_path": str(model_path),
            "calibration_method": "sigmoid",
            "metrics_json": {
                "brier_score": 0.14,
                "roc_auc": 0.72,
                "average_precision": 0.70,
            },
            "metadata_json": {
                "trained_at_ms": 1_700_000_000_000,
                "feature_contract": {"schema_hash": "feat-hash"},
                "feature_reference": {
                    "numeric_fields": {
                        "signal_strength_0_100": {
                            "p05": 40.0,
                            "p95": 90.0,
                            "iqr": 15.0,
                        }
                    }
                },
            },
        }
    )
    scorer = TakeTradeModelScorer(
        repo,
        refresh_ms=1,
        ood_robust_z_threshold=6.0,
        ood_max_flagged_features=2,
    )
    feature_snapshot = build_feature_snapshot(
        primary_timeframe="5m",
        primary_feature=_feature_row("5m"),
        features_by_tf={
            "1m": _feature_row("1m"),
            "5m": _feature_row("5m"),
            "15m": _feature_row("15m"),
            "1H": _feature_row("1H"),
            "4H": _feature_row("4H"),
        },
    )
    prediction = scorer.predict(
        signal_row={
            "timeframe": "5m",
            "market_regime": "trend",
            "regime_bias": "long",
            "regime_confidence_0_1": 0.82,
            "direction": "long",
            "signal_strength_0_100": 78.0,
            "probability_0_1": 0.72,
            "signal_class": "gross",
            "structure_score_0_100": 74.0,
            "momentum_score_0_100": 68.0,
            "multi_timeframe_score_0_100": 72.0,
            "news_score_0_100": 50.0,
            "risk_score_0_100": 63.0,
            "history_score_0_100": 54.0,
            "weighted_composite_score_0_100": 71.0,
            "decision_state": "accepted",
            "reasons_json": {},
            "reward_risk_ratio": 1.8,
            "expected_volatility_band": 0.11,
        },
        feature_snapshot=feature_snapshot,
    )
    assert 0.0 <= float(prediction["take_trade_prob"]) <= 1.0
    assert prediction["take_trade_model_version"] == "hgb-cal-1700000000000"
    assert (
        prediction["take_trade_model_run_id"] == "00000000-0000-4000-8000-0000000000aa"
    )
    assert prediction["take_trade_model_info"]["feature_schema_hash"] == "feat-hash"
    assert prediction["take_trade_model_diagnostics"]["ood_alert"] is False


def _feature_row(timeframe: str) -> dict[str, object]:
    return {
        "symbol": "BTCUSDT",
        "timeframe": timeframe,
        "start_ts_ms": 1_700_000_000_000,
        "atr_14": 100.0,
        "atrp_14": 0.11,
        "rsi_14": 58.0,
        "ret_1": 0.002,
        "ret_5": 0.006,
        "momentum_score": 63.0,
        "impulse_body_ratio": 0.58,
        "impulse_upper_wick_ratio": 0.21,
        "impulse_lower_wick_ratio": 0.19,
        "range_score": 30.0,
        "trend_ema_fast": 100_200.0,
        "trend_ema_slow": 100_000.0,
        "trend_slope_proxy": 11.0,
        "trend_dir": 1,
        "confluence_score_0_100": 75.0,
        "vol_z_50": 0.4,
        "spread_bps": 1.4,
        "bid_depth_usdt_top25": 200_000.0,
        "ask_depth_usdt_top25": 210_000.0,
        "orderbook_imbalance": 0.03,
        "depth_balance_ratio": 0.99,
        "depth_to_bar_volume_ratio": 1.5,
        "impact_buy_bps_5000": 2.1,
        "impact_sell_bps_5000": 1.9,
        "impact_buy_bps_10000": 3.4,
        "impact_sell_bps_10000": 3.1,
        "execution_cost_bps": 2.6,
        "volatility_cost_bps": 2.9,
        "funding_rate": 0.0001,
        "funding_rate_bps": 0.9,
        "funding_cost_bps_window": 0.08,
        "open_interest": 1_100_000.0,
        "open_interest_change_pct": 3.6,
        "orderbook_age_ms": 2_000,
        "funding_age_ms": 30_000,
        "open_interest_age_ms": 5_000,
        "liquidity_source": "orderbook_levels",
        "funding_source": "bitget_rest_funding",
        "open_interest_source": "bitget_rest_open_interest",
        "source_event_id": f"evt-{timeframe}",
        "computed_ts_ms": 1_700_000_010_000,
    }
