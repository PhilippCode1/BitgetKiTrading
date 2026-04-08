from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import websockets
from websockets.exceptions import ConnectionClosed

from shared_py.bitget.config import BitgetSettings
from shared_py.bitget.http import build_signature_payload, sign_hmac_sha256_base64
from live_broker.private_ws.models import NormalizedPrivateEvent

MessageHandler = Callable[[NormalizedPrivateEvent], Awaitable[None]]
ConnectedCallback = Callable[[bool], Awaitable[None]]
StaleRecoverCallback = Callable[[], None]


@dataclass(slots=True)
class PrivateWsClientStats:
    connection_state: str = "stopped"
    active_subscriptions: int = 0
    last_event_ts_ms: int | None = None
    last_exchange_ts_ms: int | None = None
    last_ingest_latency_ms: int | None = None
    last_ping_ts_ms: int | None = None
    last_pong_ts_ms: int | None = None
    received_events: int = 0
    reconnect_count: int = 0
    ping_count: int = 0
    pong_count: int = 0
    stale_escalation_count: int = 0
    gap_recovery_triggers: int = 0
    last_stale_catchup_ts_ms: int | None = None
    channel_coverage: tuple[str, ...] = ()
    ws_endpoint_host: str | None = None
    last_error: str | None = None


class BitgetPrivateWsClient:
    def __init__(
        self,
        *,
        bitget_settings: BitgetSettings,
        stats: PrivateWsClientStats,
        logger: logging.Logger | None = None,
        ping_interval_sec: float = 30.0,
        pong_timeout_sec: float = 65.0,
        reconnect_initial_delay_sec: float = 1.0,
        reconnect_max_delay_sec: float = 30.0,
        message_handlers: list[MessageHandler] | None = None,
        connected_callbacks: list[ConnectedCallback] | None = None,
        on_stale_recover: StaleRecoverCallback | None = None,
    ) -> None:
        self._settings = bitget_settings
        self._stats = stats
        self._logger = logger or logging.getLogger("live_broker.private_ws")
        self._ping_interval_sec = ping_interval_sec
        self._pong_timeout_sec = pong_timeout_sec
        self._reconnect_initial_delay_sec = reconnect_initial_delay_sec
        self._reconnect_max_delay_sec = reconnect_max_delay_sec
        self._on_stale_recover = on_stale_recover
        self._stale_after_sec = int(
            getattr(bitget_settings, "live_broker_private_ws_stale_after_sec", 90)
        )
        self._stale_max_cycles = int(
            getattr(
                bitget_settings,
                "live_broker_private_ws_stale_escalation_max_cycles",
                10,
            )
        )
        self._last_stale_recover_ts_ms: int | None = None
        self._stop_event = asyncio.Event()
        self._send_lock = asyncio.Lock()
        self._websocket: Any | None = None
        self._last_pong_monotonic = time.monotonic()
        self._last_inbound_monotonic = time.monotonic()
        self._ever_connected = False
        self._message_handlers = message_handlers or []
        self._connected_callbacks = connected_callbacks or []
        inst = self._settings.product_type
        self._channels = [
            {"instType": inst, "channel": "orders", "instId": "default"},
            {"instType": inst, "channel": "positions", "instId": "default"},
            {"instType": inst, "channel": "fill", "instId": "default"},
            # Bitget Account-Channel: nur coin=default (Doku); kein marginCoin-String.
            {"instType": inst, "channel": "account", "coin": "default"},
        ]

    async def run(self) -> None:
        backoff = self._reconnect_initial_delay_sec
        while not self._stop_event.is_set():
            try:
                await self._run_once()
                backoff = self._reconnect_initial_delay_sec
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._stats.last_error = str(exc)
                self._stats.connection_state = "reconnecting"
                self._stats.reconnect_count += 1
                self._logger.warning(
                    "Private WS reconnect in %.1fs due to error: %s",
                    backoff,
                    exc,
                )
                if self._stop_event.is_set():
                    break
                await asyncio.sleep(backoff)
                backoff = min(self._reconnect_max_delay_sec, backoff * 2)
        self._stats.connection_state = "stopped"

    async def stop(self) -> None:
        self._stop_event.set()
        if self._websocket is not None:
            await self._websocket.close()

    async def _run_once(self) -> None:
        self._stats.connection_state = "connecting"
        ws_url = self._settings.effective_ws_private_url
        if not ws_url:
            ws_url = "wss://ws.bitget.com/v2/ws/private"
        try:
            parsed = urlparse(str(ws_url))
            self._stats.ws_endpoint_host = parsed.hostname
        except Exception:
            self._stats.ws_endpoint_host = None

        async with websockets.connect(
            ws_url,
            ping_interval=None,
            ping_timeout=None,
            close_timeout=5,
            max_queue=1000,
        ) as websocket:
            self._websocket = websocket
            self._last_pong_monotonic = time.monotonic()
            self._last_inbound_monotonic = time.monotonic()
            
            await self._login()
            
            self._stats.connection_state = "connected"
            self._stats.last_error = None
            self._stats.stale_escalation_count = 0
            self._logger.info("Private WS connected and authenticated")
            
            await self._subscribe_channels()
            
            is_reconnect = self._ever_connected
            for callback in self._connected_callbacks:
                try:
                    await callback(is_reconnect)
                except Exception as exc:
                    self._logger.warning("connected callback failed: %s", exc)
            self._ever_connected = True

            tasks = [
                asyncio.create_task(self._receive_loop(), name="private-ws-recv"),
                asyncio.create_task(self._ping_loop(), name="private-ws-ping"),
                asyncio.create_task(self._pong_watcher(), name="private-ws-pong"),
                asyncio.create_task(self._stale_data_loop(), name="private-ws-stale"),
            ]
            try:
                done, _pending = await asyncio.wait(
                    tasks,
                    return_when=asyncio.FIRST_EXCEPTION,
                )
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                self._websocket = None

            for task in done:
                exception = task.exception()
                if exception is not None:
                    raise exception
            if not self._stop_event.is_set():
                raise RuntimeError("websocket loop ended without exception")

    async def _login(self) -> None:
        if not self._settings.effective_api_key or not self._settings.effective_api_secret:
            raise ValueError("API Key/Secret missing for Private WS")

        ts = str(int(time.time() * 1000))
        payload = build_signature_payload(
            timestamp_ms=int(ts),
            method="GET",
            request_path="/user/verify",
        )
        signature = sign_hmac_sha256_base64(self._settings.effective_api_secret, payload)
        
        login_msg = {
            "op": "login",
            "args": [
                {
                    "apiKey": self._settings.effective_api_key,
                    "passphrase": self._settings.effective_api_passphrase,
                    "timestamp": ts,
                    "sign": signature,
                }
            ],
        }
        await self._send_json(login_msg)
        
        # Wait for login response
        if self._websocket is None:
            raise RuntimeError("WebSocket not connected")
            
        try:
            # We expect a response to our login immediately
            response = await asyncio.wait_for(self._websocket.recv(), timeout=10.0)
            self._last_inbound_monotonic = time.monotonic()
            resp_data = json.loads(response)
            if resp_data.get("event") == "error":
                raise ValueError(f"WS Login failed: {resp_data}")
            if resp_data.get("event") == "login":
                code = resp_data.get("code", "0")
                sc = str(code) if code is not None else "0"
                if sc not in ("0", "00000", ""):
                    raise ValueError(f"WS login rejected code={code} body={resp_data}")
                self._logger.info("Private WS login successful")
        except asyncio.TimeoutError:
            raise TimeoutError("Timeout waiting for WS login response")

    async def _subscribe_channels(self) -> None:
        sub_msg = {
            "op": "subscribe",
            "args": self._channels,
        }
        await self._send_json(sub_msg)
        self._stats.active_subscriptions = len(self._channels)
        labels: list[str] = []
        for ch in self._channels:
            ident = str(ch.get("instId") or ch.get("coin") or "default")
            labels.append(f"{ch.get('channel')}:{ident}")
        self._stats.channel_coverage = tuple(labels)

    async def _receive_loop(self) -> None:
        if self._websocket is None:
            return
        async for raw_message in self._websocket:
            self._last_inbound_monotonic = time.monotonic()
            text_message = (
                raw_message.decode("utf-8")
                if isinstance(raw_message, bytes)
                else raw_message
            )
            if text_message == "pong":
                self._mark_pong()
                continue

            try:
                decoded = json.loads(text_message)
            except json.JSONDecodeError:
                self._logger.warning("ignoring non-JSON WS frame: %s", text_message)
                continue
                
            if not isinstance(decoded, dict):
                continue
                
            if decoded.get("event") == "pong":
                self._mark_pong()
                continue
                
            if decoded.get("event") in ("subscribe", "login"):
                continue
                
            if decoded.get("event") == "error":
                self._logger.warning("Bitget WS error event: %s", decoded)
                continue

            if "data" in decoded and "arg" in decoded:
                event = NormalizedPrivateEvent.from_ws_message(decoded)
                self._stats.last_event_ts_ms = event.ingest_ts_ms
                self._stats.last_exchange_ts_ms = event.exchange_ts_ms
                canon = event.to_canonical()
                lat = canon.approx_latency_ms()
                if lat is not None:
                    self._stats.last_ingest_latency_ms = lat
                self._stats.stale_escalation_count = 0
                if event.event_type == "unknown":
                    continue
                self._stats.received_events += 1
                for handler in self._message_handlers:
                    try:
                        await handler(event)
                    except Exception as exc:
                        self._logger.warning("message handler failed: %s", exc)

    async def _stale_data_loop(self) -> None:
        while not self._stop_event.is_set():
            await asyncio.sleep(5)
            if self._stats.connection_state != "connected":
                continue
            last_ev = self._stats.last_event_ts_ms
            if last_ev is None:
                continue
            now_ms = int(time.time() * 1000)
            stale_ms = now_ms - last_ev
            if stale_ms < self._stale_after_sec * 1000:
                continue
            self._stats.stale_escalation_count += 1
            self._logger.warning(
                "private ws data stale age_ms=%s escalation=%s",
                stale_ms,
                self._stats.stale_escalation_count,
            )
            if self._stats.stale_escalation_count >= self._stale_max_cycles:
                raise RuntimeError("private ws stale escalation — reconnect")
            if self._on_stale_recover is None:
                continue
            min_gap_ms = self._stale_after_sec * 1000
            if (
                self._last_stale_recover_ts_ms is not None
                and now_ms - self._last_stale_recover_ts_ms < min_gap_ms
            ):
                continue
            try:
                self._on_stale_recover()
                self._last_stale_recover_ts_ms = now_ms
                self._stats.gap_recovery_triggers += 1
                self._stats.last_stale_catchup_ts_ms = now_ms
            except Exception as exc:
                self._logger.warning(
                    "private ws stale recover callback failed: %s",
                    exc,
                )

    async def _ping_loop(self) -> None:
        while not self._stop_event.is_set():
            await asyncio.sleep(self._ping_interval_sec)
            try:
                await self._send_text("ping")
                self._stats.ping_count += 1
                self._stats.last_ping_ts_ms = int(time.time() * 1000)
            except ConnectionClosed:
                break
            except Exception as exc:
                self._logger.warning("Failed to send ping: %s", exc)

    async def _pong_watcher(self) -> None:
        while not self._stop_event.is_set():
            await asyncio.sleep(5)
            last_heartbeat = max(
                self._last_pong_monotonic,
                self._last_inbound_monotonic,
            )
            if time.monotonic() - last_heartbeat > self._pong_timeout_sec:
                raise TimeoutError("WS pong timeout")

    async def _send_json(self, payload: dict[str, object]) -> None:
        if self._websocket is None:
            raise RuntimeError("WebSocket not connected")
        async with self._send_lock:
            await self._websocket.send(json.dumps(payload, separators=(",", ":")))

    async def _send_text(self, payload: str) -> None:
        if self._websocket is None:
            raise RuntimeError("WebSocket not connected")
        async with self._send_lock:
            await self._websocket.send(payload)

    def _mark_pong(self) -> None:
        self._last_pong_monotonic = time.monotonic()
        self._stats.pong_count += 1
        self._stats.last_pong_ts_ms = int(time.time() * 1000)
