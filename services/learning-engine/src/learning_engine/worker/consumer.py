from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

from redis import Redis
from shared_py.observability import touch_worker_heartbeat

from learning_engine.config import LearningEngineSettings
from learning_engine.storage.connection import db_connect
from learning_engine.storage.repo_processed import already_processed, mark_processed
from learning_engine.worker.processors import (
    process_signal_created,
    process_trade_closed,
    process_trade_opened,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger("learning_engine.consumer")


def _ensure_group(r: Redis, stream: str, group: str) -> None:
    try:
        r.xgroup_create(stream, group, id="0", mkstream=True)
    except Exception as exc:
        if "BUSYGROUP" in str(exc):
            return
        raise


def run_consumer_loop(settings: LearningEngineSettings, stop: threading.Event) -> None:
    r = Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=30)
    group = settings.learn_consumer_group
    consumer = settings.learn_consumer_name

    streams = [
        settings.learn_stream_trade_closed,
        settings.learn_stream_trade_opened,
        settings.learn_stream_trade_updated,
        settings.learn_stream_signal_created,
    ]
    if settings.learn_consume_optional_streams:
        streams.extend(
            [
                settings.learn_stream_news_scored,
                settings.learn_stream_structure_updated,
                settings.learn_stream_drawing_updated,
                settings.learn_stream_risk_alert,
            ]
        )

    for s in streams:
        try:
            _ensure_group(r, s, group)
        except Exception as exc:
            logger.warning("ensure_group %s: %s", s, exc)

    stream_ids = {s: ">" for s in streams}
    block = settings.eventbus_block_ms
    count = settings.eventbus_count

    logger.info("learning-engine consumer started group=%s streams=%s", group, len(streams))

    while not stop.is_set():
        try:
            resp = r.xreadgroup(group, consumer, stream_ids, count=count, block=block)
        except Exception as exc:
            logger.warning("xreadgroup failed: %s", exc)
            time.sleep(1)
            touch_worker_heartbeat("learning_engine")
            continue
        touch_worker_heartbeat("learning_engine")
        if not resp:
            continue
        for stream_name, messages in resp:
            for msg_id, fields in messages:
                raw = fields.get("data", "")
                skip_process = False
                with db_connect(settings.database_url) as conn:
                    if already_processed(conn, stream_name, msg_id):
                        logger.info(
                            "idempotent skip stream=%s message_id=%s",
                            stream_name,
                            msg_id,
                        )
                        skip_process = True
                if skip_process:
                    try:
                        r.xack(stream_name, group, msg_id)
                    except Exception as exc:
                        logger.warning("ack failed: %s", exc)
                    continue
                try:
                    from shared_py.eventbus import EventEnvelope

                    env = EventEnvelope.model_validate_json(raw)
                    if stream_name == settings.learn_stream_trade_closed and env.event_type == "trade_closed":
                        process_trade_closed(
                            settings,
                            env,
                            stream=stream_name,
                            redis_message_id=msg_id,
                        )
                    elif stream_name == settings.learn_stream_signal_created and env.event_type == "signal_created":
                        process_signal_created(
                            settings,
                            env,
                            stream=stream_name,
                            redis_message_id=msg_id,
                        )
                    elif stream_name == settings.learn_stream_trade_opened and env.event_type == "trade_opened":
                        process_trade_opened(
                            settings,
                            env,
                            stream=stream_name,
                            redis_message_id=msg_id,
                        )
                    else:
                        with db_connect(settings.database_url) as conn2:
                            with conn2.transaction():
                                mark_processed(conn2, stream_name, msg_id)
                except Exception:
                    logger.exception("process failed stream=%s id=%s", stream_name, msg_id)
                    try:
                        with db_connect(settings.database_url) as conn_poison:
                            with conn_poison.transaction():
                                mark_processed(conn_poison, stream_name, msg_id)
                    except Exception as exc_poison:
                        logger.warning("mark_processed after failure: %s", exc_poison)
                try:
                    r.xack(stream_name, group, msg_id)
                except Exception as exc:
                    logger.warning("ack failed: %s", exc)

    logger.info("learning-engine consumer stopped")
