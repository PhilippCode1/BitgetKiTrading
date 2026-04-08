from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from shared_py.eventbus import STREAM_MARKET_FEED_HEALTH, EventEnvelope
from shared_py.bitget.instruments import BitgetInstrumentIdentity

if TYPE_CHECKING:
    from market_stream.sinks.eventbus import AsyncRedisEventBus


def gapfill_triggers_orderbook_resync(reason: str) -> bool:
    return (
        reason == "stale-data"
        or reason == "reconnect"
        or reason.startswith("seq-gap")
    )


def compute_quote_age_ms(
    *,
    now_ms: int,
    last_quote_ts_ms: int | None,
    last_orderbook_ts_ms: int | None,
) -> tuple[int | None, int | None]:
    age_t = (now_ms - last_quote_ts_ms) if last_quote_ts_ms else None
    age_o = (now_ms - last_orderbook_ts_ms) if last_orderbook_ts_ms else None
    return age_t, age_o


async def publish_market_feed_health(
    event_bus: AsyncRedisEventBus,
    *,
    symbol: str,
    payload: dict[str, Any],
    instrument: BitgetInstrumentIdentity | None = None,
    logger: logging.Logger | None = None,
) -> None:
    log = logger or logging.getLogger("market_stream.feed_health")
    env = EventEnvelope(
        event_type="market_feed_health",
        symbol=symbol,
        instrument=instrument,
        exchange_ts_ms=int(time.time() * 1000),
        payload=payload,
        trace={"publisher": "market-stream"},
    )
    msg_id = await event_bus.publish(STREAM_MARKET_FEED_HEALTH, env)
    if msg_id is None:
        log.debug("market_feed_health publish skipped (eventbus offline)")
