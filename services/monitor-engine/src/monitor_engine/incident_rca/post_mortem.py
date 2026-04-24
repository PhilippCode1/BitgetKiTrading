from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import uuid
from typing import Any

import httpx
from shared_py.eventbus import RedisStreamBus, sample_event_streams_union_recent
from shared_py.observability.request_context import clear_incident_context, set_incident_context
from shared_py.service_auth import INTERNAL_SERVICE_HEADER

from monitor_engine.config import MonitorEngineSettings
from monitor_engine.incident_rca.health_snapshot import collect_service_ready_snapshot
from monitor_engine.storage.repo_post_mortem import (
    insert_post_mortem,
    update_telegram_enqueued,
    utc_now,
)

logger = logging.getLogger("monitor_engine.incident_rca")


def _llm_url(settings: MonitorEngineSettings) -> str:
    b = (settings.monitor_llm_orchestrator_url or "").rstrip("/")
    return f"{b}/llm/analyst/safety_incident_diagnosis"


def _alert_test_url(settings: MonitorEngineSettings) -> str:
    b = (settings.monitor_alert_engine_url or "").rstrip("/")
    return f"{b}/admin/test-alert"


def _auth_headers(settings: MonitorEngineSettings) -> dict[str, str]:
    key = (getattr(settings, "service_internal_api_key", None) or "").strip()
    h: dict[str, str] = {"Content-Type": "application/json"}
    if key:
        h[INTERNAL_SERVICE_HEADER] = key
    return h


async def _call_safety_rca(
    settings: MonitorEngineSettings,
    diagnostic: dict[str, Any],
    *,
    timeout_sec: float,
) -> tuple[str, dict[str, Any] | None]:
    key = (getattr(settings, "service_internal_api_key", None) or "").strip()
    if not key and getattr(settings, "production", False):
        return "skipped_no_internal_key", None
    pl = {
        "question_de": (
            "system:global_halt (Kill-Switch) ist aktiv. "
            "Was war der wahrscheinlichste Ausloeser laut beiliegender "
            "Eventbus- und Service-Health-Skizze? Kurz und mit Unsicherheit."
        ),
        "diagnostic_context_json": diagnostic,
        "provider_preference": "auto",
        "temperature": 0.15,
    }
    tmo = httpx.Timeout(timeout_sec)
    try:
        async with httpx.AsyncClient(timeout=tmo) as client:
            r = await client.post(
                _llm_url(settings),
                json=pl,
                headers=_auth_headers(settings),
            )
    except (httpx.RequestError, OSError) as exc:
        return f"httpx_error:{type(exc).__name__}", None
    if r.status_code != 200:
        return f"http_{r.status_code}", None
    data = r.json() if r.content else {}
    if not isinstance(data, dict):
        return "invalid_response", None
    if data.get("ok") is not True:
        return "orchestrator_not_ok", data
    res = data.get("result")
    if not isinstance(res, dict):
        return "no_result", None
    return "ok", res


def _post_mortem_report_path(pm_id: str) -> str:
    return f"/ops/post-mortems/{pm_id}"


async def _enqueue_telegram(
    settings: MonitorEngineSettings, *, pm_id: str, summary_hint: str
) -> bool:
    if not settings.monitor_telegram_post_mortem_enabled:
        return False
    tok = (getattr(settings, "admin_token", None) or "").strip()
    if not tok:
        return False
    h = _auth_headers(settings)
    h["X-Admin-Token"] = tok
    text = (
        f"P79 Post-Mortem bereit. id={pm_id}\n"
        f"Link: {_post_mortem_report_path(pm_id)} (GET monitor-engine, intern authentifiziert)\n"
        f"Hint: {summary_hint[:1200]}"
    )
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.post(
                _alert_test_url(settings),
                json={"text": text},
                headers=h,
            )
    except (httpx.RequestError, OSError) as exc:
        logger.warning("telegram enqueue failed: %s", exc)
        return False
    return 200 <= r.status_code < 300


async def run_incident_post_mortem_once(
    settings: MonitorEngineSettings,
    bus: RedisStreamBus,
    *,
    trigger: str = "system:global_halt",
    time_budget_sec: float | None = None,
) -> str:
    """
    Ein Post-Mortem: Eventbus(100) + Service-Health + safety_incident_diagnosis + optional Telegram.
    Liefert die post_mortem uuid.
    """
    pm_id = str(uuid.uuid4())
    icorr = f"rca:{pm_id[:8]}"
    t_budget = time_budget_sec
    if t_budget is None:
        t_budget = float(settings.monitor_incident_rca_global_budget_sec)
    t0 = time.perf_counter()
    set_incident_context(post_mortem_id=pm_id, incident_correlation_id=icorr)
    started = utc_now()
    redis_samples: list[dict[str, Any]] = []
    health: list[dict[str, Any]] = []
    llm_st = "not_run"
    llm_res: dict[str, Any] | None = None
    try:

        def _load_streams() -> list[dict[str, Any]]:
            return sample_event_streams_union_recent(
                bus.redis, total_limit=100
            )

        def _rem(s: float) -> float:
            return max(0.5, s - (time.perf_counter() - t0))

        redis_samples = await asyncio.to_thread(_load_streams)
        health = await collect_service_ready_snapshot(
            settings.service_urls,
            timeout_sec=min(2.5, _rem(t_budget)),
        )
        diag: dict[str, Any] = {
            "context_kind": "P79_global_halt_post_mortem",
            "trigger": trigger,
            "post_mortem_id": pm_id,
            "incident_correlation": icorr,
            "eventbus_last_events": redis_samples,
            "service_ready_probe": health,
        }
        remain = _rem(t_budget)
        llm_st, llm_res = await _call_safety_rca(
            settings, diag, timeout_sec=min(8.0, remain * 0.7)
        )
    finally:
        clear_incident_context()
    completed = utc_now()
    duration_ms = int((time.perf_counter() - t0) * 1000.0)
    rpath = _post_mortem_report_path(pm_id)
    summary_hint = ""
    if isinstance(llm_res, dict):
        summary_hint = str(
            llm_res.get("incident_summary_de") or llm_res.get("root_causes_de") or ""
        )
    try:
        insert_post_mortem(
            settings.database_url,
            post_mortem_id=pm_id,
            trigger=trigger,
            correlation_id=icorr,
            started_ts=started,
            completed_ts=completed,
            duration_ms=duration_ms,
            redis_event_samples=redis_samples,
            service_health=health,
            llm_status=llm_st,
            llm_result=llm_res,
            telegram_enqueued=False,
            report_url=rpath,
        )
    except (OSError, TypeError, ValueError) as exc:
        logger.exception("insert_post_mortem failed: %s", exc)
    tgram_b = _rem(3.0)
    if tgram_b > 0.1:
        if await _enqueue_telegram(
            settings, pm_id=pm_id, summary_hint=summary_hint
        ):
            with contextlib.suppress(OSError, TypeError, ValueError):
                update_telegram_enqueued(
                    settings.database_url, post_mortem_id=pm_id, enqueued=True
                )
    logger.info("incident post_mortem done id=%s ms=%s llm=%s", pm_id, duration_ms, llm_st)
    return pm_id
