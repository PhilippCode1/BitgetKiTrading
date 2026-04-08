from __future__ import annotations

import logging
import threading
from typing import Any

import redis
from shared_py.eventbus import (
    STREAM_NEWS_SCORED,
    STREAM_OPERATOR_INTEL,
    STREAM_RISK_ALERT,
    STREAM_SIGNAL_CREATED,
    STREAM_STRUCTURE_UPDATED,
    STREAM_SYSTEM_ALERT,
    STREAM_TRADE_CLOSED,
    EventEnvelope,
)
from shared_py.observability import touch_worker_heartbeat

from alert_engine.alerts.policies import evaluate_envelope
from alert_engine.config import Settings
from alert_engine.log_safety import safe_chat_ref
from alert_engine.storage.repo_dedupe import RepoDedupe
from alert_engine.storage.repo_outbox import RepoOutbox
from alert_engine.storage.repo_structure import RepoStructureTrend
from alert_engine.storage.repo_subscriptions import RepoSubscriptions
from alert_engine.worker.runtime_status import RuntimeStatus

logger = logging.getLogger("alert_engine.consumer")

CONSUMER_STREAMS = (
    STREAM_SIGNAL_CREATED,
    STREAM_STRUCTURE_UPDATED,
    STREAM_TRADE_CLOSED,
    STREAM_RISK_ALERT,
    STREAM_NEWS_SCORED,
    STREAM_SYSTEM_ALERT,
    STREAM_OPERATOR_INTEL,
)


def _ensure_groups(r: redis.Redis, group: str) -> None:
    for stream in CONSUMER_STREAMS:
        try:
            r.xgroup_create(stream, group, id="0", mkstream=True)
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise


def _process_envelope(
    env: EventEnvelope,
    *,
    settings: Settings,
    trend_repo: RepoStructureTrend,
    dedupe: RepoDedupe,
    subs: RepoSubscriptions,
    outbox: RepoOutbox,
    redis_client: Any | None = None,
) -> None:
    intents = evaluate_envelope(env, settings, trend_repo, redis_client)
    for intent in intents:
        if intent.dedupe_key:
            ttl_m = max(1, intent.dedupe_ttl_minutes or 1)
            if not dedupe.try_acquire(intent.dedupe_key, ttl_m):
                continue
        chats = subs.list_allowed_chat_ids()
        if not chats:
            logger.warning("no subscribers; skip alert_type=%s", intent.alert_type)
            continue
        pl = {**intent.payload, "text": intent.text}
        for cid in chats:
            outbox.insert_pending(
                alert_type=intent.alert_type,
                severity=intent.severity,
                symbol=intent.symbol,
                timeframe=intent.timeframe,
                dedupe_key=intent.dedupe_key,
                chat_id=cid,
                payload=pl,
            )
            logger.info("outbox inserted for chat=%s type=%s", safe_chat_ref(cid), intent.alert_type)


def apply_envelope_admin(env: EventEnvelope, settings: Settings) -> None:
    """Replay path (HTTP admin): same pipeline as Redis consumer."""
    dedupe = RepoDedupe(settings.database_url)
    trend_repo = RepoStructureTrend(settings.database_url)
    subs = RepoSubscriptions(settings.database_url)
    outbox = RepoOutbox(settings.database_url)
    _process_envelope(
        env,
        settings=settings,
        trend_repo=trend_repo,
        dedupe=dedupe,
        subs=subs,
        outbox=outbox,
    )


def consumer_loop(
    stop: threading.Event,
    settings: Settings,
    status: RuntimeStatus,
) -> None:
    if not settings.redis_url or not settings.database_url:
        logger.error("REDIS_URL or DATABASE_URL missing; consumer idle")
        return
    r = redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    dedupe = RepoDedupe(settings.database_url)
    trend_repo = RepoStructureTrend(settings.database_url)
    subs = RepoSubscriptions(settings.database_url)
    outbox = RepoOutbox(settings.database_url)
    group = settings.consumer_group
    consumer = settings.consumer_name
    _ensure_groups(r, group)
    streams = {s: ">" for s in CONSUMER_STREAMS}
    logger.info("alert-engine consumer started group=%s streams=%s", group, len(CONSUMER_STREAMS))
    while not stop.is_set():
        try:
            db_ok = True
            try:
                pend_ct = outbox.count_pending()
            except Exception:
                db_ok = False
                pend_ct = 0
            status.set_all(redis_ok=r.ping(), db_ok=db_ok, pending=pend_ct)
            items = r.xreadgroup(
                group,
                consumer,
                streams,
                count=settings.event_batch,
                block=settings.event_block_ms,
            )
            for stream_name, messages in items or []:
                for message_id, fields in messages:
                    raw = fields.get("data", "")
                    try:
                        env = EventEnvelope.model_validate_json(raw)
                        _process_envelope(
                            env,
                            settings=settings,
                            trend_repo=trend_repo,
                            dedupe=dedupe,
                            subs=subs,
                            outbox=outbox,
                            redis_client=r,
                        )
                        logger.debug(
                            "event ok stream=%s msg=%s event=%s",
                            stream_name,
                            message_id,
                            env.event_type,
                        )
                    except Exception as exc:
                        logger.exception("event processing failed: %s", exc)
                    finally:
                        r.xack(stream_name, group, message_id)
        except redis.RedisError as exc:
            logger.warning("redis error in consumer: %s", exc)
            status.set_all(redis_ok=False, db_ok=True, pending=0)
            stop.wait(2)
        except Exception as exc:
            logger.exception("consumer loop error: %s", exc)
            stop.wait(2)
        touch_worker_heartbeat("alert_engine_consumer")
