from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

import httpx
from shared_py.bitget import BitgetSettings
from shared_py.observability.provider_log import provider_log_extra

from market_stream.normalization.models import NormalizedEvent
from market_stream.sinks.postgres_raw import PostgresRawSink
from market_stream.sinks.redis_stream import RedisStreamSink

if TYPE_CHECKING:
    from market_stream.provider_diagnostics import ProviderDiagnostics

OnGapfillComplete = Callable[[str], Awaitable[None]]


class BitgetRestGapFillWorker:
    def __init__(
        self,
        *,
        bitget_settings: BitgetSettings,
        redis_sink: RedisStreamSink,
        postgres_sink: PostgresRawSink,
        logger: logging.Logger | None = None,
        timeout_sec: float = 10.0,
        on_complete: OnGapfillComplete | None = None,
        provider_diagnostics: ProviderDiagnostics | None = None,
        max_429_retries: int = 3,
    ) -> None:
        self._bitget_settings = bitget_settings
        self._redis_sink = redis_sink
        self._postgres_sink = postgres_sink
        self._logger = logger or logging.getLogger("market_stream.gapfill")
        self._timeout_sec = timeout_sec
        self._on_complete = on_complete
        self._provider_diagnostics = provider_diagnostics
        self._max_429_retries = max(0, max_429_retries)
        self._last_gapfill_reason: str | None = None
        self._last_gapfill_ok_ts_ms: int | None = None
        self._last_gapfill_error: str | None = None

    async def on_reconnect(self) -> None:
        await self._run_gapfill(reason="reconnect")

    async def on_gap_detected(self, reason: str) -> None:
        await self._run_gapfill(reason=reason)

    async def maybe_gapfill_if_stale(
        self,
        last_event_ts_ms: int | None,
        stale_after_sec: int,
    ) -> bool:
        if last_event_ts_ms is None:
            return False
        now_ms = int(time.time() * 1000)
        if now_ms - last_event_ts_ms < stale_after_sec * 1000:
            return False
        await self._run_gapfill(reason="stale-data")
        return True

    async def gapfill_candles(
        self,
        *,
        granularity: str = "1m",
        limit: int = 50,
    ) -> list[NormalizedEvent]:
        response_payload = await self._request_json(
            path=self._bitget_settings.endpoint_profile.public_candles_path,
            params=self._market_params(
                granularity=self._bitget_settings.candle_granularity(granularity),
                limit=str(limit),
            ),
        )
        event = NormalizedEvent.from_gapfill_payload(
            inst_type=self._bitget_settings.public_ws_inst_type,
            channel=f"candles:{granularity}",
            inst_id=self._bitget_settings.symbol,
            action="snapshot",
            payload=response_payload,
        )
        await self._publish(event)
        return [event]

    @property
    def last_gapfill_reason(self) -> str | None:
        return self._last_gapfill_reason

    @property
    def last_gapfill_ok_ts_ms(self) -> int | None:
        return self._last_gapfill_ok_ts_ms

    @property
    def last_gapfill_error(self) -> str | None:
        return self._last_gapfill_error

    async def gapfill_merge_depth(self, *, limit: str = "100") -> list[NormalizedEvent]:
        """REST-Orderbuch-Snapshot fuer Replay/Microstructure (Bitget merge-depth)."""
        endpoint = self._bitget_settings.endpoint_profile.public_depth_path
        if not endpoint:
            return []
        response_payload = await self._request_json(
            path=endpoint,
            params=self._market_params(limit=limit),
        )
        event = NormalizedEvent.from_gapfill_payload(
            inst_type=self._bitget_settings.public_ws_inst_type,
            channel="merge-depth",
            inst_id=self._bitget_settings.symbol,
            action="snapshot",
            payload=response_payload,
        )
        await self._publish(event)
        return [event]

    async def gapfill_ticker(self) -> list[NormalizedEvent]:
        """REST-Ticker (Public) als Fallback-Spiegel neben WS-ticker."""
        response_payload = await self._request_json(
            path=self._bitget_settings.endpoint_profile.public_ticker_path,
            params=self._market_params(),
        )
        event = NormalizedEvent.from_gapfill_payload(
            inst_type=self._bitget_settings.public_ws_inst_type,
            channel="ticker-rest",
            inst_id=self._bitget_settings.symbol,
            action="snapshot",
            payload=response_payload,
        )
        await self._publish(event)
        return [event]

    async def gapfill_trades(self, *, minutes: int = 5) -> list[NormalizedEvent]:
        now_ms = int(time.time() * 1000)
        max_window_ms = 7 * 24 * 60 * 60 * 1000
        requested_window_ms = minutes * 60 * 1000
        window_ms = min(requested_window_ms, max_window_ms)
        params = self._market_params(limit="200")
        if self._bitget_settings.market_family == "futures":
            params["startTime"] = str(now_ms - window_ms)
            params["endTime"] = str(now_ms)
        response_payload = await self._request_json(
            path=self._bitget_settings.endpoint_profile.public_trades_path,
            params=params,
        )
        event = NormalizedEvent.from_gapfill_payload(
            inst_type=self._bitget_settings.public_ws_inst_type,
            channel="fills-history",
            inst_id=self._bitget_settings.symbol,
            action="snapshot",
            payload=response_payload,
        )
        await self._publish(event)
        return [event]

    async def _run_gapfill(self, *, reason: str) -> None:
        self._last_gapfill_reason = reason
        self._logger.info("starting REST gap-fill reason=%s", reason)
        try:
            await self.gapfill_candles()
            await self.gapfill_trades()
            try:
                await self.gapfill_ticker()
            except Exception as exc:
                self._logger.warning(
                    "REST gap-fill ticker optional failed reason=%s error=%s",
                    reason,
                    exc,
                )
            try:
                await self.gapfill_merge_depth()
            except Exception as exc:
                self._logger.warning(
                    "REST gap-fill merge-depth optional failed reason=%s error=%s",
                    reason,
                    exc,
                )
            self._last_gapfill_ok_ts_ms = int(time.time() * 1000)
            self._last_gapfill_error = None
        except ValueError as exc:
            self._last_gapfill_error = str(exc)
            self._logger.warning("REST gap-fill failed reason=%s error=%s", reason, exc)
            if self._provider_diagnostics is not None:
                self._provider_diagnostics.record_protocol_error("rest_gapfill", str(exc))
            return
        except Exception as exc:
            self._last_gapfill_error = str(exc)
            self._logger.warning("REST gap-fill failed reason=%s error=%s", reason, exc)
            if self._provider_diagnostics is not None:
                self._provider_diagnostics.record_transport_error(
                    f"rest_gapfill reason={reason} err={type(exc).__name__}: {exc}"
                )
            return
        if self._on_complete is not None:
            try:
                await self._on_complete(reason)
            except Exception as exc:
                self._logger.warning("gap-fill on_complete hook failed: %s", exc)
        self._logger.info("REST gap-fill finished reason=%s", reason)

    async def _request_json(
        self,
        *,
        path: str,
        params: dict[str, str],
    ) -> dict[str, Any]:
        base_url = self._bitget_settings.effective_rest_base_url
        headers = {"Accept": "application/json"}
        mode = "demo" if self._bitget_settings.bitget_demo_enabled else "live"
        max_attempts = 1 + self._max_429_retries
        async with httpx.AsyncClient(timeout=self._timeout_sec) as client:
            payload: dict[str, Any] | None = None
            for attempt in range(max_attempts):
                response = await client.get(
                    f"{base_url}{path}",
                    params=params,
                    headers=headers,
                )
                if response.status_code == 429 and attempt < max_attempts - 1:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after and retry_after.strip().isdigit():
                        wait = min(float(retry_after.strip()), 30.0)
                    else:
                        wait = min(0.5 * (2**attempt), 30.0)
                    self._logger.warning(
                        "Bitget REST 429 path=%s attempt=%s/%s wait_s=%.2f",
                        path,
                        attempt + 1,
                        max_attempts,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    code = exc.response.status_code
                    extra = provider_log_extra(
                        provider="bitget",
                        event="rest_public_rate_limited"
                        if code == 429
                        else "rest_public_http_error",
                        http_status=code,
                        exchange_mode=mode,
                        symbol=self._bitget_settings.symbol,
                    )
                    self._logger.warning(
                        "Bitget REST gap-fill HTTP %s path=%s",
                        code,
                        path,
                        extra=extra,
                    )
                    if self._provider_diagnostics is not None:
                        self._provider_diagnostics.record_protocol_error(
                            "rest_gapfill_http",
                            f"HTTP {code} path={path}",
                        )
                    raise
                raw = response.json()
                if not isinstance(raw, dict):
                    raise ValueError("Bitget REST response muss ein JSON-Objekt sein")
                response_code = raw.get("code")
                if response_code not in (None, "00000"):
                    msg = raw.get("msg") or raw.get("message") or ""
                    detail = f"code={response_code!r} msg={str(msg).strip()[:400]!r} path={path}"
                    if self._provider_diagnostics is not None:
                        self._provider_diagnostics.record_protocol_error("rest_gapfill_api", detail)
                    raise ValueError(f"Bitget REST response code not ok: {response_code}")
                payload = raw
                break
        if payload is None:
            raise RuntimeError("Bitget REST gap-fill: keine verwertbare Antwort")
        return payload

    def _market_params(self, **extra: str) -> dict[str, str]:
        params = {
            "symbol": self._bitget_settings.symbol,
            **extra,
        }
        if self._bitget_settings.rest_product_type_param:
            params["productType"] = self._bitget_settings.rest_product_type_param
        return params

    async def _publish(self, event: NormalizedEvent) -> None:
        await self._redis_sink.publish(event)
        await self._postgres_sink.insert(event)
