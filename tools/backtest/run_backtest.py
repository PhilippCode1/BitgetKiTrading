#!/usr/bin/env python3
"""Offline-Backtest (learn.trade_evaluations) — DB + Artefakte.

Fensteranker: `decision_ts_ms` (Signal-Analysezeit, sonst Open-Zeit).

Beispiel:
  python tools/backtest/run_backtest.py --symbol BTCUSDT --from 1710000000000 --to 1710003600000 --cv walk_forward
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "services/learning-engine/src"))
sys.path.insert(0, str(REPO / "shared/python/src"))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--from", dest="from_ts", type=int, required=True)
    p.add_argument("--to", dest="to_ts", type=int, required=True)
    p.add_argument(
        "--cv",
        choices=("walk_forward", "purged_kfold_embargo"),
        required=True,
    )
    p.add_argument(
        "--timeframes",
        default="5m",
        help="Komma-separiert, Metadaten im Run-Record",
    )
    p.add_argument(
        "--ephemeral-run",
        action="store_true",
        help="Neue run_id (uuid4) statt deterministischer UUID5 aus Parametern/Seed",
    )
    args = p.parse_args()

    from learning_engine.backtest.runner_offline import run_offline_backtest
    from learning_engine.config import LearningEngineSettings
    from learning_engine.storage.connection import db_connect

    settings = LearningEngineSettings()
    tfs = [x.strip() for x in args.timeframes.split(",") if x.strip()]
    with db_connect(settings.database_url) as conn:
        with conn.transaction():
            rid = run_offline_backtest(
                conn,
                settings,
                symbol=args.symbol,
                from_ts_ms=args.from_ts,
                to_ts_ms=args.to_ts,
                cv_method=args.cv,
                timeframes=tfs,
                ephemeral_run=args.ephemeral_run,
            )
    print(str(rid))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
