from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger("monitor_engine.services_http")

CheckType = str


@dataclass
class ServiceCheckResult:
    service_name: str
    check_type: CheckType
    status: str
    latency_ms: int | None
    details: dict[str, Any]


async def probe_service(
    client: httpx.AsyncClient,
    service_name: str,
    base_url: str,
    *,
    timeout_sec: float = 5.0,
) -> list[ServiceCheckResult]:
    base = base_url.rstrip("/")
    results: list[ServiceCheckResult] = []

    async def _one(
        path: str,
        check_type: CheckType,
    ) -> ServiceCheckResult:
        url = f"{base}{path}"
        t0 = time.perf_counter()
        try:
            r = await client.get(url, timeout=timeout_sec)
            ms = int((time.perf_counter() - t0) * 1000)
            ok = r.status_code < 500
            if check_type == "metrics" and r.status_code != 200:
                ok = False
            st = "ok" if ok else "fail"
            if check_type == "ready" and r.status_code == 200:
                try:
                    body = r.json()
                    if isinstance(body, dict) and body.get("ready") is False:
                        st = "degraded"
                except Exception:
                    pass
            return ServiceCheckResult(
                service_name=service_name,
                check_type=check_type,
                status=st,
                latency_ms=ms,
                details={"http_status": r.status_code, "url": url},
            )
        except Exception as exc:
            ms = int((time.perf_counter() - t0) * 1000)
            logger.warning("probe %s %s failed: %s", service_name, path, exc)
            return ServiceCheckResult(
                service_name=service_name,
                check_type=check_type,
                status="fail",
                latency_ms=ms,
                details={"error": str(exc)[:300], "url": url},
            )

    results.append(await _one("/health", "health"))
    results.append(await _one("/ready", "ready"))
    results.append(await _one("/metrics", "metrics"))
    return results
