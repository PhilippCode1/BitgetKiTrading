from __future__ import annotations

import logging
import threading

import redis
from shared_py.observability import touch_worker_heartbeat

from alert_engine.alerts.rate_limit import GlobalSendRateLimiter, PerChatMinuteLimiter
from alert_engine.config import Settings
from alert_engine.log_safety import safe_chat_ref
from alert_engine.storage.repo_outbox import RepoOutbox
from alert_engine.telegram.api_client import TelegramApiClient
from alert_engine.worker.runtime_status import RuntimeStatus

logger = logging.getLogger("alert_engine.sender")


def sender_loop(
    stop: threading.Event,
    settings: Settings,
    status: RuntimeStatus,
    api: TelegramApiClient,
) -> None:
    if not settings.database_url:
        return
    outbox = RepoOutbox(settings.database_url)
    global_lim = GlobalSendRateLimiter(settings.telegram_send_max_per_sec)
    chat_lim = PerChatMinuteLimiter(settings.telegram_send_max_per_min_per_chat)
    r_cli: redis.Redis | None = None
    if settings.redis_url:
        try:
            r_cli = redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
        except Exception as exc:
            logger.warning("outbox sender redis optional connect failed: %s", exc)
    logger.info("outbox sender started dry_run=%s", settings.telegram_dry_run)
    while not stop.is_set():
        try:
            pending_n = outbox.count_pending()
            r_ok, d_ok, _ = status.snapshot()
            status.set_all(redis_ok=r_ok, db_ok=True, pending=pending_n)
            batch = outbox.claim_pending_for_send(15)
            for row in batch:
                if stop.is_set():
                    break
                aid = str(row["alert_id"])
                chat_id = int(row["chat_id"])
                pl = row["payload"]
                if isinstance(pl, str):
                    import json

                    pl = json.loads(pl)
                text = str(pl.get("text") or "")
                reply_to = pl.get("reply_to_telegram_message_id")
                reply_id = int(reply_to) if reply_to is not None else None
                if not chat_lim.acquire(chat_id):
                    logger.warning("per-chat rate limit chat=%s requeue", safe_chat_ref(chat_id))
                    outbox.requeue_sending_to_pending(aid)
                    continue
                global_lim.acquire()
                try:
                    res = api.send_message(chat_id, text, reply_to_message_id=reply_id)
                    ok = bool(res.get("ok"))
                    if ok:
                        mid = None
                        result = res.get("result")
                        if isinstance(result, dict) and result.get("message_id") is not None:
                            mid = int(result["message_id"])
                        outbox.mark_sent(
                            aid,
                            telegram_message_id=mid,
                            simulated=settings.telegram_dry_run or bool(res.get("dry_run")),
                        )
                        cid = pl.get("correlation_id")
                        if (
                            r_cli is not None
                            and isinstance(cid, str)
                            and cid.strip()
                            and mid is not None
                            and not settings.telegram_dry_run
                        ):
                            try:
                                r_cli.setex(
                                    f"ae:opintel:thread:{cid.strip()}",
                                    int(settings.telegram_operator_thread_ttl_sec),
                                    str(mid),
                                )
                            except Exception as exc:
                                logger.warning("thread anchor redis set failed: %s", exc)
                        logger.info(
                            "send done alert_id=%s simulated=%s",
                            aid,
                            settings.telegram_dry_run,
                        )
                    else:
                        err = str(res.get("error", "telegram_error"))
                        outbox.requeue_send_or_fail(
                            aid,
                            err,
                            max_attempts=settings.telegram_outbox_max_send_attempts,
                        )
                except Exception as exc:
                    logger.exception("send failed: %s", exc)
                    outbox.requeue_send_or_fail(
                        aid,
                        str(exc)[:500],
                        max_attempts=settings.telegram_outbox_max_send_attempts,
                    )
        except Exception as exc:
            logger.exception("sender loop: %s", exc)
        touch_worker_heartbeat("alert_engine_outbox_sender")
        stop.wait(0.5)
