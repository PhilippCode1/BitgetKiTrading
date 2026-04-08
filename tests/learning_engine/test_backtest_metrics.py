from __future__ import annotations

from decimal import Decimal

from learning_engine.backtest.metrics import backtest_aggregate_metrics


def test_backtest_aggregate_empty() -> None:
    m = backtest_aggregate_metrics([])
    assert m["trades"] == 0
    assert m["profit_factor"] is None


def test_backtest_aggregate_basic() -> None:
    rows = [
        {
            "closed_ts_ms": 1000,
            "opened_ts_ms": 900,
            "pnl_net_usdt": Decimal("10"),
            "fees_total_usdt": Decimal("1"),
            "funding_total_usdt": Decimal("0"),
            "direction_correct": True,
            "stop_hit": False,
            "take_trade_label": True,
            "liquidation_risk": False,
            "expected_return_bps": Decimal("150"),
            "expected_return_gross_bps": Decimal("180"),
            "expected_mae_bps": Decimal("40"),
            "expected_mfe_bps": Decimal("220"),
        },
        {
            "closed_ts_ms": 2000,
            "opened_ts_ms": 1900,
            "pnl_net_usdt": Decimal("-4"),
            "fees_total_usdt": Decimal("1"),
            "funding_total_usdt": Decimal("0"),
            "direction_correct": False,
            "stop_hit": True,
            "take_trade_label": False,
            "liquidation_risk": True,
            "expected_return_bps": Decimal("-60"),
            "expected_return_gross_bps": Decimal("-25"),
            "expected_mae_bps": Decimal("110"),
            "expected_mfe_bps": Decimal("35"),
        },
    ]
    m = backtest_aggregate_metrics(rows)
    assert m["trades"] == 2
    assert m["avg_pnl_net"] == 3.0
    assert m["stop_out_rate"] == 0.5
    assert m["take_trade_rate"] == 0.5
    assert m["liquidation_risk_rate"] == 0.5
    assert abs(m["avg_expected_return_bps"] - 45.0) < 1e-6
    assert abs(m["avg_expected_return_gross_bps"] - 77.5) < 1e-6
