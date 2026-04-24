from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Any

import httpx


def ready_url_for_entry(base: str) -> str:
    """MONITOR-Eintrag: Service-Base oder vollqualifizierter /ready-Pfad."""
    b = (base or "").strip().rstrip("/")
    if not b:
        return ""
    if b.endswith("/ready") or b.endswith("/health"):
        return b
    return f"{b}/ready"


async def collect_service_ready_snapshot(
    service_base_urls: dict[str, str],
    *,
    timeout_sec: float = 2.5,
) -> list[dict[str, Any]]:
    """P79: flache /ready-Matrix (17+ Dienste aus MONITOR_SERVICE_URLS)."""
    out: list[dict[str, Any]] = []
    tmo = httpx.Timeout(timeout_sec)

    async def _one(
        client: httpx.AsyncClient, name: str, base: str, sink: list[dict[str, Any]]
    ) -> None:
        url = ready_url_for_entry(base)
        t0 = time.perf_counter()
        try:
            r = await client.get(url)
            ms = int((time.perf_counter() - t0) * 1000)
            body: dict[str, Any] = {}
            ct = (r.text or "")[:1]
            if r.content and ct == "{":
                with contextlib.suppress(Exception):
                    j = r.json()
                    if isinstance(j, dict):
                        body = j
            st = "ok" if r.status_code < 500 else "fail"
            row: dict[str, Any] = {
                "service": name,
                "url": url,
                "http_status": r.status_code,
                "latency_ms": ms,
                "status": st,
            }
            if "ready" in body:
                row["ready"] = body.get("ready")
            sink.append(row)
        except (httpx.RequestError, OSError, TypeError, ValueError) as exc:
            sink.append(
                {
                    "service": name,
                    "url": url,
                    "status": "error",
                    "error": str(exc)[:500],
                }
            )

    async with httpx.AsyncClient(timeout=tmo) as client:
        await asyncio.gather(
            *(
                _one(client, n, u, out)
                for n, u in service_base_urls.items()
                if n and (u or "").strip()
            ),
        )
    out.sort(key=lambda x: str(x.get("service") or ""))
    return out
