"""
Backtest-/Metrik-Outputs aus Fixture (deterministisch).
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_trade_metrics_from_json_fixture() -> None:
    from learning_engine.analytics.strategy_metrics import compute_trade_metrics

    raw = json.loads(
        (REPO / "tests" / "fixtures" / "backtest_trades_fixture.json").read_text(
            encoding="utf-8"
        )
    )
    rows = []
    for row in raw:
        rows.append(
            {
                "closed_ts_ms": row["closed_ts_ms"],
                "pnl_net_usdt": Decimal(row["pnl_net_usdt"]),
                "fees_total_usdt": Decimal(row["fees_total_usdt"]),
                "funding_total_usdt": Decimal(row["funding_total_usdt"]),
                "direction_correct": row["direction_correct"],
                "stop_hit": row["stop_hit"],
                "signal_snapshot_json": row["signal_snapshot_json"],
            }
        )
    m = compute_trade_metrics(rows)
    assert m["trades"] == 2
    assert m["wins"] == 1
    assert abs(float(m["profit_factor"]) - 2.0) < 1e-6
