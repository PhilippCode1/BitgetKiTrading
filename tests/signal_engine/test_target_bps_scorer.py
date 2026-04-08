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

from signal_engine.target_bps_models import TargetBpsModelScorer

from shared_py.model_contracts import build_feature_snapshot


class _DummyRegressor:
    def __init__(self, *, offset: float, scale: float) -> None:
        self._offset = offset
        self._scale = scale

    def predict(self, X):
        out = []
        for row in X:
            base = float(row[0]) / 100.0
            out.append(self._offset + base * self._scale)
        return out


class _FakeRepo:
    def __init__(self, rows):
        self._rows = rows

    def fetch_latest_promoted_model_run(self, *, model_name: str):
        return dict(self._rows[model_name])

    def fetch_production_model_run(self, *, model_name: str, **kwargs: object):
        return self.fetch_latest_promoted_model_run(model_name=model_name)


def test_target_bps_model_scorer_loads_promoted_artifacts_with_edge_features(
    tmp_path: Path,
) -> None:
    return_path = tmp_path / "return.joblib"
    mae_path = tmp_path / "mae.joblib"
    mfe_path = tmp_path / "mfe.joblib"
    dump(_DummyRegressor(offset=6.0, scale=18.0), return_path)
    dump(_DummyRegressor(offset=18.0, scale=22.0), mae_path)
    dump(_DummyRegressor(offset=42.0, scale=28.0), mfe_path)
    repo = _FakeRepo(
        {
            "expected_return_bps": {
                "run_id": "00000000-0000-4000-8000-0000000000a1",
                "model_name": "expected_return_bps",
                "version": "hgb-reg-1700000000000",
                "dataset_hash": "ret-hash",
                "artifact_path": str(return_path),
                "metrics_json": {"mae_bps": 11.0, "rmse_bps": 15.0},
                "metadata_json": {
                    "trained_at_ms": 1_700_000_000_000,
                    "scaling_method": "asinh_clip",
                    "feature_contract": {"schema_hash": "feat-hash"},
                    "feature_reference": {
                        "numeric_fields": {
                            "signal_strength_0_100": {
                                "p05": 45.0,
                                "p95": 90.0,
                                "iqr": 18.0,
                            }
                        }
                    },
                    "prediction_lower_bound_bps": -60.0,
                    "prediction_upper_bound_bps": 80.0,
                },
            },
            "expected_mae_bps": {
                "run_id": "00000000-0000-4000-8000-0000000000a2",
                "model_name": "expected_mae_bps",
                "version": "hgb-reg-1700000000001",
                "dataset_hash": "mae-hash",
                "artifact_path": str(mae_path),
                "metrics_json": {"mae_bps": 9.0, "rmse_bps": 12.0},
                "metadata_json": {
                    "trained_at_ms": 1_700_000_000_010,
                    "scaling_method": "log1p_clip",
                    "feature_contract": {"schema_hash": "feat-hash"},
                    "feature_reference": {
                        "numeric_fields": {
                            "signal_strength_0_100": {
                                "p05": 45.0,
                                "p95": 90.0,
                                "iqr": 18.0,
                            }
                        }
                    },
                    "prediction_lower_bound_bps": 0.0,
                    "prediction_upper_bound_bps": 120.0,
                },
            },
            "expected_mfe_bps": {
                "run_id": "00000000-0000-4000-8000-0000000000a3",
                "model_name": "expected_mfe_bps",
                "version": "hgb-reg-1700000000002",
                "dataset_hash": "mfe-hash",
                "artifact_path": str(mfe_path),
                "metrics_json": {"mae_bps": 10.0, "rmse_bps": 14.0},
                "metadata_json": {
                    "trained_at_ms": 1_700_000_000_020,
                    "scaling_method": "log1p_clip",
                    "feature_contract": {"schema_hash": "feat-hash"},
                    "feature_reference": {
                        "numeric_fields": {
                            "signal_strength_0_100": {
                                "p05": 45.0,
                                "p95": 90.0,
                                "iqr": 18.0,
                            }
                        }
                    },
                    "prediction_lower_bound_bps": 0.0,
                    "prediction_upper_bound_bps": 180.0,
                },
            },
        }
    )
    scorer = TargetBpsModelScorer(
        repo,
        refresh_ms=1,
        ood_robust_z_threshold=6.0,
        ood_max_flagged_features=2,
    )
    feature_snapshot = build_feature_snapshot(
        primary_timeframe="5m",
        primary_feature=_feature_row("5m", missing_liquidity=True, shock=True),
        features_by_tf={
            "1m": _feature_row("1m", missing_liquidity=True, shock=True),
            "5m": _feature_row("5m", missing_liquidity=True, shock=True),
            "15m": _feature_row("15m", missing_liquidity=True, shock=True),
            "1H": _feature_row("1H", missing_liquidity=True, shock=True),
            "4H": _feature_row("4H", missing_liquidity=True, shock=True),
        },
    )
    prediction = scorer.predict(
        signal_row={
            "timeframe": "5m",
            "market_regime": "shock",
            "regime_bias": "long",
            "regime_confidence_0_1": 0.91,
            "direction": "long",
            "signal_strength_0_100": 82.0,
            "probability_0_1": 0.69,
            "signal_class": "gross",
            "structure_score_0_100": 72.0,
            "momentum_score_0_100": 65.0,
            "multi_timeframe_score_0_100": 71.0,
            "news_score_0_100": 97.0,
            "risk_score_0_100": 41.0,
            "history_score_0_100": 49.0,
            "weighted_composite_score_0_100": 68.0,
            "decision_state": "accepted",
            "reasons_json": {},
            "reward_risk_ratio": 1.4,
            "expected_volatility_band": 0.18,
        },
        feature_snapshot=feature_snapshot,
    )
    assert prediction["expected_return_bps"] is not None
    assert prediction["expected_mae_bps"] is not None
    assert prediction["expected_mfe_bps"] is not None
    assert len(prediction["target_projection_models_json"]) == 3
    assert (
        prediction["target_projection_models_json"][0]["feature_schema_hash"]
        == "feat-hash"
    )
    assert (
        prediction["target_projection_summary"]["reward_to_adverse_ratio"] is not None
    )
    assert prediction["target_projection_diagnostics"]["ood_alert"] is False
    adj = prediction.get("target_projection_adjusted")
    assert isinstance(adj, dict)
    assert adj.get("round_trip_cost_bps", 0) > 0
    raw = prediction["target_projection_summary"].get("model_raw_bps")
    assert isinstance(raw, dict)
    assert raw.get("expected_return_bps") is not None
    assert prediction["expected_return_bps"] is not None
    assert prediction["expected_return_bps"] <= raw["expected_return_bps"]


def _feature_row(
    timeframe: str, *, missing_liquidity: bool, shock: bool
) -> dict[str, object]:
    return {
        "symbol": "BTCUSDT",
        "timeframe": timeframe,
        "start_ts_ms": 1_700_000_000_000,
        "atr_14": 105.0,
        "atrp_14": 0.17 if shock else 0.09,
        "rsi_14": 59.0,
        "ret_1": 0.0018,
        "ret_5": 0.0048,
        "momentum_score": 61.0,
        "impulse_body_ratio": 0.54,
        "impulse_upper_wick_ratio": 0.24,
        "impulse_lower_wick_ratio": 0.22,
        "range_score": 34.0,
        "trend_ema_fast": 100_200.0,
        "trend_ema_slow": 100_000.0,
        "trend_slope_proxy": 11.0,
        "trend_dir": 1,
        "confluence_score_0_100": 73.0,
        "vol_z_50": 0.8 if shock else 0.3,
        "spread_bps": 5.2 if missing_liquidity else 1.5,
        "bid_depth_usdt_top25": None if missing_liquidity else 220_000.0,
        "ask_depth_usdt_top25": None if missing_liquidity else 210_000.0,
        "orderbook_imbalance": 0.02,
        "depth_balance_ratio": 0.72 if missing_liquidity else 0.98,
        "depth_to_bar_volume_ratio": 0.28 if missing_liquidity else 1.5,
        "impact_buy_bps_5000": 8.0 if missing_liquidity else 2.0,
        "impact_sell_bps_5000": 7.8 if missing_liquidity else 1.9,
        "impact_buy_bps_10000": 10.4 if missing_liquidity else 3.4,
        "impact_sell_bps_10000": 10.1 if missing_liquidity else 3.1,
        "execution_cost_bps": 8.1 if missing_liquidity else 2.6,
        "volatility_cost_bps": 9.5 if shock else 2.9,
        "funding_rate": 0.0024,
        "funding_rate_bps": 24.0,
        "funding_cost_bps_window": 4.8,
        "open_interest": 1_100_000.0,
        "open_interest_change_pct": 9.0,
        "orderbook_age_ms": 2_000,
        "funding_age_ms": 30_000,
        "open_interest_age_ms": 5_000,
        "liquidity_source": None if missing_liquidity else "orderbook_levels",
        "funding_source": "" if shock else "bitget_rest_funding",
        "open_interest_source": "bitget_rest_open_interest",
        "source_event_id": f"evt-{timeframe}",
        "computed_ts_ms": 1_700_000_010_000,
    }
