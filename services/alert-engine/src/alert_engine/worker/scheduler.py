from __future__ import annotations

import logging
import threading

from shared_py.observability import touch_worker_heartbeat

from alert_engine.config import Settings
from alert_engine.storage.repo_audit import RepoAudit
from alert_engine.storage.repo_outbox import RepoOutbox
from alert_engine.storage.repo_state import RepoBotState
from alert_engine.storage.repo_subscriptions import RepoSubscriptions
from alert_engine.storage.repo_telegram_operator import RepoTelegramOperator
from alert_engine.telegram.api_client import TelegramApiClient
from alert_engine.telegram.commands import CommandContext
from alert_engine.telegram.longpoll import run_longpoll_cycle
from alert_engine.worker.event_consumer import consumer_loop
from alert_engine.worker.outbox_sender import sender_loop
from alert_engine.worker.runtime_status import RuntimeStatus

logger = logging.getLogger("alert_engine.scheduler")


class WorkerController:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self.status = RuntimeStatus()
        self._api = TelegramApiClient(settings)

    def start(self) -> None:
        if not self._settings.database_url:
            logger.error("DATABASE_URL missing")
            return
        subs = RepoSubscriptions(self._settings.database_url)
        ids = self._settings.parsed_allowed_chat_ids()
        try:
            subs.ensure_allowed_from_env(ids)
        except Exception:
            logger.exception(
                "chat_subscriptions sync from TELEGRAM_ALLOWED_CHAT_IDS failed "
                "(DB/Migration pruefen)"
            )
        else:
            if ids:
                logger.info("chat_subscriptions synced from env count=%s", len(ids))
            else:
                logger.info(
                    "chat_subscriptions: keine TELEGRAM_ALLOWED_CHAT_IDS gesetzt "
                    "(Chats koennen spaeter per /start o. a. angebunden werden)"
                )

        t1 = threading.Thread(
            target=consumer_loop,
            args=(self._stop, self._settings, self.status),
            name="ae-consumer",
            daemon=True,
        )
        t2 = threading.Thread(
            target=sender_loop,
            args=(self._stop, self._settings, self.status, self._api),
            name="ae-sender",
            daemon=True,
        )
        t3 = threading.Thread(target=self._telegram_thread, name="ae-telegram", daemon=True)
        self._threads = [t1, t2, t3]
        for t in self._threads:
            t.start()
        logger.info(
            "alert-engine background threads started consumer_group=%s sender=%s telegram_mode=%s",
            self._settings.consumer_group,
            "outbox_sender",
            self._settings.telegram_mode,
        )

    def stop(self) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=5)

    def _telegram_thread(self) -> None:
        state_repo = RepoBotState(self._settings.database_url)
        subs = RepoSubscriptions(self._settings.database_url)
        audit = RepoAudit(self._settings.database_url)
        while not self._stop.is_set():
            try:
                ob = RepoOutbox(self._settings.database_url)
                tg_op = RepoTelegramOperator(self._settings.database_url)
                r_ok, d_ok, pend = self.status.snapshot()
                ctx = CommandContext(
                    settings=self._settings,
                    subs=subs,
                    audit=audit,
                    outbox=ob,
                    api=self._api,
                    redis_ok=r_ok,
                    db_ok=d_ok,
                    pending_outbox=pend,
                    tg_operator=tg_op,
                )
                run_longpoll_cycle(self._settings, self._api, state_repo, ctx)
            except Exception:
                logger.exception("telegram thread error")
            touch_worker_heartbeat("alert_engine_telegram")
            self._stop.wait(0.2)
