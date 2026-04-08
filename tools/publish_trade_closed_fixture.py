#!/usr/bin/env python3
"""Publiziert events:trade_closed fuer Learning-Engine Tests."""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "shared" / "python" / "src"
if SHARED.is_dir():
    sys.path.insert(0, str(SHARED))

from shared_py.eventbus import (  # noqa: E402
    STREAM_TRADE_CLOSED,
    EventEnvelope,
    RedisStreamBus,
)


def main() -> None:
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        print("REDIS_URL fehlt", file=sys.stderr)
        sys.exit(1)
    bus = RedisStreamBus.from_url(url, dedupe_ttl_sec=0)
    pid = os.environ.get("FIXTURE_POSITION_ID", str(uuid.uuid4()))
    env = EventEnvelope(
        event_type="trade_closed",
        symbol=os.environ.get("FIXTURE_SYMBOL", "BTCUSDT"),
        dedupe_key=f"fixture:close:{pid}",
        payload={
            "position_id": pid,
            "reason": os.environ.get("FIXTURE_CLOSE_REASON", "CLOSED"),
            "paper": True,
        },
        trace={"source": "publish_trade_closed_fixture.py"},
    )
    mid = bus.publish(STREAM_TRADE_CLOSED, env)
    print(f"published position_id={pid} message_id={mid} stream={STREAM_TRADE_CLOSED}")


if __name__ == "__main__":
    main()
