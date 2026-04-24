from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from shared_py.bitget.instruments import BitgetInstrumentIdentity
from shared_py.eventbus import STREAM_ORDERFLOW_TOXICITY, EventEnvelope
from shared_py.observability.metrics import (
    observe_market_vpin_inference,
    set_market_vpin_score,
)
from shared_py.rust_core_bridge import APEX_CORE_AVAILABLE, get_vpin_engine_class

from market_stream.collectors.trades import TradeRecord
from market_stream.sinks.eventbus import AsyncRedisEventBus

_VPIN_SLO_SEC = 0.005


@dataclass
class VpinTelemetrySettings:
    enabled: bool
    bucket_volume: float
    window_buckets: int
    publish_interval_sec: int


class VpinTelemetry:
    """
    VPIN/Orderflow-Toxizitaet: rollierendes Volumen-Fenster, Rust-Engine
    (``VpinEngine``/``VpinAccumulator``), Prometheus ``market_vpin_score``.
    """

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
        if settings.enabled and APEX_CORE_AVAILABLE:
            VpinClass = get_vpin_engine_class()
            if VpinClass is not None:
                try:
                    self._engine = VpinClass(
                        settings.bucket_volume, settings.window_buckets
                    )
                    set_market_vpin_score(symbol=self._symbol, score=0.0)
                    self._logger.info(
                        "VPIN telemetry (Rust) enabled bucket_volume=%s "
                        "window_buckets=%s interval_sec=%s symbol=%s",
                        settings.bucket_volume,
                        settings.window_buckets,
                        settings.publish_interval_sec,
                        self._symbol,
                    )
                except Exception as exc:  # noqa: BLE001
                    self._logger.warning(
                        "VPIN: VpinEngine instanziieren fehlgeschlagen: %s",
                        exc,
                    )
                    self._engine = None
        if settings.enabled and self._engine is None:
            if not APEX_CORE_AVAILABLE or get_vpin_engine_class() is None:
                self._logger.warning(
                    "VPIN disabled: apex_core nicht verfuegbar; "
                    "maturin develop in shared_rs/apex_core bauen."
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
        except Exception as exc:  # noqa: BLE001
            self._logger.debug("vpin set_mid_from_bid_ask failed: %s", exc)

    def on_trades(self, trades: list[TradeRecord]) -> None:
        if self._engine is None or not trades:
            return
        t0 = time.perf_counter()
        try:
            for t in trades:
                p = float(t.price)
                sz = float(t.size)
                tb = t.side == "buy"
                self._engine.push_trade(p, sz, tb)
            score = float(self._engine.toxicity_score())
        except (TypeError, ValueError) as exc:  # noqa: BLE001
            self._logger.debug("vpin push_trade skip: %s", exc)
            return
        except Exception as exc:  # noqa: BLE001
            self._logger.debug("vpin batch/toxicity_score failed: %s", exc)
            return
        dt = time.perf_counter() - t0
        set_market_vpin_score(symbol=self._symbol, score=score)
        observe_market_vpin_inference(
            symbol=self._symbol, duration_sec=dt, slow_threshold_sec=_VPIN_SLO_SEC
        )
        if dt > _VPIN_SLO_SEC:
            self._logger.warning(
                "VPIN inference SLO: duration_ms=%.3f > %sms symbol=%s",
                dt * 1000.0,
                _VPIN_SLO_SEC * 1000.0,
                self._symbol,
            )

    def _refresh_prometheus_gauge(self) -> None:
        if self._engine is None:
            return
        try:
            s = float(self._engine.toxicity_score())
        except Exception:  # noqa: BLE001
            return
        set_market_vpin_score(symbol=self._symbol, score=s)

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
                self._refresh_prometheus_gauge()
                await self._publish_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
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
            dedupe_key=(
                f"orderflow_toxicity:{self._symbol}:"
                f"{ts_ms // (self._settings.publish_interval_sec * 1000)}"
            ),
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
