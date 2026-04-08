from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
LEARNING_SRC = ROOT / "services" / "learning-engine" / "src"
candidate_str = str(LEARNING_SRC)
if LEARNING_SRC.is_dir() and candidate_str not in sys.path:
    sys.path.insert(0, candidate_str)

from learning_engine.storage import repo_backtest


def test_fetch_trade_evaluations_window_uses_decision_anchor() -> None:
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchall.return_value = []
    conn.execute.return_value = cur

    repo_backtest.fetch_trade_evaluations_window(
        conn,
        symbol="BTCUSDT",
        from_ts_ms=1_700_000_000_000,
        to_ts_ms=1_700_000_360_000,
    )

    sql, params = conn.execute.call_args.args
    assert "decision_ts_ms >= %s" in sql
    assert "decision_ts_ms <= %s" in sql
    assert "ORDER BY decision_ts_ms ASC, closed_ts_ms ASC" in sql
    assert params == ("BTCUSDT", 1_700_000_000_000, 1_700_000_360_000)
