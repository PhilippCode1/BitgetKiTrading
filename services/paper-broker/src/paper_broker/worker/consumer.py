from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

from shared_py.eventbus import (
    STREAM_DRAWING_UPDATED,
    STREAM_FUNDING_UPDATE,
    STREAM_MARKET_TICK,
    STREAM_NEWS_SCORED,
    STREAM_SIGNAL_CREATED,
    STREAM_STRUCTURE_UPDATED,
    RedisStreamBus,
)
from shared_py.observability import touch_worker_heartbeat

if TYPE_CHECKING:
    from paper_broker.config import PaperBrokerSettings
    from paper_broker.engine.broker import PaperBrokerService
    from paper_broker.strategy.engine import StrategyExecutionEngine

logger = logging.getLogger("paper_broker.worker")


def run_consumer_loop(
    settings: PaperBrokerSettings,
    broker: PaperBrokerService,
    bus: RedisStreamBus,
    stop: threading.Event,
    strategy_engine: StrategyExecutionEngine | None = None,
) -> None:
    group = settings.paper_worker_group
    consumer = settings.paper_worker_consumer
    streams = [
        STREAM_MARKET_TICK,
        STREAM_FUNDING_UPDATE,
        STREAM_SIGNAL_CREATED,
        STREAM_NEWS_SCORED,
        STREAM_DRAWING_UPDATED,
        STREAM_STRUCTURE_UPDATED,
    ]
    for s in streams:
        try:
            bus.ensure_group(s, group)
        except Exception as exc:
            logger.warning("ensure_group %s: %s", s, exc)
    logger.info("paper-broker consumer started group=%s streams=%s", group, len(streams))
    while not stop.is_set():
        had_work = False
        for stream in streams:
            try:
                batch = bus.consume(stream, group, consumer, count=10, block_ms=1500)
            except Exception as exc:
                logger.warning("consume %s failed: %s", stream, exc)
                continue
            for ev in batch:
                had_work = True
                try:
                    env = ev.envelope
                    if env.event_type == "strategy_registry_updated":
                        broker.apply_registry_envelope(env)
                    elif env.event_type == "market_tick":
                        broker.apply_envelope_tick(env)
                        now_ms = env.exchange_ts_ms or int(
                            env.payload.get("ts_ms") or time.time() * 1000
                        )
                        broker.process_tick(now_ms)
                    elif env.event_type == "funding_update":
                        broker.apply_envelope_funding(env)
                    elif strategy_engine is not None and settings.strategy_exec_enabled:
                        if env.event_type == "signal_created":
                            strategy_engine.handle_signal_created(env.payload, env.symbol)
                        elif env.event_type == "news_scored":
                            strategy_engine.handle_news_scored(env.payload, env.symbol)
                        elif env.event_type == "drawing_updated":
                            tf = str(env.timeframe or "5m")
                            strategy_engine.handle_drawing_updated(
                                env.payload, env.symbol, tf
                            )
                        elif env.event_type == "structure_updated":
                            strategy_engine.handle_structure_updated(
                                env.payload,
                                env.symbol,
                                str(env.timeframe or "5m"),
                            )
                except Exception as exc:
                    logger.exception("handler error: %s", exc)
                finally:
                    try:
                        bus.ack(stream, group, ev.message_id)
                    except Exception as exc:
                        logger.warning("ack failed: %s", exc)
        if not had_work:
            time.sleep(0.05)
        touch_worker_heartbeat("paper_broker")
    logger.info("paper-broker consumer stopped")
