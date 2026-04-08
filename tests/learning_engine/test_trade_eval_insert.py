from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from learning_engine.storage import repo_eval


def test_upsert_trade_evaluation_calls_execute() -> None:
    conn = MagicMock()
    cur_ins = MagicMock()
    cur_sel = MagicMock()
    cur_sel.fetchone.return_value = {"evaluation_id": uuid4()}
    conn.execute.side_effect = [cur_ins, cur_sel]
    pid = uuid4()
    row = {
        "paper_trade_id": pid,
        "signal_id": None,
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "decision_ts_ms": 900,
        "opened_ts_ms": 1000,
        "closed_ts_ms": 2000,
        "side": "long",
        "qty_base": Decimal("0.01"),
        "entry_price_avg": Decimal("60000"),
        "exit_price_avg": Decimal("60100"),
        "pnl_gross_usdt": Decimal("1"),
        "fees_total_usdt": Decimal("0.1"),
        "funding_total_usdt": Decimal("0"),
        "pnl_net_usdt": Decimal("0.9"),
        "direction_correct": True,
        "stop_hit": False,
        "tp1_hit": True,
        "tp2_hit": False,
        "tp3_hit": False,
        "time_to_tp1_ms": 500,
        "time_to_stop_ms": None,
        "stop_quality_score": 80,
        "stop_distance_atr_mult": Decimal("1.2"),
        "slippage_bps_entry": Decimal("2"),
        "slippage_bps_exit": Decimal("3"),
        "market_regime": "trend",
        "take_trade_label": True,
        "expected_return_bps": Decimal("15"),
        "expected_return_gross_bps": Decimal("22"),
        "expected_mae_bps": Decimal("8"),
        "expected_mfe_bps": Decimal("30"),
        "liquidation_proximity_bps": Decimal("1250"),
        "liquidation_risk": False,
        "news_context_json": [],
        "signal_snapshot_json": {},
        "feature_snapshot_json": {},
        "structure_snapshot_json": {},
        "error_labels_json": [],
        "model_contract_json": {},
    }
    repo_eval.upsert_trade_evaluation(conn, row)
    assert conn.execute.call_count == 2
