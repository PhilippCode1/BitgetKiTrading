from __future__ import annotations

import logging
from typing import Any

from alert_engine.config import Settings
from alert_engine.storage.repo_state import RepoBotState
from alert_engine.telegram.api_client import TelegramApiClient
from alert_engine.telegram.commands import handle_update

logger = logging.getLogger("alert_engine.longpoll")


def parse_allowed_updates(s: Settings) -> list[str]:
    parts = [p.strip() for p in s.telegram_allowed_updates.split(",") if p.strip()]
    return parts or ["message", "callback_query"]


def run_longpoll_cycle(
    settings: Settings,
    api: TelegramApiClient,
    state_repo: RepoBotState,
    command_ctx: Any,
) -> None:
    if settings.telegram_mode.lower() != "getupdates":
        return
    last = state_repo.get_last_update_id()
    # Erstes Pollen: offset weglassen (Telegram liefert neueste Updates).
    offset = (last + 1) if last > 0 else None
    data = api.get_updates(
        offset=offset,
        timeout_sec=settings.telegram_longpoll_timeout_sec,
        allowed_updates=parse_allowed_updates(settings),
    )
    if not data.get("ok"):
        logger.debug("getUpdates not ok: %s", data)
        return
    max_id = last
    for upd in data.get("result") or []:
        uid = int(upd.get("update_id", 0))
        max_id = max(max_id, uid)
        handle_update(upd, command_ctx)
    if max_id > last:
        state_repo.set_last_update_id(max_id)
        logger.debug("advanced last_update_id to %s", max_id)
