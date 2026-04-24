from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import FastAPI
from shared_py.eventbus import RedisStreamBus
from shared_py.observability.global_halt_redis import (
    REDIS_KEY_GLOBAL_HALT,
    parse_global_halt_value,
)

from monitor_engine.config import MonitorEngineSettings
from monitor_engine.incident_rca.post_mortem import run_incident_post_mortem_once

logger = logging.getLogger("monitor_engine.incident_watcher")

_last_halt: bool = False
_last_post_mortem_ts: float = 0.0
_lock = asyncio.Lock()


def _get_halt_raw(redis: Any) -> str | None:
    try:
        v = redis.get(REDIS_KEY_GLOBAL_HALT)
        if v is None:
            return None
        if isinstance(v, bytes):
            return v.decode("utf-8", errors="replace")
        return str(v)
    except (OSError, TypeError, ValueError) as exc:
        logger.warning("global_halt get failed: %s", exc)
        return None


async def _incident_watcher(app: FastAPI) -> None:
    global _last_halt
    global _last_post_mortem_ts
    settings: MonitorEngineSettings = app.state.settings
    bus: RedisStreamBus = app.state.bus
    if not settings.monitor_incident_rca_enabled:
        logger.info("incident RCA watcher disabled (MONITOR_INCIDENT_RCA_ENABLED=0)")
        return
    # Erster Poll: Halt-Startzustand ohne Flanke (kein doppelter Run nach Deploy)
    raw0 = await asyncio.to_thread(_get_halt_raw, bus.redis)
    _last_halt = parse_global_halt_value(raw0)
    interval = 1.0
    while True:
        try:
            raw = await asyncio.to_thread(_get_halt_raw, bus.redis)
            now_h = parse_global_halt_value(raw)
            if now_h and not _last_halt:
                dsec = int(settings.monitor_incident_rca_debounce_sec)
                if dsec > 0:
                    nowm = time.monotonic()
                    if nowm - _last_post_mortem_ts < float(dsec):
                        logger.info("incident RCA debounce skip (%ss)", dsec)
                    else:
                        async with _lock:
                            await run_incident_post_mortem_once(
                                settings, bus, trigger=REDIS_KEY_GLOBAL_HALT
                            )
                        _last_post_mortem_ts = time.monotonic()
                else:
                    async with _lock:
                        await run_incident_post_mortem_once(
                            settings, bus, trigger=REDIS_KEY_GLOBAL_HALT
                        )
                    _last_post_mortem_ts = time.monotonic()
            _last_halt = now_h
        except asyncio.CancelledError:
            break
        except (OSError, TypeError, ValueError, RuntimeError) as exc:
            logger.exception("incident watcher tick: %s", exc)
        await asyncio.sleep(interval)


def start_global_halt_watcher(app: FastAPI) -> asyncio.Task[None]:
    t = asyncio.create_task(_incident_watcher(app), name="incident-halt-watcher")
    app.state.incident_watcher_task = t
    return t
