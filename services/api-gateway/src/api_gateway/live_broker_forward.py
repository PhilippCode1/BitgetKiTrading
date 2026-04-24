"""HTTP-Forward vom Gateway zum internen live-broker (Notfall-/Safety-Mutationen)."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

from shared_py.observability.apex_trace import merge_gateway_response_apex
from shared_py.observability.request_context import get_outbound_trace_headers
from shared_py.service_auth import INTERNAL_SERVICE_HEADER, internal_service_auth_required

from api_gateway.config import GatewaySettings
from api_gateway.gateway_metrics import observe_live_broker_forward

logger = logging.getLogger("api_gateway.live_broker_forward")


class LiveBrokerForwardHttpError(Exception):
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self.payload = payload
        super().__init__(f"live-broker HTTP {status_code}")


def post_live_broker_json(
    settings: GatewaySettings,
    subpath: str,
    body: dict[str, Any],
    *,
    timeout_sec: float = 45.0,
) -> Any:
    base = settings.live_broker_http_base()
    if not base:
        raise RuntimeError(
            "live-broker Basis-URL fehlt: LIVE_BROKER_BASE_URL setzen oder "
            "HEALTH_URL_LIVE_BROKER (Scheme/Host, z. B. http://live-broker:8120/ready)"
        )
    path = subpath if subpath.startswith("/") else f"/{subpath}"
    url = f"{base}{path}"
    payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "User-Agent": "api-gateway-live-broker-forward/1.0",
    }
    headers.update(get_outbound_trace_headers())
    ik = str(getattr(settings, "service_internal_api_key", "") or "").strip()
    if internal_service_auth_required(settings) and not ik:
        raise RuntimeError(
            "INTERNAL_API_KEY fehlt fuer live-broker Forward "
            "(Production oder Key-Pflicht; gleicher Wert wie im live-broker)"
        )
    if ik:
        headers[INTERNAL_SERVICE_HEADER] = ik
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers=headers,
    )
    t0 = time.perf_counter()
    t_gw0_ns = time.time_ns()
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read()
            elapsed = time.perf_counter() - t0
            t_gw1_ns = time.time_ns()
            if not raw:
                observe_live_broker_forward(result="success", elapsed_sec=elapsed)
                return {}
            body = json.loads(raw.decode("utf-8"))
            observe_live_broker_forward(result="success", elapsed_sec=elapsed)
            if isinstance(body, dict):
                body = merge_gateway_response_apex(body, t_gw0_ns=t_gw0_ns, t_gw1_ns=t_gw1_ns)
                try:
                    logger.info(
                        "apex_gateway forward path=%s deltas_ms=%s",
                        subpath,
                        (body.get("apex_trace") or {}).get("deltas_ms"),
                    )
                except Exception:
                    pass
            return body
    except urllib.error.HTTPError as e:
        observe_live_broker_forward(
            result="http_error", elapsed_sec=time.perf_counter() - t0
        )
        raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
        try:
            parsed: Any = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"detail": raw[:4000]}
        raise LiveBrokerForwardHttpError(int(e.code), parsed) from e
    except urllib.error.URLError as e:
        observe_live_broker_forward(
            result="url_error", elapsed_sec=time.perf_counter() - t0
        )
        logger.warning("live-broker forward failed: %s", e)
        raise RuntimeError(str(e.reason or e)) from e
