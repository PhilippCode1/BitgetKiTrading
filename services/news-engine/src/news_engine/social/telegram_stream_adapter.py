from __future__ import annotations

import asyncio
import logging
from typing import Any

from news_engine.social.types import SocialIncomingMessage

logger = logging.getLogger("news_engine.social.telegram")

_TELETHON_IMPORT_ERROR: Exception | None = None
try:
    from telethon import TelegramClient, events  # type: ignore[import-untyped]
    from telethon.sessions import StringSession  # type: ignore[import-untyped]
except Exception as exc:  # pragma: no cover — optional Abhaengigkeit
    TelegramClient = None  # type: ignore[misc, assignment]
    events = None  # type: ignore[misc, assignment]
    StringSession = None  # type: ignore[misc, assignment]
    _TELETHON_IMPORT_ERROR = exc


def telethon_available() -> bool:
    return TelegramClient is not None and StringSession is not None and events is not None


class TelegramStreamAdapter:
    """Alpha-Kanaele via Telethon; setzt SOCIAL_TELEGRAM_ENABLED + Session voraus."""

    def __init__(
        self,
        *,
        api_id: int,
        api_hash: str,
        session_string: str,
        channel_specs: list[str],
    ) -> None:
        self._api_id = api_id
        self._api_hash = api_hash.strip()
        self._session_string = session_string.strip()
        self._channels = [c.strip() for c in channel_specs if c.strip()]

    async def run(self, queue: asyncio.Queue[SocialIncomingMessage], stop: asyncio.Event) -> None:
        if not telethon_available():
            logger.warning("Telethon nicht installiert: %s", _TELETHON_IMPORT_ERROR)
            return
        if not self._channels:
            logger.warning("TelegramStreamAdapter: keine TELEGRAM_ALPHA_CHANNELS gesetzt")
            return
        assert TelegramClient is not None and StringSession is not None and events is not None

        session = StringSession(self._session_string)
        client = TelegramClient(session, self._api_id, self._api_hash)

        @client.on(events.NewMessage(chats=self._channels))
        async def _handler(event: Any) -> None:
            if stop.is_set():
                return
            text = (getattr(event, "raw_text", None) or event.text or "").strip()
            if not text:
                return
            sender = await event.get_sender()
            author_id = str(getattr(sender, "id", "unknown"))
            followers: int | None = None
            if sender is not None:
                fc = getattr(sender, "followers_count", None)
                if fc is not None:
                    try:
                        followers = int(fc)
                    except (TypeError, ValueError):
                        followers = None
            ext = f"tg:{event.chat_id}:{event.id}"
            await queue.put(
                SocialIncomingMessage(
                    source="telegram",
                    text=text,
                    author_id=author_id,
                    external_id=ext,
                    followers=followers,
                )
            )

        await client.connect()
        if not await client.is_user_authorized():
            logger.error("TelegramStreamAdapter: Session nicht autorisiert")
            return
        logger.info("TelegramStreamAdapter verbunden, Kanaele=%s", len(self._channels))
        stop_wait = asyncio.create_task(stop.wait())
        run_dc = asyncio.create_task(client.run_until_disconnected())
        try:
            _, pending = await asyncio.wait(
                {stop_wait, run_dc},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()
        finally:
            if client.is_connected():
                await client.disconnect()
