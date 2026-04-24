from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import cast
from unittest.mock import MagicMock, patch

import httpx

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ME_SRC = REPO_ROOT / "services" / "monitor-engine" / "src"
for p in (str(REPO_ROOT), str(ME_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from monitor_engine.checks import services_http as m


def test_parse_worker_heartbeat_ts() -> None:
    now = 1_700_000_000.0
    body = (
        "# HELP h\n"
        f'worker_heartbeat_timestamp{{service="feature_engine"}} {now}\n'
    )
    assert m._parse_worker_heartbeat_ts(body, "feature_engine") == now
    assert m._parse_worker_heartbeat_ts(body, "other") is None


def test_local_async_probe_context() -> None:
    ctx = m._local_async_probe_context()
    assert "local_thread_name" in ctx
    assert "local_asyncio_task_name" in ctx


def test_metrics_probe_degraded_only_after_degrade_grace() -> None:
    old = time.time() - 20.0
    mtext = f'worker_heartbeat_timestamp{{service="feature_engine"}} {old}\n'

    async def fake_get(url: str, **_kw: object) -> httpx.Response:  # pragma: no cover
        u = str(url)
        if u.endswith("/metrics"):
            return httpx.Response(200, text=mtext, request=httpx.Request("GET", u))
        if u.endswith("/health"):
            return httpx.Response(200, json={"status": "ok"}, request=httpx.Request("GET", u))
        if u.endswith("/ready"):
            return httpx.Response(
                200, json={"ready": True, "checks": {}}, request=httpx.Request("GET", u)
            )
        return httpx.Response(404, request=httpx.Request("GET", u))

    client = MagicMock()
    client.get = cast(Callable[..., Awaitable[httpx.Response]], fake_get)

    async def _go() -> None:
        return await m.probe_service(
            cast(httpx.AsyncClient, client),
            "feature-engine",
            "http://t",
            timeout_sec=2.0,
            heartbeat_stale_warn_sec=10.0,
            heartbeat_stale_degrade_sec=15.0,
        )

    out = asyncio.run(_go())
    mres = [x for x in out if x.check_type == "metrics"][0]
    assert mres.status == "degraded"
    assert "worker_heartbeat" in mres.details
    assert mres.details.get("degraded_reason")


def test_metrics_probe_warn_only_in_window() -> None:
    old = time.time() - 12.0
    mtext = f'worker_heartbeat_timestamp{{service="feature_engine"}} {old}\n'

    async def fake_get(url: str, **_kw: object) -> httpx.Response:  # pragma: no cover
        u = str(url)
        if u.endswith("/metrics"):
            return httpx.Response(200, text=mtext, request=httpx.Request("GET", u))
        if u.endswith("/health"):
            return httpx.Response(200, json={"status": "ok"}, request=httpx.Request("GET", u))
        if u.endswith("/ready"):
            return httpx.Response(
                200, json={"ready": True, "checks": {}}, request=httpx.Request("GET", u)
            )
        return httpx.Response(404, request=httpx.Request("GET", u))

    client = MagicMock()
    client.get = cast(Callable[..., Awaitable[httpx.Response]], fake_get)

    with patch.object(m.logger, "warning") as wlog:
        async def _go() -> None:
            return await m.probe_service(
                cast(httpx.AsyncClient, client),
                "feature-engine",
                "http://t",
                timeout_sec=2.0,
                heartbeat_stale_warn_sec=10.0,
                heartbeat_stale_degrade_sec=15.0,
            )

        out = asyncio.run(_go())
    mres = [x for x in out if x.check_type == "metrics"][0]
    assert mres.status == "ok"
    assert mres.details.get("worker_heartbeat", {}).get("pre_alert") is True
    assert wlog.call_count >= 1
    msg = wlog.call_args[0][0] if wlog.call_args is not None else ""
    assert "Heartbeat delay detected" in str(msg)
