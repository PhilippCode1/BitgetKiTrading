from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEARNING_SRC = ROOT / "services" / "learning-engine" / "src"
if LEARNING_SRC.is_dir() and str(LEARNING_SRC) not in sys.path:
    sys.path.insert(0, str(LEARNING_SRC))

from learning_engine.training.trade_relevance_metrics import (
    execution_sensitivity_proxy,
    stop_failure_mode_rates,
    trade_relevance_binary_classification_report,
)


def test_trade_relevance_binary_basic() -> None:
    y = [0, 0, 1, 1, 0]
    p = [0.1, 0.2, 0.8, 0.7, 0.5]
    r = trade_relevance_binary_classification_report(y, p)
    assert r["count"] == 5
    assert r["abstention_count"] >= 1
    assert "route_stability_proxy" in r


def test_stop_failure_mode_rates() -> None:
    ex = [
        {"error_labels": ["stop_slip"]},
        {"error_labels": ["stop_slip", "latency"]},
        {"error_labels": []},
    ]
    c = stop_failure_mode_rates(ex)
    assert c.get("stop_slip") == 2


def test_execution_sensitivity_insufficient_n() -> None:
    ex = [{"features": {"execution_cost_bps": 1.0}} for _ in range(3)]
    r = execution_sensitivity_proxy(ex, [0.5, 0.4, 0.6])
    assert r["available"] is False


def test_execution_sensitivity_correlation() -> None:
    ex = [{"features": {"execution_cost_bps": float(i)}} for i in range(10)]
    p = [0.1 * i for i in range(10)]
    r = execution_sensitivity_proxy(ex, p)
    assert r["available"] is True
    assert r["n"] == 10
    assert r["pearson_prob_vs_execution_cost_bps"] is not None
