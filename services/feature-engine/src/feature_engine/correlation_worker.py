from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import TYPE_CHECKING, Any, Callable

from shared_py.eventbus import (
    STREAM_INTERMARKET_CORRELATION_UPDATE,
    STREAM_REGIME_DIVERGENCE_DETECTED,
    EventEnvelope,
    make_stream_bus_from_url,
)
from shared_py.observability import touch_worker_heartbeat

from feature_engine.correlation_graph import (
    CorrelationEngineState,
    compute_correlation_snapshot,
    correlation_dedupe_key,
)

if TYPE_CHECKING:
    from feature_engine.app import FeatureEngineSettings

logger = logging.getLogger("feature_engine.correlation_worker")


class CorrelationGraphWorker:
    """60s-Takt: Korrelationsmatrix + optional REGIME_DIVERGENCE_DETECTED."""

    def __init__(
        self,
        settings: Any,
        *,
        on_snapshot: Callable[[dict[str, Any]], None],
        logger_: logging.Logger | None = None,
    ) -> None:
        self._settings = settings
        self._on_snapshot = on_snapshot
        self._logger = logger_ or logger
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._state = CorrelationEngineState()
        self._bus = make_stream_bus_from_url(
            settings.redis_url,
            dedupe_ttl_sec=settings.eventbus_dedupe_ttl_sec,
            default_block_ms=settings.eventbus_default_block_ms,
            default_count=settings.eventbus_default_count,
            logger=self._logger,
        )
        self._last_error: str | None = None
        self._ticks = 0

    def stats_payload(self) -> dict[str, object]:
        return {
            "correlation_graph_enabled": bool(self._settings.correlation_graph_enabled),
            "correlation_ticks": self._ticks,
            "correlation_last_error": self._last_error,
            "correlation_state_ts_ms": self._state.updated_ts_ms,
        }

    async def start_background(self) -> None:
        if not self._settings.correlation_graph_enabled:
            self._logger.info("CorrelationGraphWorker: deaktiviert (CORRELATION_GRAPH_ENABLED=false)")
            return
        self._task = asyncio.create_task(self._loop(), name="correlation-graph-loop")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await asyncio.to_thread(self._bus.close)

    async def _loop(self) -> None:
        interval = max(15, int(self._settings.correlation_publish_interval_sec))
        while not self._stop.is_set():
            try:
                snap, self._state = await asyncio.to_thread(
                    compute_correlation_snapshot,
                    redis=self._bus.redis,
                    state=self._state,
                )
                self._on_snapshot(snap)
                dk = correlation_dedupe_key(snap)
                env = EventEnvelope(
                    event_type="intermarket_correlation_update",
                    symbol="GLOBAL",
                    dedupe_key=dk,
                    payload=snap,
                    trace={"source": "feature-engine-correlation"},
                )
                await asyncio.to_thread(
                    self._bus.publish,
                    STREAM_INTERMARKET_CORRELATION_UPDATE,
                    env,
                )
                rd = snap.get("regime_divergence") or {}
                if bool(rd.get("triggered")):
                    hour = int(snap.get("computed_ts_ms", 0)) // 3_600_000
                    rdk = hashlib.sha256(f"REGIME_DIV:{hour}:{rd.get('score_0_1')}".encode()).hexdigest()[:48]
                    env_r = EventEnvelope(
                        event_type="regime_divergence_detected",
                        symbol="BTCUSDT",
                        dedupe_key=rdk,
                        payload={
                            "event_name": "REGIME_DIVERGENCE_DETECTED",
                            "symbol": "BTCUSDT",
                            "computed_ts_ms": snap.get("computed_ts_ms"),
                            "score_0_1": rd.get("score_0_1"),
                            "debug": rd.get("debug"),
                            "parent_correlation_dedupe": dk,
                        },
                        trace={"source": "feature-engine-correlation"},
                    )
                    await asyncio.to_thread(
                        self._bus.publish,
                        STREAM_REGIME_DIVERGENCE_DETECTED,
                        env_r,
                    )
                self._last_error = None
                self._ticks += 1
                touch_worker_heartbeat("feature_engine_correlation")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._last_error = str(exc)[:500]
                self._logger.exception("CorrelationGraphWorker tick failed: %s", exc)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=float(interval))
            except TimeoutError:
                continue
