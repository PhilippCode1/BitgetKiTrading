#!/usr/bin/env python3
"""Seed 50 trade_evaluations für Learning Engine V1 (Drift/Metriken/Patterns).

Voraussetzung: Migrationen bis 160 angewendet, learn.strategies wird ergänzt.

Usage:
  set DATABASE_URL
  python tools/seed_trade_evaluations.py
"""
from __future__ import annotations

import os
import random
import sys
import time
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parents[1]
LE_SRC = REPO / "services" / "learning-engine" / "src"
sys.path.insert(0, str(LE_SRC))

import psycopg
from learning_engine.storage.repo_eval import upsert_trade_evaluation
from psycopg.rows import dict_row

STRATEGIES = (
    "TrendContinuationStrategy",
    "BreakoutBoxStrategy",
    "MeanReversionMicroStrategy",
)


def ensure_strategies(conn: psycopg.Connection) -> None:
    for name in STRATEGIES:
        conn.execute(
            """
            INSERT INTO learn.strategies (name, description)
            VALUES (%s, %s)
            ON CONFLICT (name) DO NOTHING
            """,
            (name, "seed"),
        )


def main() -> int:
    dsn = os.environ.get("DATABASE_URL", "").strip()
    if not dsn:
        print("DATABASE_URL fehlt", file=sys.stderr)
        return 1
    random.seed(42)
    now_ms = int(time.time() * 1000)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.transaction():
            ensure_strategies(conn)
        with conn.transaction():
            for i in range(50):
                pid = uuid4()
                opened = now_ms - (50 - i) * 3_600_000
                closed = opened + 120_000
                strat = STRATEGIES[i % len(STRATEGIES)]
                if i < 25:
                    pnl = Decimal(str(round(random.uniform(5, 80), 2)))
                    direction = True
                    labels: list[str] = []
                else:
                    pnl = Decimal(str(round(random.uniform(-120, -5), 2)))
                    direction = False
                    labels = []
                    if i % 4 == 0:
                        labels.append("HIGH_TF_CONFLICT")
                    if i % 5 == 0:
                        labels.append("STOP_TOO_TIGHT")
                row = {
                    "paper_trade_id": pid,
                    "signal_id": uuid4(),
                    "symbol": "BTCUSDT",
                    "timeframe": random.choice(["5m", "15m", "1h"]),
                    "opened_ts_ms": opened,
                    "closed_ts_ms": closed,
                    "side": random.choice(["long", "short"]),
                    "qty_base": Decimal("0.02"),
                    "entry_price_avg": Decimal("65000"),
                    "exit_price_avg": Decimal("65100"),
                    "pnl_gross_usdt": pnl + Decimal("1"),
                    "fees_total_usdt": Decimal("0.5"),
                    "funding_total_usdt": Decimal("-0.1"),
                    "pnl_net_usdt": pnl,
                    "direction_correct": direction,
                    "stop_hit": i % 7 == 0 and not direction,
                    "tp1_hit": direction and i % 3 == 0,
                    "tp2_hit": False,
                    "tp3_hit": False,
                    "time_to_tp1_ms": 1000 if direction else None,
                    "time_to_stop_ms": None,
                    "stop_quality_score": 70,
                    "stop_distance_atr_mult": Decimal("1.0"),
                    "slippage_bps_entry": Decimal("2"),
                    "slippage_bps_exit": Decimal("2"),
                    "market_regime": random.choice(["UP", "DOWN", "RANGE"]),
                    "news_context_json": [],
                    "signal_snapshot_json": {
                        "strategy_name": strat,
                        "signal_class": "kern",
                        "timeframe": "5m",
                        "market_regime": "trend" if direction else "chop",
                        "regime_bias": "long" if direction else "neutral",
                        "regime_confidence_0_1": 0.72 if direction else 0.61,
                        "regime_reasons_json": ["seed_fixture"],
                        "multi_timeframe_score_0_100": random.randint(20, 90),
                        "structure_score_0_100": random.randint(30, 80),
                    },
                    "feature_snapshot_json": {"atrp_14": round(random.uniform(0.001, 0.01), 6)},
                    "structure_snapshot_json": {},
                    "error_labels_json": labels,
                }
                upsert_trade_evaluation(conn, row)
    print("seeded 50 trade_evaluations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
