from __future__ import annotations

import logging
import time
from typing import Any

from shared_py.eventbus import RedisStreamBus
from shared_py.eventbus.envelope import STREAM_OPERATOR_INTEL, STREAM_SYSTEM_ALERT, EventEnvelope

logger = logging.getLogger("live_broker.events")


def publish_system_alert(
    bus: RedisStreamBus,
    *,
    alert_key: str,
    severity: str,
    title: str,
    message: str,
    details: dict[str, Any],
) -> None:
    env = EventEnvelope(
        event_type="system_alert",
        dedupe_key=alert_key,
        payload={
            "alert_key": alert_key,
            "severity": severity,
            "title": title,
            "message": message,
            "details": details,
            "ts_ms": int(time.time() * 1000),
        },
        trace={"source": "live-broker"},
    )
    bus.publish(STREAM_SYSTEM_ALERT, env)
    logger.info("published system_alert alert_key=%s severity=%s", alert_key, severity)


def publish_operator_intel(
    bus: RedisStreamBus,
    *,
    symbol: str,
    payload: dict[str, Any],
    timeframe: str | None = None,
    trace: dict[str, Any] | None = None,
) -> None:
    """Strukturierter Operator-Kanal — alert-engine wandelt in Outbox/Telegram um."""
    env = EventEnvelope(
        event_type="operator_intel",
        symbol=symbol,
        timeframe=timeframe,
        dedupe_key=str(payload.get("dedupe_key") or "") or None,
        payload=payload,
        trace=trace or {"source": "live-broker"},
    )
    bus.publish(STREAM_OPERATOR_INTEL, env)
    logger.info(
        "published operator_intel kind=%s symbol=%s",
        payload.get("intel_kind"),
        symbol,
    )
