from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from shared_py.bitget.instruments import BitgetInstrumentIdentity
from shared_py.eventbus import STREAM_ORDERFLOW_TOXICITY, EventEnvelope

from market_stream.collectors.trades import TradeRecord
from market_stream.sinks.eventbus import AsyncRedisEventBus


@dataclass
class VpinTelemetrySettings:
    enabled: bool
    bucket_volume: float
    window_buckets: int
    publish_interval_sec: int


class VpinTelemetry:
    """Rust-VPIN (`apex_core.VpinEngine`) + periodischer Eventbus-Push."""

    def __init__(
        self,
        *,
        settings: VpinTelemetrySettings,
        symbol: str,
        event_bus: AsyncRedisEventBus,
        instrument: BitgetInstrumentIdentity | None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._settings = settings
        self._symbol = symbol
        self._event_bus = event_bus
        self._instrument = instrument
        self._logger = logger or logging.getLogger("market_stream.vpin")
        self._engine: Any | None = None
        if settings.enabled:
            try:
                from apex_core import VpinEngine

                self._engine = VpinEngine(settings.bucket_volume, settings.window_buckets)
                self._logger.info(
                    "VPIN telemetry enabled bucket_volume=%s window_buckets=%s interval_sec=%s",
                    settings.bucket_volume,
                    settings.window_buckets,
                    settings.publish_interval_sec,
                )
            except ImportError as exc:
                self._logger.warning(
                    "VPIN disabled: apex_core not importable (%s); maturin develop apex_core",
                    exc,
                )

    @property
    def enabled(self) -> bool:
        return self._engine is not None

    @property
    def runs_publish_loop(self) -> bool:
        return self._settings.enabled and self._engine is not None

    def on_best_quote(self, bid: float, ask: float) -> None:
        if self._engine is None:
            return
        try:
            self._engine.set_mid_from_bid_ask(bid, ask)
        except Exception as exc:
            self._logger.debug("vpin set_mid_from_bid_ask failed: %s", exc)

    def on_trades(self, trades: list[TradeRecord]) -> None:
        if self._engine is None or not trades:
            return
        for t in trades:
            try:
                p = float(t.price)
                sz = float(t.size)
                tb = True if t.side == "buy" else False
                self._engine.push_trade(p, sz, tb)
            except (TypeError, ValueError) as exc:
                self._logger.debug("vpin push_trade skip: %s", exc)

    def toxicity_score(self) -> float:
        if self._engine is None:
            return 0.0
        return float(self._engine.toxicity_score())

    def completed_buckets(self) -> int:
        if self._engine is None:
            return 0
        return int(self._engine.completed_bucket_count())

    async def publish_loop(self) -> None:
        if self._engine is None:
            return
        interval = max(1, int(self._settings.publish_interval_sec))
        while True:
            await asyncio.sleep(float(interval))
            try:
                await self._publish_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._logger.warning("vpin publish_once failed: %s", exc)

    async def _publish_once(self) -> None:
        ts_ms = int(time.time() * 1000)
        score = self.toxicity_score()
        n_done = self.completed_buckets()
        envelope = EventEnvelope(
            event_type="orderflow_toxicity",
            symbol=self._symbol,
            instrument=self._instrument,
            exchange_ts_ms=ts_ms,
            dedupe_key=f"orderflow_toxicity:{self._symbol}:{ts_ms // (self._settings.publish_interval_sec * 1000)}",
            payload={
                "schema_version": "orderflow_toxicity/v1",
                "toxicity_score_0_1": score,
                "completed_buckets": n_done,
                "vpin_bucket_volume": self._settings.bucket_volume,
                "vpin_window_buckets": self._settings.window_buckets,
                "source": "market_stream.vpin",
            },
            trace={"source": "market_stream.vpin"},
        )
        await self._event_bus.publish(STREAM_ORDERFLOW_TOXICITY, envelope)
