from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger("monitor_engine.services_http")

CheckType = str


def _summarize_ready_body(body: dict[str, Any]) -> str:
    ch = body.get("checks")
    if not isinstance(ch, dict):
        return f"ready={body.get('ready')!r} (no checks dict, keys={list(body.keys())[:8]!r})"
    bad: list[str] = []
    for k, v in ch.items():
        if isinstance(v, dict) and v.get("ok") is False:
            d = v.get("detail", "")
            bad.append(f"{k}={d!r}" if d else k)
    if not bad:
        return f"ready={body.get('ready')!r} (all check dicts ok or empty)"
    return "not_ready: " + "; ".join(bad[:6])


def _ready_streak_key(service_name: str) -> str:
    return f"{service_name}:/ready"


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
    ready_fail_streaks: dict[str, int] | None = None,
    ready_fails_to_degrade: int = 2,
) -> list[ServiceCheckResult]:
    base = base_url.rstrip("/")
    results: list[ServiceCheckResult] = []
    streaks = ready_fail_streaks if ready_fail_streaks is not None else {}
    sk = _ready_streak_key(service_name)
    n_fail = max(1, int(ready_fails_to_degrade))

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
            details: dict[str, Any] = {"http_status": r.status_code, "url": url}
            if check_type == "ready" and r.status_code == 200:
                try:
                    body = r.json() if r.content else {}
                except Exception as exc:
                    body = {}
                    details["json_error"] = str(exc)[:200]
                if isinstance(body, dict) and body.get("ready") is True:
                    streaks[sk] = 0
                elif isinstance(body, dict) and body.get("ready") is False:
                    reason = _summarize_ready_body(body)
                    cur = int(streaks.get(sk, 0)) + 1
                    streaks[sk] = cur
                    details["not_ready_details"] = reason
                    details["not_ready_streak"] = cur
                    details["not_ready_streak_threshold"] = n_fail
                    if cur < n_fail:
                        st = "ok"
                        details["degraded_suppressed"] = True
                        logger.warning(
                            "service ready soft-fail (no aggregate degraded yet) service=%s url=%s "
                            "streak=%s/%s: %s",
                            service_name,
                            url,
                            cur,
                            n_fail,
                            reason,
                        )
                    else:
                        st = "degraded"
                        details["degraded_reason"] = (
                            f"ready=false for {cur} consecutive probe(s) (threshold={n_fail}): {reason}"
                        )
                        logger.error(
                            "service ready hardened-degraded service=%s url=%s: %s",
                            service_name,
                            url,
                            details["degraded_reason"],
                        )
            elif check_type == "ready" and r.status_code != 200:
                details["probe_note"] = (
                    f"ready endpoint http_status={r.status_code} (streak only fuer JSON ready=false, nicht fuer HTTP-Fehler)"
                )
                logger.warning(
                    "service %s /ready non-200 status=%s url=%s (fail status in matrix, no ready-streak)",
                    service_name,
                    r.status_code,
                    url,
                )
            return ServiceCheckResult(
                service_name=service_name,
                check_type=check_type,
                status=st,
                latency_ms=ms,
                details=details,
            )
        except Exception as exc:
            ms = int((time.perf_counter() - t0) * 1000)
            logger.warning(
                "probe %s %s failed: %s",
                service_name,
                path,
                exc,
            )
            return ServiceCheckResult(
                service_name=service_name,
                check_type=check_type,
                status="fail",
                latency_ms=ms,
                details={
                    "error": str(exc)[:300],
                    "url": url,
                    "degraded_reason": (
                        f"probe exception (no ready-streak): {exc!s}"
                        if check_type == "ready"
                        else str(exc)[:200]
                    ),
                },
            )

    results.append(await _one("/health", "health"))
    results.append(await _one("/ready", "ready"))
    results.append(await _one("/metrics", "metrics"))
    return results
