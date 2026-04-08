#!/usr/bin/env python3
"""
Publiziert Test-Events fuer den alert-engine (Redis Streams).
Nutzt EventEnvelope / shared_py — keine Secrets.

Beispiel:
  python tools/publish_alert_fixtures.py --type gross_signal
  ALERT_FIXTURE_CHAT_ID=1000001  (optional; upsertet allowed Chat in DB via psql)
"""
from __future__ import annotations

import argparse
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
    STREAM_NEWS_SCORED,
    STREAM_RISK_ALERT,
    STREAM_SIGNAL_CREATED,
    STREAM_STRUCTURE_UPDATED,
    STREAM_SYSTEM_ALERT,
    STREAM_TRADE_CLOSED,
    EventEnvelope,
    RedisStreamBus,
)


def _bus() -> RedisStreamBus:
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        print("REDIS_URL fehlt", file=sys.stderr)
        sys.exit(1)
    return RedisStreamBus.from_url(url, dedupe_ttl_sec=0)


def publish_gross() -> None:
    bus = _bus()
    sid = str(uuid.uuid4())
    now = int(time.time() * 1000)
    p = {
        "signal_id": sid,
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "direction": "long",
        "signal_strength_0_100": 90,
        "probability_0_1": 0.8,
        "signal_class": "gross",
        "analysis_ts_ms": now,
        "decision_state": "accepted",
        "rejection_state": False,
        "rejection_reasons_json": [],
        "reasons_json": ["structure ok", "momentum", "mtf"],
        "stop_zone_id": None,
        "scoring_model_version": "fixture",
    }
    env = EventEnvelope(
        event_type="signal_created",
        symbol="BTCUSDT",
        timeframe="5m",
        exchange_ts_ms=now,
        dedupe_key=f"fixture:alert:gross:{sid}",
        payload=p,
        trace={"source": "publish_alert_fixtures.py"},
    )
    print(bus.publish(STREAM_SIGNAL_CREATED, env))


def publish_core() -> None:
    bus = _bus()
    sid = str(uuid.uuid4())
    now = int(time.time() * 1000)
    p = {
        "signal_id": sid,
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "direction": "short",
        "signal_strength_0_100": 70,
        "probability_0_1": 0.55,
        "signal_class": "kern",
        "analysis_ts_ms": now,
        "decision_state": "accepted",
        "rejection_state": False,
        "rejection_reasons_json": [],
        "reasons_json": ["a", "b"],
        "scoring_model_version": "fixture",
    }
    env = EventEnvelope(
        event_type="signal_created",
        symbol="BTCUSDT",
        timeframe="15m",
        exchange_ts_ms=now,
        dedupe_key=f"fixture:alert:core:{sid}",
        payload=p,
        trace={"source": "publish_alert_fixtures.py"},
    )
    print(bus.publish(STREAM_SIGNAL_CREATED, env))


def publish_trend() -> None:
    bus = _bus()
    now = int(time.time() * 1000)
    env = EventEnvelope(
        event_type="structure_updated",
        symbol="BTCUSDT",
        timeframe="5m",
        exchange_ts_ms=now,
        dedupe_key=f"fixture:alert:struct:{now}",
        payload={
            "ts_ms": now,
            "trend_dir": "down",
            "choch": True,
        },
        trace={"source": "publish_alert_fixtures.py"},
    )
    print(bus.publish(STREAM_STRUCTURE_UPDATED, env))


def publish_trade_closed() -> None:
    bus = _bus()
    pid = str(uuid.uuid4())
    env = EventEnvelope(
        event_type="trade_closed",
        symbol="BTCUSDT",
        dedupe_key=f"fixture:alert:close:{pid}",
        payload={
            "position_id": pid,
            "reason": "TP",
            "pnl_net_usdt": "12.34",
            "fees_total_usdt": "0.5",
            "funding_total_usdt": "-0.1",
            "paper": True,
        },
        trace={"source": "publish_alert_fixtures.py"},
    )
    print(bus.publish(STREAM_TRADE_CLOSED, env))


def publish_risk() -> None:
    bus = _bus()
    env = EventEnvelope(
        event_type="risk_alert",
        symbol="BTCUSDT",
        dedupe_key=f"fixture:alert:risk:{uuid.uuid4()}",
        payload={
            "position_id": str(uuid.uuid4()),
            "warnings": ["stop proximity"],
            "stop_quality_score": 30,
            "severity": "high",
        },
        trace={"source": "publish_alert_fixtures.py"},
    )
    print(bus.publish(STREAM_RISK_ALERT, env))


def publish_news() -> None:
    bus = _bus()
    nid = str(uuid.uuid4())
    env = EventEnvelope(
        event_type="news_scored",
        symbol="BTCUSDT",
        dedupe_key=f"fixture:alert:news:{nid}",
        payload={
            "news_id": nid,
            "relevance_score": 90,
            "sentiment": "bearish",
            "impact_window": "immediate",
            "title": "Fixture headline",
            "url": "https://example.com/news",
            "published_ts_ms": int(time.time() * 1000),
        },
        trace={"source": "publish_alert_fixtures.py"},
    )
    print(bus.publish(STREAM_NEWS_SCORED, env))


def publish_system() -> None:
    bus = _bus()
    env = EventEnvelope(
        event_type="system_alert",
        symbol="BTCUSDT",
        dedupe_key=f"fixture:alert:sys:{uuid.uuid4()}",
        payload={"message": "Fixture system health", "severity": "warn"},
        trace={"source": "publish_alert_fixtures.py"},
    )
    print(bus.publish(STREAM_SYSTEM_ALERT, env))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--type",
        required=True,
        choices=(
            "gross_signal",
            "core_signal",
            "trend",
            "trade_closed",
            "risk_alert",
            "news_high",
            "system_alert",
        ),
    )
    args = ap.parse_args()
    fn = {
        "gross_signal": publish_gross,
        "core_signal": publish_core,
        "trend": publish_trend,
        "trade_closed": publish_trade_closed,
        "risk_alert": publish_risk,
        "news_high": publish_news,
        "system_alert": publish_system,
    }[args.type]
    fn()
    print(
        "Hinweis: mindestens ein Chat in alert.chat_subscriptions (status=allowed), "
        "z. B. via POST /admin/chats/<id>/allow",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
