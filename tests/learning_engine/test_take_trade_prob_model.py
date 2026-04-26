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
from learning_engine.meta_models.take_trade_prob import train_take_trade_prob_model
from learning_engine.storage import repo_model_runs
from shared_py.model_contracts import build_feature_snapshot, build_model_output_snapshot


@pytest.fixture
def learning_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> LearningEngineSettings:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("TAKE_TRADE_MODEL_ARTIFACTS_DIR", str(tmp_path / "models"))
    return LearningEngineSettings()


def test_train_take_trade_prob_model_writes_artifact_and_metrics(
    learning_settings: LearningEngineSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [_evaluation_row(i) for i in range(96)]
    inserted: dict[str, object] = {}
    cleared: list[str] = []

    def _fake_fetch(
        _conn: object,
        *,
        symbol: str | None = None,
        min_decision_ts_ms: int | None = None,
    ) -> list[dict[str, object]]:
        return rows

    monkeypatch.setattr(
        repo_model_runs,
        "fetch_take_trade_training_rows",
        _fake_fetch,
    )
    monkeypatch.setattr(
        repo_model_runs,
        "clear_promoted_model",
        lambda _conn, model_name: cleared.append(model_name),
    )

    def _capture_insert(_conn, **kwargs):
        inserted.update(kwargs)

    monkeypatch.setattr(repo_model_runs, "insert_model_run", _capture_insert)

    report = train_take_trade_prob_model(object(), learning_settings)

    assert "data_version_hash" in report
    assert "cv_report" in report
    assert report["cv_report"]["summary"]["walk_forward_mean_roc_auc"] is not None
    assert cleared == ["take_trade_prob"]
    assert report["promoted"] is True
    assert 0.0 <= float(report["metrics"]["brier_score"]) <= 1.0
    assert report["rows"]["total"] == len(rows)
    assert report["rows"]["train"] > 0
    assert report["rows"]["calibration"] > 0
    assert report["rows"]["test"] > 0
    artifact_path = ROOT / str(report["artifact_path"])
    assert artifact_path.is_file()
    adir = artifact_path.parent
    assert (adir / "training_manifest.json").is_file()
    assert (adir / "run_manifest.json").is_file()
    assert (adir / "cv_report.json").is_file()
    assert (adir / "calibration.joblib").is_file()
    assert inserted["model_name"] == "take_trade_prob"
    assert inserted["calibration_method"] == "sigmoid"
    metadata = inserted["metadata_json"]
    assert isinstance(metadata, dict)
    assert metadata["feature_contract"]["model_name"] == "take_trade_prob"
    assert "model_layer_contract" in metadata
    assert metadata["model_layer_contract"]["model_layer_contract_version"]
    dbr = metadata["dataset_build_report"]
    assert dbr["kept_count"] == len(rows)
    assert dbr["dropped"] == {}
    assert metadata["training_rows_raw"] == len(rows)
    assert "feature_reference" in metadata
    assert "signal_strength_0_100" in metadata["feature_reference"]["numeric_fields"]
    assert metadata["metrics"]["brier_score"] == report["metrics"]["brier_score"]
    assert len(report["regime_metrics"]) >= 2
    assert len(report["calibration_curve"]) == 5


def _evaluation_row(index: int) -> dict[str, object]:
    label = 1 if index % 2 == 0 else 0
    regime = "trend" if label else "chop"
    bias = "long" if label else "neutral"
    signal_strength = 78.0 if label else 38.0
    heuristic_prob = 0.76 if label else 0.29
    multi_tf = 74.0 if label else 31.0
    risk = 67.0 if label else 36.0
    feature_rows = {
        "1m": _feature_row("1m", index, label),
        "5m": _feature_row("5m", index, label),
        "15m": _feature_row("15m", index, label),
        "1H": _feature_row("1H", index, label),
        "4H": _feature_row("4H", index, label),
    }
    signal_snapshot = build_model_output_snapshot(
        {
            "signal_id": str(uuid4()),
            "symbol": "BTCUSDT",
            "timeframe": "5m",
            "analysis_ts_ms": 1_700_000_000_000 + index * 60_000,
            "market_regime": regime,
            "regime_bias": bias,
            "regime_confidence_0_1": 0.84 if label else 0.46,
            "regime_reasons_json": [f"regime={regime}"],
            "direction": "long" if label else "neutral",
            "signal_strength_0_100": signal_strength,
            "probability_0_1": heuristic_prob,
            "signal_class": "gross" if label else "warnung",
            "structure_score_0_100": 72.0 if label else 34.0,
            "momentum_score_0_100": 69.0 if label else 35.0,
            "multi_timeframe_score_0_100": multi_tf,
            "news_score_0_100": 52.0 if label else 48.0,
            "risk_score_0_100": risk,
            "history_score_0_100": 54.0 if label else 44.0,
            "weighted_composite_score_0_100": 71.0 if label else 36.0,
            "rejection_state": False,
            "rejection_reasons_json": [],
            "decision_state": "accepted" if label else "downgraded",
            "reasons_json": {},
            "reward_risk_ratio": 1.9 if label else 0.9,
            "expected_volatility_band": 0.12 if label else 0.08,
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
        "take_trade_label": bool(label),
        "signal_snapshot_json": signal_snapshot,
        "feature_snapshot_json": feature_snapshot,
    }


def _feature_row(timeframe: str, index: int, label: int) -> dict[str, object]:
    return {
        "symbol": "BTCUSDT",
        "timeframe": timeframe,
        "start_ts_ms": 1_700_000_000_000 + index * 60_000,
        "atr_14": 100.0 + index,
        "atrp_14": 0.11 if label else 0.05,
        "rsi_14": 61.0 if label else 42.0,
        "ret_1": 0.002 if label else -0.0015,
        "ret_5": 0.006 if label else -0.003,
        "momentum_score": 64.0 if label else -18.0,
        "impulse_body_ratio": 0.62 if label else 0.31,
        "impulse_upper_wick_ratio": 0.18,
        "impulse_lower_wick_ratio": 0.20,
        "range_score": 28.0 if label else 71.0,
        "trend_ema_fast": 100_200.0 + index,
        "trend_ema_slow": 100_000.0 + index,
        "trend_slope_proxy": 12.0 if label else -4.0,
        "trend_dir": 1 if label else 0,
        "confluence_score_0_100": 78.0 if label else 39.0,
        "vol_z_50": 0.4 if label else 0.1,
        "spread_bps": 1.4 if label else 3.0,
        "bid_depth_usdt_top25": 250_000.0,
        "ask_depth_usdt_top25": 245_000.0,
        "orderbook_imbalance": 0.05 if label else -0.02,
        "depth_balance_ratio": 0.99 if label else 0.92,
        "depth_to_bar_volume_ratio": 1.8 if label else 0.9,
        "impact_buy_bps_5000": 2.0 if label else 4.2,
        "impact_sell_bps_5000": 1.9 if label else 4.0,
        "impact_buy_bps_10000": 3.4 if label else 6.1,
        "impact_sell_bps_10000": 3.1 if label else 5.7,
        "execution_cost_bps": 2.4 if label else 5.2,
        "volatility_cost_bps": 2.9 if label else 5.6,
        "funding_rate": 0.0001,
        "funding_rate_bps": 0.8 if label else 2.2,
        "funding_cost_bps_window": 0.05 if label else 0.22,
        "open_interest": 1_100_000.0 + index,
        "open_interest_change_pct": 4.2 if label else -1.1,
        "orderbook_age_ms": 2_000,
        "funding_age_ms": 30_000,
        "open_interest_age_ms": 5_000,
        "liquidity_source": "orderbook_levels",
        "funding_source": "bitget_rest_funding",
        "open_interest_source": "bitget_rest_open_interest",
        "source_event_id": f"evt-{timeframe}-{index}",
        "computed_ts_ms": 1_700_000_010_000 + index * 60_000,
    }
