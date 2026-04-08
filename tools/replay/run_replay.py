#!/usr/bin/env python3
"""Replay: tsdb.candles → Redis events:candle_close (speed_factor).

Replay publiziert nur historische Markt-Events; Learning-Targets entstehen
spaeter in `trade_closed`, nicht direkt im Replay-Tool.

Beispiel:
  python tools/replay/run_replay.py --symbol BTCUSDT --from 1710000000000 --to 1710003600000 --tf 5m,1m
"""
from __future__ import annotations

import argparse
import os
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
    p.add_argument("--tf", default="5m", help="Komma-separierte Timeframes (DB-Schreibweise z. B. 1H)")
    p.add_argument(
        "--speed",
        type=float,
        default=None,
        help="Default: REPLAY_SPEED_FACTOR aus ENV",
    )
    p.add_argument("--ticks", action="store_true", help="Zusaetzlich market_tick aus Close approximieren")
    p.add_argument(
        "--ephemeral-session",
        action="store_true",
        help="Neue session_id pro Lauf statt deterministischer UUID5 (Tests/Ad-hoc)",
    )
    args = p.parse_args()

    from learning_engine.backtest.runner_replay import run_replay_candles
    from learning_engine.config import LearningEngineSettings

    settings = LearningEngineSettings()
    speed = args.speed if args.speed is not None else settings.replay_speed_factor
    dsn = os.environ.get("DATABASE_URL", "").strip() or settings.database_url
    redis_url = os.environ.get("REDIS_URL", "").strip() or settings.redis_url
    tfs = [x.strip() for x in args.tf.split(",") if x.strip()]
    sid = run_replay_candles(
        dsn,
        redis_url,
        symbol=args.symbol,
        timeframes=tfs,
        from_ts_ms=args.from_ts,
        to_ts_ms=args.to_ts,
        speed_factor=speed,
        publish_ticks=args.ticks,
        ephemeral_session=args.ephemeral_session,
        settings=settings,
    )
    print(str(sid))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
