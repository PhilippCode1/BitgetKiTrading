"""Heartbeat-Task bleibt aktiv, wenn die Hauptroutine kooperativ blockt (await sleep)."""

from __future__ import annotations

import asyncio
import contextlib
import time
from unittest.mock import patch

from shared_py.observability.health import create_isolated_heartbeat_task


def test_isolated_heartbeat_continues_when_main_awaits_sleep_5s() -> None:
    """Nachweis-Constraint: Hauptschleife `await asyncio.sleep(5)` — Heartbeat-Task laeuft weiter."""
    calls: list[int] = []

    def _track(_name: str) -> None:
        calls.append(int(time.time() * 1000))

    async def _run() -> None:
        with patch("shared_py.observability.metrics.touch_worker_heartbeat", side_effect=_track):
            stop = asyncio.Event()
            task = create_isolated_heartbeat_task("test_hb", 1.0, stop)
            await asyncio.sleep(5.0)
            stop.set()
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    asyncio.run(_run())

    # mind. 3 Ticks trotz 5s Block in derselben Schleife (Haupt-Task = sleep, HB-Task separat)
    assert len(calls) >= 3
