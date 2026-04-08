from __future__ import annotations

import math
import sys
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[2]
LEARNING_SRC = ROOT / "services" / "learning-engine" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for candidate in (LEARNING_SRC, SHARED_SRC):
    candidate_str = str(candidate)
    if candidate.is_dir() and candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from learning_engine.config import LearningEngineSettings
from learning_engine.meta_models.target_bps import train_expected_bps_models
from learning_engine.storage import repo_model_runs
from shared_py.model_contracts import build_feature_snapshot, build_model_output_snapshot


@pytest.fixture
def learning_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> LearningEngineSettings:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("EXPECTED_BPS_MODEL_ARTIFACTS_DIR", str(tmp_path / "expected-bps"))
    return LearningEngineSettings()


def test_train_expected_bps_models_write_artifacts_and_metrics(
    learning_settings: LearningEngineSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [_evaluation_row(i) for i in range(132)]
    inserted: list[dict[str, object]] = []
    cleared: list[str] = []

    monkeypatch.setattr(
        repo_model_runs,
        "fetch_target_training_rows",
        lambda _conn, target_field, symbol=None: rows,
    )
    monkeypatch.setattr(
        repo_model_runs,
        "clear_promoted_model",
        lambda _conn, model_name: cleared.append(model_name),
    )
    monkeypatch.setattr(
        repo_model_runs,
        "insert_model_run",
        lambda _conn, **kwargs: inserted.append(kwargs),
    )

    report = train_expected_bps_models(object(), learning_settings)

    for _name, model_report in report["models"].items():
        assert "data_version_hash" in model_report
        assert "cv_report" in model_report
        assert model_report["cv_report"]["summary"]["walk_forward_mean_mae_bps"] is not None

    assert set(report["models"]) == {
        "expected_return_bps",
        "expected_mae_bps",
        "expected_mfe_bps",
    }
    assert cleared == ["expected_return_bps", "expected_mae_bps", "expected_mfe_bps"]
    assert len(inserted) == 3
    for output_field, model_report in report["models"].items():
        artifact_path = ROOT / str(model_report["artifact_path"])
        assert artifact_path.is_file()
        adir = artifact_path.parent
        assert (adir / "training_manifest.json").is_file()
        assert (adir / "run_manifest.json").is_file()
        assert (adir / "cv_report.json").is_file()
        assert model_report["rows"]["total"] == len(rows)
        assert model_report["rows"]["train"] > 0
        assert model_report["rows"]["test"] > 0
        assert math.isfinite(float(model_report["metrics"]["mae_bps"]))
        assert math.isfinite(float(model_report["metrics"]["rmse_bps"]))
        assert len(model_report["regime_metrics"]) >= 2
        assert model_report["prediction_bounds_bps"]["upper"] > model_report["prediction_bounds_bps"][
            "lower"
        ]
        inserted_row = next(item for item in inserted if item["output_field"] == output_field)
        metadata = inserted_row["metadata_json"]
        assert isinstance(metadata, dict)
        assert metadata["feature_contract"]["output_field"] == output_field
        assert "feature_reference" in metadata
        assert "signal_strength_0_100" in metadata["feature_reference"]["numeric_fields"]
        assert metadata["metrics"]["mae_bps"] == model_report["metrics"]["mae_bps"]
        if output_field == "expected_return_bps":
            assert metadata["scaling_method"] == "asinh_clip"
        else:
            assert metadata["scaling_method"] == "log1p_clip"


def _evaluation_row(index: int) -> dict[str, object]:
    shock = index % 11 == 0
    missing_liquidity = index % 7 == 0
    long_bias = index % 2 == 0
    regime = "shock" if shock else "trend" if long_bias else "chop"
    direction = "long" if long_bias else "short"
    funding_bps = 24.0 if shock else 0.8 + (index % 5) * 0.4
    signal_strength = 79.0 if long_bias else 47.0
    heuristic_prob = 0.74 if long_bias else 0.38
    news_score = 95.0 if shock else 48.0
    risk_score = 42.0 if shock else 64.0 if long_bias else 52.0
    expected_return = 28.0 if long_bias else -9.0
    expected_return -= funding_bps * 0.7
    if missing_liquidity:
        expected_return -= 11.0
    if shock:
        expected_return -= 18.0
    expected_mae = 26.0 + funding_bps * 0.8 + (12.0 if missing_liquidity else 0.0) + (
        18.0 if shock else 0.0
    )
    expected_mfe = max(expected_mae + 6.0, 58.0 + (18.0 if long_bias else -4.0) - (10.0 if shock else 0.0))

    feature_rows = {
        "1m": _feature_row("1m", index, long_bias, missing_liquidity, shock, funding_bps),
        "5m": _feature_row("5m", index, long_bias, missing_liquidity, shock, funding_bps),
        "15m": _feature_row("15m", index, long_bias, missing_liquidity, shock, funding_bps),
        "1H": _feature_row("1H", index, long_bias, missing_liquidity, shock, funding_bps),
        "4H": _feature_row("4H", index, long_bias, missing_liquidity, shock, funding_bps),
    }
    signal_snapshot = build_model_output_snapshot(
        {
            "signal_id": str(uuid4()),
            "symbol": "BTCUSDT",
            "timeframe": "5m",
            "analysis_ts_ms": 1_700_000_000_000 + index * 60_000,
            "market_regime": regime,
            "regime_bias": "long" if long_bias else "short",
            "regime_confidence_0_1": 0.91 if shock else 0.82 if long_bias else 0.57,
            "regime_reasons_json": [f"regime={regime}"],
            "direction": direction,
            "signal_strength_0_100": signal_strength,
            "probability_0_1": heuristic_prob,
            "signal_class": "gross" if long_bias else "kern",
            "structure_score_0_100": 74.0 if long_bias else 49.0,
            "momentum_score_0_100": 69.0 if long_bias else 41.0,
            "multi_timeframe_score_0_100": 73.0 if long_bias else 43.0,
            "news_score_0_100": news_score,
            "risk_score_0_100": risk_score,
            "history_score_0_100": 54.0 if long_bias else 47.0,
            "weighted_composite_score_0_100": 71.0 if long_bias else 44.0,
            "rejection_state": False,
            "rejection_reasons_json": [],
            "decision_state": "accepted" if expected_return > 0 else "downgraded",
            "reasons_json": {},
            "reward_risk_ratio": 1.9 if long_bias else 1.1,
            "expected_volatility_band": 0.16 if shock else 0.10,
            "scoring_model_version": "v1.0.0",
        }
    )
    feature_snapshot = build_feature_snapshot(
        primary_timeframe="5m",
        primary_feature=feature_rows["5m"],
        features_by_tf=feature_rows,
    )
    return {
        "paper_trade_id": str(uuid4()),
        "decision_ts_ms": 1_700_000_000_000 + index * 60_000,
        "market_regime": regime,
        "expected_return_bps": expected_return,
        "expected_mae_bps": expected_mae,
        "expected_mfe_bps": expected_mfe,
        "signal_snapshot_json": signal_snapshot,
        "feature_snapshot_json": feature_snapshot,
    }


def _feature_row(
    timeframe: str,
    index: int,
    long_bias: bool,
    missing_liquidity: bool,
    shock: bool,
    funding_bps: float,
) -> dict[str, object]:
    return {
        "symbol": "BTCUSDT",
        "timeframe": timeframe,
        "start_ts_ms": 1_700_000_000_000 + index * 60_000,
        "atr_14": 90.0 + index,
        "atrp_14": 0.14 if shock else 0.08,
        "rsi_14": 61.0 if long_bias else 44.0,
        "ret_1": 0.0025 if long_bias else -0.0016,
        "ret_5": 0.006 if long_bias else -0.003,
        "momentum_score": 66.0 if long_bias else -14.0,
        "impulse_body_ratio": 0.62 if long_bias else 0.33,
        "impulse_upper_wick_ratio": 0.18,
        "impulse_lower_wick_ratio": 0.24,
        "range_score": 24.0 if long_bias else 64.0,
        "trend_ema_fast": 100_200.0 + index,
        "trend_ema_slow": 100_000.0 + index,
        "trend_slope_proxy": 14.0 if long_bias else -5.0,
        "trend_dir": 1 if long_bias else -1,
        "confluence_score_0_100": 80.0 if long_bias else 42.0,
        "vol_z_50": 0.7 if shock else 0.3,
        "spread_bps": 4.4 if missing_liquidity else 1.5,
        "bid_depth_usdt_top25": None if missing_liquidity else 260_000.0,
        "ask_depth_usdt_top25": None if missing_liquidity else 255_000.0,
        "orderbook_imbalance": 0.03 if long_bias else -0.03,
        "depth_balance_ratio": 0.98 if not missing_liquidity else 0.72,
        "depth_to_bar_volume_ratio": 0.25 if missing_liquidity else 1.6,
        "impact_buy_bps_5000": 7.5 if missing_liquidity else 2.1,
        "impact_sell_bps_5000": 7.1 if missing_liquidity else 1.9,
        "impact_buy_bps_10000": 10.0 if missing_liquidity else 3.6,
        "impact_sell_bps_10000": 9.4 if missing_liquidity else 3.2,
        "execution_cost_bps": 8.4 if missing_liquidity else 2.6,
        "volatility_cost_bps": 9.2 if shock else 3.1,
        "funding_rate": funding_bps / 10_000.0,
        "funding_rate_bps": funding_bps,
        "funding_cost_bps_window": funding_bps * 0.2,
        "open_interest": 1_150_000.0 + index,
        "open_interest_change_pct": 10.0 if shock else 4.0 if long_bias else -2.5,
        "orderbook_age_ms": 2_000,
        "funding_age_ms": 30_000,
        "open_interest_age_ms": 5_000,
        "liquidity_source": None if missing_liquidity else "orderbook_levels",
        "funding_source": "" if shock else "bitget_rest_funding",
        "open_interest_source": "bitget_rest_open_interest",
        "source_event_id": f"evt-{timeframe}-{index}",
        "computed_ts_ms": 1_700_000_010_000 + index * 60_000,
    }
