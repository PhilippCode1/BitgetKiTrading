from __future__ import annotations

import logging
import time
from typing import Any

from shared_py.eventbus import RedisStreamBus
from shared_py.eventbus.envelope import STREAM_SYSTEM_ALERT, EventEnvelope

from monitor_engine.alerts.dedupe import PublishDedupe
from monitor_engine.alerts.operator_context import merge_operator_guidance
from monitor_engine.alerts.rules import AlertSpec
from monitor_engine.storage.repo_alerts import upsert_alert

logger = logging.getLogger("monitor_engine.publisher")


def publish_system_alert(
    bus: RedisStreamBus,
    *,
    alert_key: str,
    severity: str,
    title: str,
    message: str,
    details: dict[str, Any],
) -> None:
    ts_ms = int(time.time() * 1000)
    env = EventEnvelope(
        event_type="system_alert",
        dedupe_key=alert_key,
        payload={
            "alert_key": alert_key,
            "severity": severity,
            "title": title,
            "message": message,
            "details": details,
            "ts_ms": ts_ms,
        },
    )
    bus.publish(STREAM_SYSTEM_ALERT, env)
    logger.info("events:system_alert published alert_key=%s", alert_key)


def process_alerts(
    dsn: str,
    bus: RedisStreamBus,
    specs: list[AlertSpec],
    *,
    dedupe: PublishDedupe,
    dedupe_sec: int,
) -> None:
    observed_at_ms = int(time.time() * 1000)
    for spec in specs:
        details = merge_operator_guidance(
            alert_key=spec.alert_key,
            base_details=spec.details,
            severity=spec.severity,
            title=spec.title,
            observed_at_ms=observed_at_ms,
        )
        try:
            upsert_alert(
                dsn,
                alert_key=spec.alert_key,
                severity=spec.severity,
                title=spec.title,
                message=spec.message,
                details=details,
            )
        except Exception as exc:
            logger.warning(
                "ops alert upsert failed alert_key=%s: %s",
                spec.alert_key,
                exc,
            )
            continue
        logger.info("ops alert upsert alert_key=%s severity=%s", spec.alert_key, spec.severity)
        if dedupe.allow_publish(spec.alert_key, dedupe_sec):
            try:
                publish_system_alert(
                    bus,
                    alert_key=spec.alert_key,
                    severity=spec.severity,
                    title=spec.title,
                    message=spec.message,
                    details=details,
                )
            except Exception as exc:
                logger.exception("publish system_alert failed: %s", exc)
