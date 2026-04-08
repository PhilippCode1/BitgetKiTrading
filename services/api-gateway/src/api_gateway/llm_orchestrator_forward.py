"""HTTP-Forward vom Gateway zum internen LLM-Orchestrator (nur Dienst-zu-Dienst)."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

from shared_py.observability.correlation import log_correlation_fields
from shared_py.observability.request_context import (
    get_current_trace_ids,
    get_outbound_trace_headers,
)
from shared_py.service_auth import (
    INTERNAL_SERVICE_HEADER,
    internal_service_auth_required,
)

from api_gateway.config import GatewaySettings

logger = logging.getLogger("api_gateway.llm_orchestrator_forward")


class LLMOrchestratorForwardHttpError(Exception):
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self.payload = payload
        super().__init__(f"llm-orchestrator HTTP {status_code}")


def post_llm_orchestrator_json(
    settings: GatewaySettings,
    subpath: str,
    body: dict[str, Any],
    *,
    timeout_sec: float = 120.0,
) -> Any:
    base = settings.llm_orchestrator_http_base()
    if not base:
        raise RuntimeError(
            "LLM-Orchestrator-Basis-URL fehlt: LLM_ORCH_BASE_URL setzen oder "
            "HEALTH_URL_LLM_ORCHESTRATOR (mit Scheme und Host)"
        )
    ik = str(getattr(settings, "service_internal_api_key", "") or "").strip()
    if internal_service_auth_required(settings) and not ik:
        raise RuntimeError(
            "INTERNAL_API_KEY fehlt fuer LLM-Orchestrator-Forward "
            "(Production/interner Key Pflicht; gleicher Wert wie llm-orchestrator)."
        )
    path = subpath if subpath.startswith("/") else f"/{subpath}"
    url = f"{base}{path}"
    payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "User-Agent": "api-gateway-llm-forward/1.0",
    }
    headers.update(get_outbound_trace_headers())
    if ik:
        headers[INTERNAL_SERVICE_HEADER] = ik
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers=headers,
    )
    t0 = time.perf_counter()
    rid, cid = get_current_trace_ids()
    trace_extra = log_correlation_fields(request_id=rid, correlation_id=cid)
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read()
            elapsed = time.perf_counter() - t0
            if not raw:
                logger.info(
                    "llm forward empty body duration_s=%.3f path=%s",
                    elapsed,
                    path,
                    extra=trace_extra,
                )
                return {}
            out = json.loads(raw.decode("utf-8"))
            logger.info(
                "llm forward ok duration_s=%.3f path=%s",
                elapsed,
                path,
                extra=trace_extra,
            )
            return out
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
        try:
            parsed: Any = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"detail": raw[:4000]}
        logger.warning(
            "llm forward HTTP %s duration_s=%.3f path=%s — Orchestrator pruefen; "
            "502 oft Provider/Key/Schema",
            e.code,
            time.perf_counter() - t0,
            path,
            extra=trace_extra,
        )
        raise LLMOrchestratorForwardHttpError(int(e.code), parsed) from e
    except urllib.error.URLError as e:
        logger.warning("llm forward URL error %s: %s", path, e, extra=trace_extra)
        raise RuntimeError(str(e.reason or e)) from e


def get_llm_orchestrator_json(
    settings: GatewaySettings,
    subpath: str,
    *,
    timeout_sec: float = 30.0,
) -> Any:
    """GET ohne Body — z. B. Governance-Summary (interner Service-Key)."""
    base = settings.llm_orchestrator_http_base()
    if not base:
        raise RuntimeError(
            "LLM-Orchestrator-Basis-URL fehlt: LLM_ORCH_BASE_URL setzen oder "
            "HEALTH_URL_LLM_ORCHESTRATOR (mit Scheme und Host)"
        )
    ik = str(getattr(settings, "service_internal_api_key", "") or "").strip()
    if internal_service_auth_required(settings) and not ik:
        raise RuntimeError(
            "INTERNAL_API_KEY fehlt fuer LLM-Orchestrator-Forward "
            "(Production/interner Key Pflicht; gleicher Wert wie llm-orchestrator)."
        )
    path = subpath if subpath.startswith("/") else f"/{subpath}"
    url = f"{base}{path}"
    headers: dict[str, str] = {
        "Accept": "application/json",
        "User-Agent": "api-gateway-llm-forward/1.0",
    }
    headers.update(get_outbound_trace_headers())
    if ik:
        headers[INTERNAL_SERVICE_HEADER] = ik
    req = urllib.request.Request(url, method="GET", headers=headers)
    t0 = time.perf_counter()
    rid, cid = get_current_trace_ids()
    trace_extra = log_correlation_fields(request_id=rid, correlation_id=cid)
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read()
            elapsed = time.perf_counter() - t0
            if not raw:
                logger.info(
                    "llm GET empty body duration_s=%.3f path=%s",
                    elapsed,
                    path,
                    extra=trace_extra,
                )
                return {}
            out = json.loads(raw.decode("utf-8"))
            logger.info(
                "llm GET ok duration_s=%.3f path=%s",
                elapsed,
                path,
                extra=trace_extra,
            )
            return out
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
        try:
            parsed: Any = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"detail": raw[:4000]}
        logger.warning(
            "llm GET HTTP %s duration_s=%.3f path=%s",
            e.code,
            time.perf_counter() - t0,
            path,
            extra=trace_extra,
        )
        raise LLMOrchestratorForwardHttpError(int(e.code), parsed) from e
    except urllib.error.URLError as e:
        logger.warning("llm GET URL error %s: %s", path, e, extra=trace_extra)
        raise RuntimeError(str(e.reason or e)) from e
