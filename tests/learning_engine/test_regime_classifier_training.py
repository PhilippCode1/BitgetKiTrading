from __future__ import annotations

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
from learning_engine.meta_models.regime_classifier import train_market_regime_classifier
from learning_engine.storage import repo_model_runs
from shared_py.model_contracts import MARKET_REGIME_VALUES, build_feature_snapshot, build_model_output_snapshot


@pytest.fixture
def learning_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> LearningEngineSettings:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("REGIME_CLASSIFIER_MODEL_ARTIFACTS_DIR", str(tmp_path / "regime"))
    monkeypatch.setenv("REGIME_CLASSIFIER_MIN_ROWS", "100")
    monkeypatch.setenv("REGIME_CLASSIFIER_MIN_PER_CLASS", "8")
    return LearningEngineSettings()


def test_train_regime_classifier_writes_artifacts_and_cv(
    learning_settings: LearningEngineSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [_evaluation_row(i) for i in range(130)]
    inserted: dict[str, object] = {}
    cleared: list[str] = []

    monkeypatch.setattr(
        repo_model_runs,
        "fetch_regime_training_rows",
        lambda _conn, symbol=None: rows,
    )
    monkeypatch.setattr(
        repo_model_runs,
        "clear_promoted_model",
        lambda _conn, model_name: cleared.append(model_name),
    )

    def _capture_insert(_conn, **kwargs):
        inserted.update(kwargs)

    monkeypatch.setattr(repo_model_runs, "insert_model_run", _capture_insert)

    report = train_market_regime_classifier(object(), learning_settings)

    assert cleared == ["market_regime_classifier"]
    assert report["promoted"] is True
    assert "data_version_hash" in report
    assert report["cv_report"]["summary"]["walk_forward_mean_accuracy"] is not None
    artifact_path = ROOT / str(report["artifact_path"])
    assert artifact_path.is_file()
    adir = artifact_path.parent
    assert (adir / "training_manifest.json").is_file()
    assert (adir / "run_manifest.json").is_file()
    assert (adir / "cv_report.json").is_file()
    assert inserted["model_name"] == "market_regime_classifier"
    metadata = inserted["metadata_json"]
    assert isinstance(metadata, dict)
    assert metadata["feature_contract"]["schema_kind"] == "regime_model_feature_vector"
    assert "market_regime_is_" not in " ".join(metadata["feature_contract"]["fields"])


def _evaluation_row(index: int) -> dict[str, object]:
    regime = MARKET_REGIME_VALUES[index % len(MARKET_REGIME_VALUES)]
    long_bias = index % 2 == 0
    feature_rows = {
        "1m": _feature_row("1m", index, long_bias),
        "5m": _feature_row("5m", index, long_bias),
        "15m": _feature_row("15m", index, long_bias),
        "1H": _feature_row("1H", index, long_bias),
        "4H": _feature_row("4H", index, long_bias),
    }
    signal_snapshot = build_model_output_snapshot(
        {
            "signal_id": str(uuid4()),
            "symbol": "BTCUSDT",
            "timeframe": "5m",
            "analysis_ts_ms": 1_700_000_000_000 + index * 60_000,
            "market_regime": regime,
            "regime_bias": "long" if long_bias else "short",
            "regime_confidence_0_1": 0.82,
            "regime_reasons_json": [f"regime={regime}"],
            "direction": "long" if long_bias else "short",
            "signal_strength_0_100": 72.0 if long_bias else 44.0,
            "probability_0_1": 0.7 if long_bias else 0.35,
            "signal_class": "gross" if long_bias else "kern",
            "structure_score_0_100": 70.0 if long_bias else 45.0,
            "momentum_score_0_100": 65.0 if long_bias else 40.0,
            "multi_timeframe_score_0_100": 68.0 if long_bias else 42.0,
            "news_score_0_100": 50.0,
            "risk_score_0_100": 60.0 if long_bias else 50.0,
            "history_score_0_100": 52.0,
            "weighted_composite_score_0_100": 66.0 if long_bias else 43.0,
            "rejection_state": False,
            "rejection_reasons_json": [],
            "decision_state": "accepted",
            "reasons_json": {},
            "reward_risk_ratio": 1.6,
            "expected_volatility_band": 0.11,
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
        "closed_ts_ms": 1_700_000_000_000 + index * 60_000 + 120_000,
        "market_regime": regime,
        "signal_snapshot_json": signal_snapshot,
        "feature_snapshot_json": feature_snapshot,
    }


def _feature_row(timeframe: str, index: int, long_bias: bool) -> dict[str, object]:
    return {
        "symbol": "BTCUSDT",
        "timeframe": timeframe,
        "start_ts_ms": 1_700_000_000_000 + index * 60_000,
        "atr_14": 95.0 + index,
        "atrp_14": 0.1,
        "rsi_14": 55.0,
        "ret_1": 0.001,
        "ret_5": 0.003,
        "momentum_score": 50.0,
        "impulse_body_ratio": 0.5,
        "impulse_upper_wick_ratio": 0.2,
        "impulse_lower_wick_ratio": 0.2,
        "range_score": 40.0,
        "trend_ema_fast": 100_200.0,
        "trend_ema_slow": 100_000.0,
        "trend_slope_proxy": 5.0 if long_bias else -2.0,
        "trend_dir": 1 if long_bias else -1,
        "confluence_score_0_100": 60.0,
        "vol_z_50": 0.3,
        "spread_bps": 2.0,
        "bid_depth_usdt_top25": 250_000.0,
        "ask_depth_usdt_top25": 245_000.0,
        "orderbook_imbalance": 0.02,
        "depth_balance_ratio": 0.98,
        "depth_to_bar_volume_ratio": 1.4,
        "impact_buy_bps_5000": 2.5,
        "impact_sell_bps_5000": 2.4,
        "impact_buy_bps_10000": 3.5,
        "impact_sell_bps_10000": 3.3,
        "execution_cost_bps": 2.8,
        "volatility_cost_bps": 3.0,
        "funding_rate": 0.0001,
        "funding_rate_bps": 1.0,
        "funding_cost_bps_window": 0.1,
        "open_interest": 1_100_000.0,
        "open_interest_change_pct": 2.0,
        "orderbook_age_ms": 2_000,
        "funding_age_ms": 30_000,
        "open_interest_age_ms": 5_000,
        "liquidity_source": "orderbook_levels",
        "funding_source": "bitget_rest_funding",
        "open_interest_source": "bitget_rest_open_interest",
        "source_event_id": f"evt-{timeframe}-{index}",
        "computed_ts_ms": 1_700_000_010_000 + index * 60_000,
    }
