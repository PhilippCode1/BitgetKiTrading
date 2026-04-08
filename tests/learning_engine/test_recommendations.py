from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

from learning_engine.analytics import recommendations


def _row(
    *,
    pnl: str,
    labels: list[str],
    feature_overrides: dict | None = None,
) -> dict:
    feature = {
        "atrp_14": 0.002,
        "execution_cost_bps": 2.5,
        "spread_bps": 1.2,
        "depth_to_bar_volume_ratio": 1.0,
        "liquidity_source": "orderbook_levels",
    }
    if feature_overrides:
        feature.update(feature_overrides)
    return {
        "closed_ts_ms": 1,
        "pnl_net_usdt": Decimal(pnl),
        "direction_correct": Decimal(pnl) > 0,
        "error_labels_json": labels,
        "signal_snapshot_json": {
            "timeframe": "5m",
            "signal_class": "kern",
            "multi_timeframe_score_0_100": 40,
            "structure_score_0_100": 50,
            "market_regime": "chop",
            "regime_bias": "neutral",
        },
        "feature_snapshot_json": feature,
        "paper_trade_id": "00000000-0000-0000-0000-000000000001",
    }


def test_high_tf_conflict_recommendation() -> None:
    losses = [_row(pnl="-10", labels=["HIGH_TF_CONFLICT"]) for _ in range(8)]
    wins = [_row(pnl="5", labels=[]) for _ in range(5)]
    settings = MagicMock()
    recs = recommendations.build_signal_and_risk_recommendations(losses + wins, settings)
    types = {r["type"] for r in recs}
    assert "signal_weights" in types


def test_stop_tight_recommendation() -> None:
    losses = [_row(pnl="-8", labels=["STOP_TOO_TIGHT"]) for _ in range(6)]
    settings = MagicMock()
    recs = recommendations.build_signal_and_risk_recommendations(losses, settings)
    assert any(r["type"] == "risk_rules" for r in recs)


def test_execution_gate_recommendation() -> None:
    losses = [
        _row(
            pnl="-9",
            labels=[],
            feature_overrides={
                "execution_cost_bps": 22.0,
                "spread_bps": 9.0,
                "depth_to_bar_volume_ratio": 0.2,
                "liquidity_source": "ticker:bitget_ws_ticker",
            },
        )
        for _ in range(6)
    ]
    settings = MagicMock()
    recs = recommendations.build_signal_and_risk_recommendations(losses, settings)
    assert any(r["type"] == "execution_gates" for r in recs)
