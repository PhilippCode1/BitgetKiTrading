#!/usr/bin/env python3
"""
Publiziert ein events:signal_created Envelope fuer Strategy-Tests (ohne DB-Zeile).
Voraussetzung: REDIS_URL, vollstaendiges Signal-Payload mit decision_state=accepted.
"""
from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "shared" / "python" / "src"
if SHARED.is_dir():
    sys.path.insert(0, str(SHARED))

from shared_py.eventbus import (  # noqa: E402
    STREAM_SIGNAL_CREATED,
    EventEnvelope,
    RedisStreamBus,
)


def main() -> None:
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        print("REDIS_URL fehlt", file=sys.stderr)
        sys.exit(1)
    bus = RedisStreamBus.from_url(url, dedupe_ttl_sec=0)
    sid = str(uuid.uuid4())
    now = int(time.time() * 1000)
    payload = {
        "schema_version": "1.0",
        "signal_id": sid,
        "symbol": os.environ.get("FIXTURE_SYMBOL", "BTCUSDT"),
        "timeframe": os.environ.get("FIXTURE_TIMEFRAME", "5m"),
        "direction": os.environ.get("FIXTURE_DIRECTION", "long"),
        "signal_strength_0_100": int(os.environ.get("FIXTURE_STRENGTH", "80")),
        "probability_0_1": float(os.environ.get("FIXTURE_PROB", "0.72")),
        "signal_class": os.environ.get("FIXTURE_CLASS", "kern"),
        "analysis_ts_ms": now,
        "decision_state": "accepted",
        "rejection_state": False,
        "rejection_reasons_json": [],
        "risk_score_0_100": int(os.environ.get("FIXTURE_RISK", "70")),
        "scoring_model_version": "fixture",
    }
    env = EventEnvelope(
        event_type="signal_created",
        symbol=payload["symbol"],
        timeframe=payload["timeframe"],
        exchange_ts_ms=now,
        dedupe_key=f"fixture:signal:{sid}",
        payload=payload,
        trace={"source": "publish_signal_fixture.py"},
    )
    mid = bus.publish(STREAM_SIGNAL_CREATED, env)
    print(f"published signal_id={sid} message_id={mid} stream={STREAM_SIGNAL_CREATED}")


if __name__ == "__main__":
    main()
