from __future__ import annotations

import logging
from typing import Any

from shared_py.eventbus import (
    EventEnvelope,
    RedisStreamBus,
    STREAM_FUNDING_BOOKED,
    STREAM_RISK_ALERT,
    STREAM_TRADE_CLOSED,
    STREAM_TRADE_OPENED,
    STREAM_TRADE_UPDATED,
)

logger = logging.getLogger("paper_broker.publisher")


def publish_trade_opened(
    bus: RedisStreamBus,
    *,
    position_id: str,
    account_id: str,
    symbol: str,
    side: str,
    qty_base: str,
    entry_price_avg: str,
    leverage: str,
    trace: dict[str, Any] | None = None,
) -> str:
    env = EventEnvelope(
        event_type="trade_opened",
        symbol=symbol,
        exchange_ts_ms=None,
        dedupe_key=f"paper:open:{position_id}",
        payload={
            "position_id": position_id,
            "account_id": account_id,
            "side": side,
            "qty_base": qty_base,
            "entry_price_avg": entry_price_avg,
            "leverage": leverage,
        },
        trace=trace or {"source": "paper-broker"},
    )
    mid = bus.publish(STREAM_TRADE_OPENED, env)
    logger.info("published trade_opened position_id=%s", position_id)
    return str(mid)


def publish_trade_updated(
    bus: RedisStreamBus,
    *,
    position_id: str,
    symbol: str,
    qty_base: str,
    state: str,
    tp_index: int | None = None,
    trace: dict[str, Any] | None = None,
) -> str:
    pl: dict[str, Any] = {"position_id": position_id, "qty_base": qty_base, "state": state}
    if tp_index is not None:
        pl["tp_index"] = tp_index
        pl["reason"] = "tp_hit"
    env = EventEnvelope(
        event_type="trade_updated",
        symbol=symbol,
        dedupe_key=f"paper:upd:{position_id}:{qty_base}:{state}:{tp_index}",
        payload=pl,
        trace=trace or {"source": "paper-broker"},
    )
    mid = bus.publish(STREAM_TRADE_UPDATED, env)
    return str(mid)


def publish_trade_closed_evt(
    bus: RedisStreamBus,
    *,
    position_id: str,
    symbol: str,
    reason: str,
    trace: dict[str, Any] | None = None,
) -> str:
    env = EventEnvelope(
        event_type="trade_closed",
        symbol=symbol,
        dedupe_key=f"paper:close:{position_id}:{reason}",
        payload={"position_id": position_id, "reason": reason, "paper": True},
        trace=trace or {"source": "paper-broker"},
    )
    mid = bus.publish(STREAM_TRADE_CLOSED, env)
    logger.info("published trade_closed position_id=%s reason=%s", position_id, reason)
    return str(mid)


def publish_funding_booked(
    bus: RedisStreamBus,
    *,
    position_id: str,
    symbol: str,
    funding_rate: str,
    amount: str,
    ts_ms: int,
    trace: dict[str, Any] | None = None,
) -> str:
    env = EventEnvelope(
        event_type="funding_booked",
        symbol=symbol,
        exchange_ts_ms=ts_ms,
        dedupe_key=f"paper:fund:{position_id}:{ts_ms}",
        payload={
            "position_id": position_id,
            "funding_rate": funding_rate,
            "amount": amount,
            "ts_ms": ts_ms,
        },
        trace=trace or {"source": "paper-broker"},
    )
    mid = bus.publish(STREAM_FUNDING_BOOKED, env)
    logger.info(
        "booked funding position_id=%s funding_rate=%s amount=%s",
        position_id,
        funding_rate,
        amount,
    )
    return str(mid)


def publish_risk_alert(
    bus: RedisStreamBus,
    *,
    symbol: str,
    position_id: str,
    warnings: list[str],
    stop_quality_score: int,
    trace: dict[str, Any] | None = None,
) -> str:
    env = EventEnvelope(
        event_type="risk_alert",
        symbol=symbol,
        dedupe_key=f"paper:risk:{position_id}:{stop_quality_score}",
        payload={
            "position_id": position_id,
            "warnings": warnings,
            "stop_quality_score": stop_quality_score,
        },
        trace=trace or {"source": "paper-broker"},
    )
    mid = bus.publish(STREAM_RISK_ALERT, env)
    logger.info(
        "risk_alert position_id=%s stop_quality_score=%s warnings=%s",
        position_id,
        stop_quality_score,
        warnings,
    )
    return str(mid)
