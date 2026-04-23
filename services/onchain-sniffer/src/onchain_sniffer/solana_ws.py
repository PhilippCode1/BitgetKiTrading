"""Solana: Platzhalter — `logsSubscribe`/Prioritaets-Fee-Streams koennen spaeter angebunden werden."""

from __future__ import annotations

import asyncio
import logging

from onchain_sniffer.config import OnchainSnifferSettings

try:
    from solana.rpc.async_api import AsyncClient  # noqa: F401 — solana-py (optional)
except ImportError:
    AsyncClient = None  # type: ignore[misc, assignment]

logger = logging.getLogger("onchain_sniffer.solana_ws")


async def run_solana_listener(settings: OnchainSnifferSettings, _bus) -> None:
    if not settings.solana_ws_url or not settings.solana_listener_enabled:
        logger.info("Solana-Sniffer aus (SOLANA_WS_URL / ONCHAIN_SOLANA_LISTENER_ENABLED)")
        return
    while True:
        logger.warning(
            "Solana Mempool/Raydium-Deep-Subscribe ist Platzhalter — URL gesetzt aber Logik noch nicht aktiv."
        )
        await asyncio.sleep(3600.0)
