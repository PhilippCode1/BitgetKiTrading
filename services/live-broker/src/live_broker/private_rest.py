from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx

from shared_py.bitget import (
    build_private_rest_headers,
    build_query_string,
    canonical_json_body,
)
from live_broker.bitget_exchange_handling import ExchangeHandling, exchange_handling_for_classification
from shared_py.bitget.errors import (
    BitgetErrorClassification,
    classify_bitget_private_rest_failure,
)
from shared_py.resilience import (
    CircuitBreaker,
    compute_backoff_delay,
)

if TYPE_CHECKING:
    from live_broker.config import LiveBrokerSettings

logger = logging.getLogger("live_broker.private_rest")

_SECRET_KEY_SUBSTR = ("secret", "passphrase", "password", "apikey", "api_key", "sign", "token")


def _scrub_secrets_from_mapping(obj: Any, depth: int = 0) -> Any:
    if depth > 8:
        return "[TRUNCATED]"
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            lk = str(k).lower()
            if any(s in lk for s in _SECRET_KEY_SUBSTR):
                out[str(k)] = "[REDACTED]"
            else:
                out[str(k)] = _scrub_secrets_from_mapping(v, depth + 1)
        return out
    if isinstance(obj, list):
        return [_scrub_secrets_from_mapping(x, depth + 1) for x in obj[:100]]
    return obj


class BitgetRestError(RuntimeError):
    def __init__(
        self,
        *,
        classification: BitgetErrorClassification,
        message: str,
        retryable: bool,
        http_status: int | None = None,
        exchange_code: str | None = None,
        exchange_msg: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.classification = classification
        self.retryable = retryable
        self.http_status = http_status
        self.exchange_code = exchange_code
        self.exchange_msg = exchange_msg
        self.payload = payload or {}

    def exchange_handling(self) -> ExchangeHandling:
        return exchange_handling_for_classification(self.classification)

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "exchange_handling": self.exchange_handling(),
            "retryable": self.retryable,
            "http_status": self.http_status,
            "exchange_code": self.exchange_code,
            "exchange_msg": self.exchange_msg,
            "message": str(self),
            "payload": _scrub_secrets_from_mapping(self.payload),
        }


def _probe_bitget_error_de(exc: BitgetRestError, *, demo: bool) -> str:
    """Kurztext fuer Operator/Console — keine Secrets, keine rohen Signaturen."""
    mode = "Demo (BITGET_DEMO_* + BITGET_DEMO_REST_BASE_URL)" if demo else "Live (BITGET_API_* + BITGET_API_BASE_URL)"
    code = (exc.exchange_code or "").strip()
    msg = (exc.exchange_msg or str(exc) or "").strip()
    if exc.classification in ("auth", "permission"):
        return (
            f"Bitget hat die Anmeldung abgelehnt ({mode}). "
            "Haeufig: falsches Secret, falsche Passphrase, oder Live-Keys gegen Demo-Endpoint (oder umgekehrt). "
            f"Boerse code={code or '—'}: {msg[:180]}"
        )
    if exc.classification == "timestamp":
        return (
            "Zeitstempel/Signatur abgewiesen — lokale Uhr oder Server-Time-Sync pruefen "
            f"(code={code or '—'})."
        )
    if exc.classification == "clock_skew":
        return msg[:220] if msg else "Zeitabweichnung zur Boerse zu gross — NTP/Sync pruefen."
    if exc.classification == "rate_limit":
        return "Bitget Rate-Limit — kurz warten und erneut versuchen."
    if exc.classification == "transport":
        return f"Netzwerk/Transport zur Bitget-API fehlgeschlagen: {msg[:180]}"
    if exc.classification == "server":
        return f"Bitget-Serverfehler (voruebergehend): {msg[:180]}"
    return f"Bitget private ({mode}): {msg[:220] if msg else exc.classification}"


def _should_retry_private_http(exc: BitgetRestError, *, attempt: int, max_retries: int) -> bool:
    """Kein Retry-Spam: nur wo retryable und keine Security/Config-Hardstops."""
    if attempt >= max_retries:
        return False
    if not exc.retryable:
        return False
    if exc.classification in (
        "auth",
        "permission",
        "clock_skew",
        "operator_intervention",
        "validation",
        "duplicate",
        "service_disabled",
        "kill_switch",
        "not_found",
        "conflict",
    ):
        return False
    return True


@dataclass(frozen=True)
class BitgetRestResponse:
    http_status: int
    payload: dict[str, Any]
    request_path: str
    method: str
    query_string: str
    body: str
    attempts: int


class BitgetPrivateRestClient:
    def __init__(
        self,
        settings: "LiveBrokerSettings",
        *,
        transport: httpx.BaseTransport | None = None,
        sleep_fn=time.sleep,
        monotonic_fn=time.monotonic,
        now_ms_fn=None,
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._sleep = sleep_fn
        self._monotonic = monotonic_fn
        self._now_ms = now_ms_fn or (lambda: int(time.time() * 1000))
        self._circuit = CircuitBreaker(
            fail_threshold=settings.live_broker_circuit_fail_threshold,
            open_seconds=settings.live_broker_circuit_open_sec,
        )
        self._server_time_offset_ms = 0
        self._last_server_sync_mono: float | None = None
        self._last_server_rtt_ms: int | None = None

    def state_snapshot(self) -> dict[str, Any]:
        sync_age_sec = None
        if self._last_server_sync_mono is not None:
            sync_age_sec = round(self._monotonic() - self._last_server_sync_mono, 3)
        offset_within_budget = (
            abs(self._server_time_offset_ms)
            <= self._settings.live_broker_server_time_max_skew_ms
        )
        return {
            "server_time_offset_ms": self._server_time_offset_ms,
            "offset_within_budget": offset_within_budget,
            "last_server_rtt_ms": self._last_server_rtt_ms,
            "last_server_sync_age_sec": sync_age_sec,
            "circuit": self._circuit.state_snapshot(),
        }

    def sync_server_time(self, *, force: bool = False) -> dict[str, Any]:
        if not force and self._last_server_sync_mono is not None:
            age = self._monotonic() - self._last_server_sync_mono
            if age < self._settings.live_broker_server_time_sync_sec:
                return self.state_snapshot()
        path = "/api/v2/public/time"
        start_ms = int(self._now_ms())
        try:
            with self._build_client() as client:
                response = client.get(f"{self._settings.effective_rest_base_url}{path}")
        except httpx.HTTPError as exc:
            raise BitgetRestError(
                classification="transport",
                message=f"Bitget server time request failed: {exc}",
                retryable=True,
            ) from exc
        end_ms = int(self._now_ms())
        payload = self._decode_json(response)
        if response.status_code >= 400 or str(payload.get("code") or "") != "00000":
            raise self._map_error(
                http_status=response.status_code,
                payload=payload,
                fallback_message="Bitget server time sync failed",
            )
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict) or "serverTime" not in data:
            raise BitgetRestError(
                classification="unknown",
                message="Bitget server time response missing data.serverTime",
                retryable=False,
                http_status=response.status_code,
                payload=payload,
            )
        server_time_ms = int(str(data["serverTime"]))
        midpoint_ms = start_ms + ((end_ms - start_ms) // 2)
        self._server_time_offset_ms = server_time_ms - midpoint_ms
        self._last_server_rtt_ms = end_ms - start_ms
        self._last_server_sync_mono = self._monotonic()
        if (
            abs(self._server_time_offset_ms)
            > self._settings.live_broker_server_time_max_skew_ms
        ):
            logger.warning(
                "bitget server time skew exceeds budget offset_ms=%s budget_ms=%s",
                self._server_time_offset_ms,
                self._settings.live_broker_server_time_max_skew_ms,
            )
        return self.state_snapshot()

    def _reject_if_clock_skew_too_large(self) -> None:
        """Hard gate: keine privaten Trading-Requests bei Zeitdrift (ohne Blind-Retry an der Boerse)."""
        budget = int(self._settings.live_broker_server_time_max_skew_ms)
        off = abs(int(self._server_time_offset_ms))
        if off > budget:
            raise BitgetRestError(
                classification="clock_skew",
                message=(
                    f"Zeitabweichnung zur Boerse zu gross ({off}ms > {budget}ms) — "
                    "Sync/ NTP pruefen, keine Order senden"
                ),
                retryable=False,
                payload={"offset_ms": self._server_time_offset_ms, "budget_ms": budget},
            )

    def probe_private_access(self) -> dict[str, Any]:
        """
        Read-only: synchronisiert Serverzeit und ruft ein Konto-/Asset-Read auf.
        Unterscheidet fehlende Keys, falsche Signatur/Passphrase und Transport — ohne Order.
        """
        demo = bool(self._settings.bitget_demo_enabled)
        base: dict[str, Any] = {
            "private_auth_ok": False,
            "private_auth_detail": "",
            "private_auth_detail_de": "",
            "private_auth_classification": None,
            "private_auth_exchange_code": None,
            "bitget_demo_mode": demo,
        }
        if (
            not self._settings.effective_api_key
            or not self._settings.effective_api_secret
            or not self._settings.effective_api_passphrase
        ):
            scope = "Demo (BITGET_DEMO_*)" if demo else "Live (BITGET_API_*)"
            msg = (
                f"API-Key, Secret oder Passphrase fehlt fuer {scope}. "
                "Ohne vollstaendiges Tripel ist keine private Bitget-Anbindung moeglich."
            )
            return {
                **base,
                "private_auth_detail": "missing_credentials",
                "private_auth_detail_de": msg,
            }
        path = str(
            getattr(self._settings.endpoint_profile, "private_account_assets_path", "") or ""
        ).strip()
        if not path:
            return {
                **base,
                "private_auth_detail": "no_private_account_path",
                "private_auth_detail_de": (
                    "Fuer diese market_family gibt es keinen konfigurierten Konto-Read-Pfad — "
                    "Endpoint-Profil pruefen (BITGET_MARKET_FAMILY / Produkttyp)."
                ),
            }
        fam = (self._settings.market_family or "").strip().lower()
        params: dict[str, Any] = {}
        if fam == "futures":
            pt = self._settings.rest_product_type_param
            if pt:
                params["productType"] = pt
            params["marginCoin"] = self._settings.effective_margin_coin
            # Bitget GET /api/v2/mix/account/account verlangt symbol (Doku: Required).
            sym = (self._settings.symbol or "").strip().lower()
            if sym:
                params["symbol"] = sym
            elif "/mix/account/account" in path:
                return {
                    **base,
                    "private_auth_detail": "missing_symbol_for_futures_account_probe",
                    "private_auth_detail_de": (
                        "Futures-Konto-Read (/api/v2/mix/account/account) verlangt laut Bitget-Doku "
                        "ein symbol-Query — BITGET_SYMBOL setzen."
                    ),
                }
        elif fam == "spot":
            if self._settings.effective_margin_coin:
                params["coin"] = self._settings.effective_margin_coin
        elif fam == "margin":
            if self._settings.margin_account_mode == "isolated":
                params["symbol"] = self._settings.symbol
            elif self._settings.effective_margin_coin:
                params["coin"] = self._settings.effective_margin_coin
        try:
            self.sync_server_time(force=False)
        except BitgetRestError as exc:
            return {
                **base,
                "private_auth_detail": str(exc),
                "private_auth_detail_de": _probe_bitget_error_de(exc, demo=demo),
                "private_auth_classification": exc.classification,
                "private_auth_exchange_code": exc.exchange_code,
            }
        try:
            self._private_request(
                "GET",
                path,
                params=params,
                operation="probe_credentials",
                priority=True,
            )
        except BitgetRestError as exc:
            return {
                **base,
                "private_auth_detail": exc.exchange_msg or str(exc),
                "private_auth_detail_de": _probe_bitget_error_de(exc, demo=demo),
                "private_auth_classification": exc.classification,
                "private_auth_exchange_code": exc.exchange_code,
            }
        return {
            **base,
            "private_auth_ok": True,
            "private_auth_detail": "ok",
            "private_auth_detail_de": (
                "Private Bitget-API: Authentifizierung und Konto-Read erfolgreich "
                f"({'Demo/Paper' if demo else 'Live'}-Keys, REST-Basis wie konfiguriert)."
            ),
        }

    def place_order(
        self,
        body: dict[str, Any],
        *,
        priority: bool = False,
        request_path: str | None = None,
    ) -> BitgetRestResponse:
        path = (request_path or "").strip() or self._require_endpoint_path(
            "private_place_order_path",
            "place_order",
        )
        return self._private_request(
            "POST",
            path,
            body=body,
            operation="place_order",
            priority=priority,
        )

    def cancel_order(
        self,
        body: dict[str, Any],
        *,
        priority: bool = False,
        request_path: str | None = None,
    ) -> BitgetRestResponse:
        path = (request_path or "").strip() or self._require_endpoint_path(
            "private_cancel_order_path",
            "cancel_order",
        )
        return self._private_request(
            "POST",
            path,
            body=body,
            operation="cancel_order",
            priority=priority,
        )

    def cancel_all_orders(
        self,
        body: dict[str, Any],
        *,
        priority: bool = False,
        request_path: str | None = None,
    ) -> BitgetRestResponse:
        path = (request_path or "").strip() or self._require_endpoint_path(
            "private_cancel_all_orders_path",
            "cancel_all_orders",
        )
        return self._private_request(
            "POST",
            path,
            body=body,
            operation="cancel_all_orders",
            priority=priority,
        )

    def modify_order(
        self,
        body: dict[str, Any],
        *,
        priority: bool = False,
        request_path: str | None = None,
    ) -> BitgetRestResponse:
        path = (request_path or "").strip() or self._require_endpoint_path(
            "private_modify_order_path",
            "modify_order",
        )
        return self._private_request(
            "POST",
            path,
            body=body,
            operation="modify_order",
            priority=priority,
        )

    def get_order_detail(
        self,
        *,
        params: dict[str, Any],
        priority: bool = False,
        request_path: str | None = None,
        market_family: str | None = None,
    ) -> BitgetRestResponse:
        fam = (market_family or self._settings.market_family or "").strip().lower()
        query_params = dict(params)
        req_path = (request_path or "").strip()
        if not req_path:
            req_path = str(
                self._settings.endpoint_profile.private_order_detail_path or ""
            ).strip()
        if not req_path:
            req_path = self._require_endpoint_path(
                "private_open_orders_path",
                "get_order_detail",
            )
        if fam == "margin":
            now_ms = int(self._now_ms())
            query_params.setdefault(
                "startTime",
                str(now_ms - 90 * 24 * 60 * 60 * 1000),
            )
            query_params.setdefault("endTime", str(now_ms))
            query_params.setdefault("limit", "1")
        return self._private_request(
            "GET",
            req_path,
            params=query_params,
            operation="get_order_detail",
            priority=priority,
        )

    def list_orders_pending(
        self,
        *,
        symbol: str | None = None,
        priority: bool = True,
    ) -> BitgetRestResponse:
        """REST-Snapshot: offene Auftraege (Catch-up / Reconcile)."""
        request_path = self._require_endpoint_path(
            "private_open_orders_path",
            "orders_pending",
        )
        params: dict[str, Any] = {}
        if self._settings.rest_product_type_param:
            params["productType"] = self._settings.rest_product_type_param
        if symbol:
            params["symbol"] = symbol
        elif self._settings.market_family == "margin":
            params["symbol"] = self._settings.symbol
        if self._settings.market_family == "margin":
            now_ms = int(self._now_ms())
            params.setdefault(
                "startTime",
                str(now_ms - 90 * 24 * 60 * 60 * 1000),
            )
            params.setdefault("endTime", str(now_ms))
            params.setdefault("limit", "100")
        return self._private_request(
            "GET",
            request_path,
            params=params,
            operation="orders_pending",
            priority=priority,
        )

    def list_orders_history(
        self,
        *,
        params: dict[str, Any],
        priority: bool = True,
        request_path: str | None = None,
        market_family: str | None = None,
    ) -> BitgetRestResponse:
        fam = (market_family or self._settings.market_family or "").strip().lower()
        req_path = (request_path or "").strip() or self._require_endpoint_path(
            "private_order_history_path",
            "orders_history",
        )
        query_params = dict(params)
        if fam == "futures" and self._settings.rest_product_type_param:
            query_params.setdefault(
                "productType", self._settings.rest_product_type_param
            )
        if fam == "margin":
            now_ms = int(self._now_ms())
            query_params.setdefault(
                "startTime",
                str(now_ms - 90 * 24 * 60 * 60 * 1000),
            )
            query_params.setdefault("endTime", str(now_ms))
            query_params.setdefault("limit", str(query_params.get("limit") or "100"))
        return self._private_request(
            "GET",
            req_path,
            params=query_params,
            operation="orders_history",
            priority=priority,
        )

    def list_fill_history(
        self,
        *,
        params: dict[str, Any],
        priority: bool = True,
        request_path: str | None = None,
        market_family: str | None = None,
    ) -> BitgetRestResponse:
        fam = (market_family or self._settings.market_family or "").strip().lower()
        req_path = (request_path or "").strip() or self._require_endpoint_path(
            "private_fill_history_path",
            "fill_history",
        )
        query_params = dict(params)
        if fam == "futures" and self._settings.rest_product_type_param:
            query_params.setdefault(
                "productType", self._settings.rest_product_type_param
            )
            query_params.setdefault("marginCoin", self._settings.effective_margin_coin)
        if fam == "margin":
            now_ms = int(self._now_ms())
            query_params.setdefault(
                "startTime",
                str(now_ms - 90 * 24 * 60 * 60 * 1000),
            )
            query_params.setdefault("endTime", str(now_ms))
            query_params.setdefault("limit", str(query_params.get("limit") or "100"))
        return self._private_request(
            "GET",
            req_path,
            params=query_params,
            operation="fill_history",
            priority=priority,
        )

    def set_account_leverage(
        self,
        body: dict[str, Any],
        *,
        priority: bool = False,
        request_path: str | None = None,
    ) -> BitgetRestResponse:
        path = (request_path or "").strip() or self._require_endpoint_path(
            "private_set_leverage_path",
            "set_leverage",
        )
        return self._private_request(
            "POST",
            path,
            body=body,
            operation="set_leverage",
            priority=priority,
        )

    def list_all_positions(
        self,
        *,
        priority: bool = True,
    ) -> BitgetRestResponse:
        """REST-Snapshot: alle Positionen."""
        if self._settings.market_family == "futures":
            params: dict[str, Any] = {
                "productType": self._settings.rest_product_type_param
                or str(self._settings.product_type or "").lower().replace("_", "-"),
                "marginCoin": self._settings.effective_margin_coin,
            }
            request_path = self._require_endpoint_path(
                "private_positions_path",
                "all_positions",
            )
        else:
            request_path = self._require_endpoint_path(
                "private_account_assets_path",
                "account_assets",
            )
            params = {}
            if self._settings.market_family == "spot":
                if self._settings.effective_margin_coin:
                    params["coin"] = self._settings.effective_margin_coin
            elif self._settings.market_family == "margin":
                if self._settings.margin_account_mode == "isolated":
                    params["symbol"] = self._settings.symbol
                elif self._settings.effective_margin_coin:
                    params["coin"] = self._settings.effective_margin_coin
        return self._private_request(
            "GET",
            request_path,
            params=params,
            operation="all_positions",
            priority=priority,
        )

    def _require_endpoint_path(self, attr_name: str, operation: str) -> str:
        value = str(getattr(self._settings.endpoint_profile, attr_name, "") or "").strip()
        if value:
            return value
        raise BitgetRestError(
            classification="service_disabled",
            message=(
                f"{operation} wird fuer market_family={self._settings.market_family} "
                "nicht ueber einen gueltigen Endpoint unterstuetzt"
            ),
            retryable=False,
        )

    def _private_request(
        self,
        method: str,
        request_path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        operation: str,
        priority: bool = False,
    ) -> BitgetRestResponse:
        if self._circuit.is_open("bitget-private-rest") and not priority:
            raise BitgetRestError(
                classification="circuit_open",
                message="Bitget private REST circuit is open",
                retryable=True,
            )
        if not self._settings.live_broker_enabled:
            raise BitgetRestError(
                classification="service_disabled",
                message="LIVE_BROKER_ENABLED=false",
                retryable=False,
            )
        if (
            not self._settings.effective_api_key
            or not self._settings.effective_api_secret
            or not self._settings.effective_api_passphrase
        ):
            raise BitgetRestError(
                classification="auth",
                message="Bitget private API credentials missing",
                retryable=False,
            )

        query_string = build_query_string(params)
        body_text = canonical_json_body(body)
        last_error: BitgetRestError | None = None
        max_retries = self._settings.live_broker_http_max_retries

        self.sync_server_time(force=False)
        if not priority:
            self._reject_if_clock_skew_too_large()

        for attempt in range(max_retries + 1):
            try:
                self.sync_server_time(
                    force=attempt > 0
                    and last_error is not None
                    and last_error.classification == "timestamp"
                )
                if not priority:
                    self._reject_if_clock_skew_too_large()
                timestamp_ms = int(self._now_ms()) + int(self._server_time_offset_ms)
                headers = build_private_rest_headers(
                    self._settings,
                    timestamp_ms=timestamp_ms,
                    method=method,
                    request_path=request_path,
                    query_string=query_string,
                    body=body_text,
                )
                url = f"{self._settings.effective_rest_base_url}{request_path}"
                if query_string:
                    url = f"{url}?{query_string}"
                with self._build_client() as client:
                    response = client.request(
                        method.upper(),
                        url,
                        content=body_text or None,
                        headers=headers,
                    )
                payload = self._decode_json(response)
                self._refresh_offset_from_payload(payload)
                if response.status_code >= 400 or str(payload.get("code") or "") != "00000":
                    raise self._map_error(
                        http_status=response.status_code,
                        payload=payload,
                        fallback_message=f"Bitget {operation} failed",
                    )
                self._circuit.record_success("bitget-private-rest")
                logger.info(
                    "bitget private ok operation=%s path=%s attempts=%s",
                    operation,
                    request_path,
                    attempt + 1,
                )
                return BitgetRestResponse(
                    http_status=response.status_code,
                    payload=payload,
                    request_path=request_path,
                    method=method.upper(),
                    query_string=query_string,
                    body=body_text,
                    attempts=attempt + 1,
                )
            except BitgetRestError as exc:
                last_error = exc
                should_trip = exc.classification in (
                    "timestamp",
                    "rate_limit",
                    "transport",
                    "server",
                    "circuit_open",
                )
                if should_trip:
                    self._circuit.record_failure("bitget-private-rest")
                if _should_retry_private_http(exc, attempt=attempt, max_retries=max_retries):
                    delay = compute_backoff_delay(
                        attempt,
                        base_sec=self._settings.live_broker_http_retry_base_sec,
                        max_sec=self._settings.live_broker_http_retry_max_sec,
                    )
                    logger.warning(
                        "bitget retry operation=%s attempt=%s classification=%s handling=%s delay_sec=%.3f",
                        operation,
                        attempt + 1,
                        exc.classification,
                        exc.exchange_handling(),
                        delay,
                    )
                    self._sleep(delay)
                    continue
                raise
            except httpx.HTTPError as exc:
                last_error = BitgetRestError(
                    classification="transport",
                    message=f"Bitget transport error: {exc}",
                    retryable=True,
                )
                self._circuit.record_failure("bitget-private-rest")
                if _should_retry_private_http(last_error, attempt=attempt, max_retries=max_retries):
                    delay = compute_backoff_delay(
                        attempt,
                        base_sec=self._settings.live_broker_http_retry_base_sec,
                        max_sec=self._settings.live_broker_http_retry_max_sec,
                    )
                    self._sleep(delay)
                    continue
                raise last_error from exc
        assert last_error is not None
        raise last_error

    def _map_error(
        self,
        *,
        http_status: int,
        payload: dict[str, Any],
        fallback_message: str,
    ) -> BitgetRestError:
        c = classify_bitget_private_rest_failure(
            http_status=http_status,
            payload=payload,
            fallback_message=fallback_message,
        )
        return BitgetRestError(
            classification=c.classification,
            message=c.diagnostic_message,
            retryable=c.retryable,
            http_status=http_status,
            exchange_code=c.exchange_code,
            exchange_msg=c.exchange_msg,
            payload=payload,
        )

    def _decode_json(self, response: httpx.Response) -> dict[str, Any]:
        if not response.content:
            return {}
        try:
            data = response.json()
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _refresh_offset_from_payload(self, payload: dict[str, Any]) -> None:
        request_time = payload.get("requestTime") if isinstance(payload, dict) else None
        if request_time in (None, ""):
            return
        try:
            server_ms = int(str(request_time))
        except ValueError:
            return
        self._server_time_offset_ms = server_ms - int(self._now_ms())
        self._last_server_sync_mono = self._monotonic()

    def _build_client(self) -> httpx.Client:
        return httpx.Client(
            timeout=self._settings.live_broker_http_timeout_sec,
            transport=self._transport,
        )
