from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import psycopg
from redis.exceptions import RedisError
from shared_py.eventbus import (
    STREAM_DRAWING_UPDATED,
    ConsumedEvent,
    EventEnvelope,
    RedisStreamBus,
)
from shared_py.input_pipeline_provenance import build_drawing_input_provenance
from shared_py.observability import touch_worker_heartbeat
from shared_py.replay_determinism import stable_stream_event_id

from drawing_engine.builder import build_drawing_records
from drawing_engine.family_adapter import apply_family_drawing_hints
from drawing_engine.persist import persist_drawing_batch
from drawing_engine.settings import DrawingEngineSettings, normalize_timeframe
from drawing_engine.storage.repo import DrawingRepository

KNOWN_TFS = {"1m", "5m", "15m", "1H", "4H"}


@dataclass(slots=True)
class DrawingWorkerStats:
    running: bool = False
    redis_connected: bool = False
    db_connected: bool = False
    group_ready: bool = False
    consumed_events: int = 0
    processed_events: int = 0
    dlq_events: int = 0
    last_event_id: str | None = None
    last_error: str | None = None
    last_drawing_skip: str | None = None


class DrawingWorker:
    def __init__(
        self,
        settings: DrawingEngineSettings,
        repo: DrawingRepository,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._settings = settings
        self._repo = repo
        self._logger = logger or logging.getLogger("drawing_engine.worker")
        self._stats = DrawingWorkerStats()
        self._stop_event = asyncio.Event()
        self._bus = RedisStreamBus.from_url(
            settings.redis_url,
            dedupe_ttl_sec=settings.eventbus_dedupe_ttl_sec,
            default_block_ms=settings.eventbus_default_block_ms,
            default_count=settings.eventbus_default_count,
        )

    def stats_payload(self) -> dict[str, object]:
        return {
            "running": self._stats.running,
            "redis_connected": self._stats.redis_connected,
            "db_connected": self._stats.db_connected,
            "group_ready": self._stats.group_ready,
            "stream": self._settings.drawing_stream,
            "group": self._settings.drawing_group,
            "consumer": self._settings.drawing_consumer,
            "consumed_events": self._stats.consumed_events,
            "processed_events": self._stats.processed_events,
            "dlq_events": self._stats.dlq_events,
            "last_event_id": self._stats.last_event_id,
            "last_error": self._stats.last_error,
            "last_drawing_skip": self._stats.last_drawing_skip,
        }

    async def run(self) -> None:
        self._stats.running = True
        try:
            while not self._stop_event.is_set():
                try:
                    await self._ensure_group()
                    items = await asyncio.to_thread(
                        self._bus.consume,
                        self._settings.drawing_stream,
                        self._settings.drawing_group,
                        self._settings.drawing_consumer,
                        self._settings.eventbus_default_count,
                        self._settings.eventbus_default_block_ms,
                    )
                    self._stats.redis_connected = True
                    touch_worker_heartbeat("drawing_engine")
                    if not items:
                        continue
                    for item in items:
                        await self._handle_item(item)
                except asyncio.CancelledError:
                    raise
                except (OSError, RedisError) as exc:
                    self._stats.redis_connected = False
                    self._stats.group_ready = False
                    self._stats.last_error = str(exc)
                    self._logger.warning("drawing worker redis error: %s", exc)
                    await asyncio.sleep(2)
                except Exception as exc:
                    self._stats.last_error = str(exc)
                    self._logger.exception("drawing worker loop failed", exc_info=exc)
                    await asyncio.sleep(2)
        finally:
            self._stats.running = False
            await self.close()

    async def stop(self) -> None:
        self._stop_event.set()

    async def close(self) -> None:
        await asyncio.to_thread(self._bus.redis.close)

    async def _ensure_group(self) -> None:
        if self._stats.group_ready:
            return
        await asyncio.to_thread(
            self._bus.ensure_group,
            self._settings.drawing_stream,
            self._settings.drawing_group,
        )
        self._stats.group_ready = True

    async def _handle_item(self, item: ConsumedEvent) -> None:
        self._stats.consumed_events += 1
        self._stats.last_event_id = item.envelope.event_id
        self._stats.last_drawing_skip = None
        try:
            changed = await asyncio.to_thread(self._process_envelope, item.envelope)
            self._stats.db_connected = True
            self._stats.processed_events += 1
            if changed:
                await asyncio.to_thread(self._publish_drawing_updated, item.envelope, changed)
            await self._ack(item)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._stats.last_error = str(exc)
            if isinstance(exc, psycopg.Error):
                self._stats.db_connected = False
            await self._publish_dlq(item, exc)
            await self._ack(item)
            self._logger.warning(
                "drawing worker DLQ event_id=%s error=%s",
                item.envelope.event_id,
                exc,
            )

    def _process_envelope(self, env: EventEnvelope) -> list[str]:
        if env.event_type != "structure_updated":
            self._stats.last_drawing_skip = "skip_non_structure_updated"
            self._logger.debug("skip event_type=%s", env.event_type)
            return []
        symbol = str(env.symbol).strip()
        timeframe = normalize_timeframe(_extract_timeframe(env))
        if timeframe not in KNOWN_TFS:
            self._stats.last_drawing_skip = "unsupported_timeframe"
            self._logger.debug("skip timeframe=%s", timeframe)
            return []
        payload = env.payload
        ts_ms = int(payload.get("ts_ms") or env.exchange_ts_ms or 0)
        if ts_ms <= 0:
            ts_ms = int(env.ingest_ts_ms)

        state = self._repo.fetch_structure_state(symbol=symbol, timeframe=timeframe)
        trend_dir = str(state["trend_dir"]) if state else "RANGE"
        breakout_box: dict[str, Any] | None = None
        if state and isinstance(state.get("breakout_box_json"), dict):
            breakout_box = state["breakout_box_json"]

        swings = self._repo.fetch_swings(symbol=symbol, timeframe=timeframe, limit=250)
        last_close = self._repo.fetch_latest_close(symbol=symbol, timeframe=timeframe)
        if last_close is None:
            self._stats.last_drawing_skip = "no_close_candle"
            self._logger.warning(
                "drawing-engine: keine Candle fuer close, skip symbol=%s tf=%s",
                symbol,
                timeframe,
            )
            return []

        ob = self._repo.fetch_latest_orderbook_raw(symbol=symbol)
        bids_raw: Any = None
        asks_raw: Any = None
        ob_ts: int | None = None
        if ob is not None:
            bids_raw, asks_raw, ob_ts = ob[0], ob[1], ob[2]

        now_ms = int(time.time() * 1000)
        orderbook_fresh = False
        if ob_ts is not None:
            orderbook_fresh = (now_ms - ob_ts) <= self._settings.drawing_max_orderbook_age_ms

        st_prov_raw = state.get("input_provenance_json") if state else None
        st_prov: dict[str, Any] | None = None
        if isinstance(st_prov_raw, dict):
            st_prov = st_prov_raw
        elif isinstance(st_prov_raw, str):
            st_prov = json.loads(st_prov_raw)
        instrument_ctx: dict[str, Any] | None = None
        market_family: str | None = None
        if isinstance(st_prov, dict):
            ic = st_prov.get("instrument_context")
            if isinstance(ic, dict):
                instrument_ctx = ic
                raw_f = ic.get("market_family")
                if isinstance(raw_f, str) and raw_f.strip():
                    market_family = raw_f.strip().lower()
        struct_cov: bool | None = None
        if isinstance(st_prov, dict):
            cs = st_prov.get("candle_series")
            if isinstance(cs, dict) and "coverage_ok" in cs:
                struct_cov = bool(cs["coverage_ok"])

        batch_prov = build_drawing_input_provenance(
            symbol=symbol,
            timeframe=timeframe,
            structure_bar_ts_ms=ts_ms,
            structure_state_updated_ts_ms=(
                int(state["updated_ts_ms"])
                if state and state.get("updated_ts_ms") is not None
                else None
            ),
            structure_provenance=st_prov,
            orderbook_ts_ms=ob_ts,
            drawing_computed_ts_ms=now_ms,
            orderbook_max_age_ms=self._settings.drawing_max_orderbook_age_ms,
            orderbook_fresh=orderbook_fresh,
        )

        zone_bps = Decimal(str(self._settings.zone_cluster_bps))
        pad_bps = Decimal(str(self._settings.zone_pad_bps))
        stop_bps = Decimal(str(self._settings.stop_pad_bps))
        liq_cluster = Decimal(str(self._settings.liquidity_cluster_bps))

        records = build_drawing_records(
            symbol=symbol,
            timeframe=timeframe,
            trend_dir=trend_dir,
            last_close=last_close,
            swing_rows=swings,
            breakout_box=breakout_box,
            bids_raw=bids_raw,
            asks_raw=asks_raw,
            zone_cluster_bps=zone_bps,
            zone_pad_bps=pad_bps,
            stop_pad_bps=stop_bps,
            liquidity_topk=self._settings.liquidity_topk,
            liquidity_cluster_bps=liq_cluster,
            ts_ms=ts_ms,
        )

        _adjust_drawing_records_for_input_gates(
            records,
            orderbook_fresh=orderbook_fresh,
            structure_coverage_ok=struct_cov,
        )
        apply_family_drawing_hints(
            records,
            market_family=market_family,
            instrument_context=instrument_ctx,
        )

        if not records:
            self._stats.last_drawing_skip = "no_geometry_candidates"
            return []

        parent_ids = persist_drawing_batch(
            self._repo,
            symbol=symbol,
            timeframe=timeframe,
            records=records,
            ts_ms=ts_ms,
            batch_input_provenance=batch_prov,
            logger=self._logger,
        )
        if parent_ids:
            self._stats.last_drawing_skip = None
        else:
            self._stats.last_drawing_skip = "no_drawing_revision"
        return parent_ids

    def _publish_drawing_updated(
        self,
        source: EventEnvelope,
        parent_ids: list[str],
    ) -> None:
        if not parent_ids:
            return
        dk = f"drawing:{source.symbol}:{source.timeframe}:{source.event_id}"
        merged_trace = dict(source.trace or {})
        merged_trace["structure_updated_event_id"] = source.event_id
        merged_trace["source_event_id"] = source.event_id
        out = EventEnvelope(
            event_id=stable_stream_event_id(stream=STREAM_DRAWING_UPDATED, dedupe_key=dk),
            event_type="drawing_updated",
            symbol=source.symbol,
            timeframe=source.timeframe,
            exchange_ts_ms=source.exchange_ts_ms,
            dedupe_key=dk,
            payload={
                "parent_ids": parent_ids,
                "ts_ms": source.payload.get("ts_ms") or source.exchange_ts_ms,
                "source_event_id": source.event_id,
            },
            trace=merged_trace,
        )
        self._bus.publish(STREAM_DRAWING_UPDATED, out)
        self._logger.info(
            "published drawing_updated symbol=%s tf=%s parents=%s",
            source.symbol,
            source.timeframe,
            len(parent_ids),
        )

    async def _publish_dlq(self, item: ConsumedEvent, exc: Exception) -> None:
        await asyncio.to_thread(
            self._bus.publish_dlq,
            item.envelope,
            {"stage": "drawing_worker", "error": str(exc)},
        )
        self._stats.dlq_events += 1

    async def _ack(self, item: ConsumedEvent) -> None:
        await asyncio.to_thread(
            self._bus.ack,
            item.stream,
            self._settings.drawing_group,
            item.message_id,
        )


def _adjust_drawing_records_for_input_gates(
    records: list[dict[str, Any]],
    *,
    orderbook_fresh: bool,
    structure_coverage_ok: bool | None,
) -> None:
    for r in records:
        reasons = list(r["reasons"])
        conf = float(r["confidence"])
        if not orderbook_fresh:
            if "input:orderbook_stale" not in reasons:
                reasons.append("input:orderbook_stale")
            conf *= 0.88
        if structure_coverage_ok is False:
            if "input:candle_series_gappy" not in reasons:
                reasons.append("input:candle_series_gappy")
            conf *= 0.9
        r["reasons"] = reasons
        r["confidence"] = max(0.0, min(100.0, conf))


def _extract_timeframe(env: EventEnvelope) -> str:
    if env.timeframe is not None and str(env.timeframe).strip():
        return str(env.timeframe).strip()
    raw = env.payload.get("timeframe")
    if raw is not None and str(raw).strip():
        return str(raw).strip()
    raise ValueError("structure_updated ohne timeframe")
