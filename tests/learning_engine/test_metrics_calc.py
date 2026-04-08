from __future__ import annotations

from decimal import Decimal

from learning_engine.analytics.strategy_metrics import (
    compute_trade_metrics,
    infer_strategy_name,
    max_drawdown_fraction_from_pnls,
)


def test_max_drawdown_peak_then_drop() -> None:
    # +10, +10, -15 → peak 20, dann 5 → dd = (20-5)/20 = 0.75
    pnls = [Decimal("10"), Decimal("10"), Decimal("-15")]
    assert abs(max_drawdown_fraction_from_pnls(pnls) - 0.75) < 1e-6


def test_profit_factor_and_win_rate() -> None:
    rows = [
        {
            "closed_ts_ms": 1000,
            "pnl_net_usdt": Decimal("10"),
            "fees_total_usdt": Decimal("1"),
            "funding_total_usdt": Decimal("0"),
            "direction_correct": True,
            "stop_hit": False,
            "take_trade_label": True,
            "liquidation_risk": False,
            "expected_return_bps": Decimal("150"),
            "expected_return_gross_bps": Decimal("180"),
            "expected_mae_bps": Decimal("45"),
            "expected_mfe_bps": Decimal("220"),
            "signal_snapshot_json": {"strategy_name": "X"},
        },
        {
            "closed_ts_ms": 2000,
            "pnl_net_usdt": Decimal("-5"),
            "fees_total_usdt": Decimal("1"),
            "funding_total_usdt": Decimal("-0.5"),
            "direction_correct": False,
            "stop_hit": True,
            "take_trade_label": False,
            "liquidation_risk": True,
            "expected_return_bps": Decimal("-80"),
            "expected_return_gross_bps": Decimal("-40"),
            "expected_mae_bps": Decimal("120"),
            "expected_mfe_bps": Decimal("35"),
            "signal_snapshot_json": {"strategy_name": "X"},
        },
    ]
    m = compute_trade_metrics(rows)
    assert m["trades"] == 2
    assert m["wins"] == 1
    assert m["win_rate"] == 0.5
    assert abs(m["gross_profit"] - 10.0) < 1e-6
    assert abs(m["gross_loss"] - (-5.0)) < 1e-6
    assert abs(m["profit_factor"] - 2.0) < 1e-6
    assert m["stop_out_rate"] == 0.5
    assert m["take_trade_rate"] == 0.5
    assert m["liquidation_risk_rate"] == 0.5
    assert abs(m["avg_expected_return_bps"] - 35.0) < 1e-6
    assert abs(m["avg_expected_return_gross_bps"] - 70.0) < 1e-6
    assert abs(m["avg_expected_mae_bps"] - 82.5) < 1e-6
    assert abs(m["avg_expected_mfe_bps"] - 127.5) < 1e-6
    denom = 10 + 5
    assert abs(m["fee_drag"] - 2.0 / denom) < 1e-6


def test_infer_strategy_name_from_class() -> None:
    row = {"signal_snapshot_json": {"signal_class": "mikro"}}
    assert infer_strategy_name(row) == "MeanReversionMicroStrategy"


def test_infer_strategy_name_from_playbook_family() -> None:
    row = {
        "signal_snapshot_json": {
            "playbook_id": "breakout_expansion",
            "playbook_family": "breakout",
        }
    }
    assert infer_strategy_name(row) == "BreakoutBoxStrategy"


def test_empty_metrics() -> None:
    m = compute_trade_metrics([])
    assert m["trades"] == 0
    assert m["profit_factor"] is None
