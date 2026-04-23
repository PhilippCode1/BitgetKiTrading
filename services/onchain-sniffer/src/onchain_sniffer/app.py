from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from prometheus_client import make_asgi_app

from onchain_sniffer.config import OnchainSnifferSettings
from onchain_sniffer.eth_listener import run_eth_mempool_listener
from onchain_sniffer.solana_ws import run_solana_listener
from shared_py.eventbus import RedisStreamBus

logger = logging.getLogger("onchain_sniffer.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = OnchainSnifferSettings()
    bus = RedisStreamBus.from_url(settings.redis_url)
    app.state.settings = settings
    app.state.bus = bus
    tasks: list[asyncio.Task[Any]] = []
    if settings.eth_listener_enabled and settings.has_eth_stack:
        tasks.append(asyncio.create_task(run_eth_mempool_listener(settings, bus)))
    if settings.solana_listener_enabled:
        tasks.append(asyncio.create_task(run_solana_listener(settings, bus)))
    app.state.bg_tasks = tasks
    yield
    for t in tasks:
        t.cancel()
    for t in tasks:
        try:
            await t
        except asyncio.CancelledError:
            pass
    try:
        bus.close()
    except Exception as exc:
        logger.debug("bus close: %s", exc)


def build_app() -> FastAPI:
    app = FastAPI(title="onchain-sniffer", lifespan=lifespan)
    app.mount("/metrics", make_asgi_app())

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def ready() -> dict[str, Any]:
        s = getattr(app.state, "settings", None)
        if s is None:
            return {"status": "starting"}
        return {
            "status": "ready",
            "eth_listener": bool(s.eth_listener_enabled and s.has_eth_stack),
            "solana_listener": bool(s.solana_listener_enabled and s.solana_ws_url),
        }

    return app
