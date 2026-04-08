from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
LEARNING_SRC = ROOT / "services" / "learning-engine" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for candidate in (LEARNING_SRC, SHARED_SRC):
    candidate_str = str(candidate)
    if candidate.is_dir() and candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from learning_engine.worker.processors import _collect_learning_quality_issues


def test_learning_quality_gates_flag_account_and_feature_issues() -> None:
    now_ms = 1_700_000_000_000
    settings = SimpleNamespace(
        learn_max_feature_age_ms=60_000,
        learn_stale_signal_ms=60_000,
    )
    issues = _collect_learning_quality_issues(
        settings=settings,
        decision_ts_ms=now_ms,
        opened_ts_ms=now_ms,
        closed_ts_ms=now_ms - 1,
        side="long",
        entry_avg=Decimal("0"),
        fills=[],
        signal_row={
            "signal_id": "sig-1",
            "symbol": "BTCUSDT",
            "timeframe": "5m",
            "analysis_ts_ms": now_ms - 120_000,
            "market_regime": "trending",
            "direction": "long",
            "signal_strength_0_100": 74.0,
            "probability_0_1": 0.7,
            "signal_class": "gross",
            "structure_score_0_100": 70.0,
            "momentum_score_0_100": 69.0,
            "multi_timeframe_score_0_100": 72.0,
            "news_score_0_100": 50.0,
            "risk_score_0_100": 63.0,
            "history_score_0_100": 52.0,
            "weighted_composite_score_0_100": 70.0,
            "rejection_state": False,
            "rejection_reasons_json": [],
            "decision_state": "accepted",
            "reasons_json": {"decisive_factors": ["ok"]},
            "reward_risk_ratio": 1.7,
            "expected_volatility_band": 0.11,
            "scoring_model_version": "v1.0.0",
        },
        primary_timeframe="5m",
        feature_rows={
            "5m": {
                "symbol": "BTCUSDT",
                "timeframe": "5m",
                "start_ts_ms": now_ms - 180_000,
                "trend_dir": 1,
                "source_event_id": "evt-1",
                "computed_ts_ms": now_ms - 180_000,
            }
        },
    )
    assert "account_entry_price_invalid" in issues
    assert "account_closed_before_open" in issues
    assert "missing_trade_fills" in issues
    assert "stale_feature_snapshot" in issues
    assert "missing_liquidity_feature_snapshot" in issues
    assert "missing_funding_feature_snapshot" in issues
    assert "missing_open_interest_feature_snapshot" in issues
    assert "stale_signal_snapshot" in issues
