from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import psycopg
from redis.exceptions import RedisError
from shared_py.eventbus import (
    STREAM_STRUCTURE_UPDATED,
    ConsumedEvent,
    EventEnvelope,
    RedisStreamBus,
)
from shared_py.input_pipeline_provenance import (
    analyze_sorted_candle_starts,
    build_structure_input_provenance,
    coverage_ok,
    timeframe_to_ms,
)
from shared_py.observability import touch_worker_heartbeat
from shared_py.replay_determinism import stable_stream_event_id

from structure_engine.algorithms.breakouts import (
    box_to_json,
    build_box,
    pending_from_json,
    prebreak_side,
    update_false_breakout_watch,
)
from structure_engine.algorithms.compression import (
    CompressionParams,
    atr_pct_ratio_from_feature,
    fallback_atr_pct_ratio,
    next_compression_state,
    range_20_ratio,
)
from structure_engine.algorithms.swings import confirmed_ts_ms, detect_confirmed_swing
from structure_engine.algorithms.trend import (
    structure_event_on_bar_edge,
    trend_from_swings,
)
from structure_engine.settings import (
    StructureEngineSettings,
    is_supported_timeframe,
    normalize_timeframe,
)
from structure_engine.storage.repo import (
    StoredCandle,
    StructureRepository,
    merge_candle_history,
    stored_to_candles,
)


def _stable_json(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


@dataclass(slots=True)
class StructureWorkerStats:
    running: bool = False
    redis_connected: bool = False
    db_connected: bool = False
    group_ready: bool = False
    consumed_events: int = 0
    processed_events: int = 0
    dlq_events: int = 0
    last_event_id: str | None = None
    last_error: str | None = None
    last_structure_skip: str | None = None


class StructureWorker:
    def __init__(
        self,
        settings: StructureEngineSettings,
        repo: StructureRepository,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._settings = settings
        self._repo = repo
        self._logger = logger or logging.getLogger("structure_engine.worker")
        self._stats = StructureWorkerStats()
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
            "stream": self._settings.structure_stream,
            "group": self._settings.structure_group,
            "consumer": self._settings.structure_consumer,
            "consumed_events": self._stats.consumed_events,
            "processed_events": self._stats.processed_events,
            "dlq_events": self._stats.dlq_events,
            "last_event_id": self._stats.last_event_id,
            "last_error": self._stats.last_error,
            "last_structure_skip": self._stats.last_structure_skip,
        }

    async def run(self) -> None:
        self._stats.running = True
        try:
            while not self._stop_event.is_set():
                try:
                    await self._ensure_group()
                    items = await asyncio.to_thread(
                        self._bus.consume,
                        self._settings.structure_stream,
                        self._settings.structure_group,
                        self._settings.structure_consumer,
                        self._settings.eventbus_default_count,
                        self._settings.eventbus_default_block_ms,
                    )
                    self._stats.redis_connected = True
                    touch_worker_heartbeat("structure_engine")
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
                    self._logger.warning("structure worker redis error: %s", exc)
                    await asyncio.sleep(2)
                except Exception as exc:
                    self._stats.last_error = str(exc)
                    self._logger.exception("structure worker loop failed", exc_info=exc)
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
            self._settings.structure_stream,
            self._settings.structure_group,
        )
        self._stats.group_ready = True

    async def _handle_item(self, item: ConsumedEvent) -> None:
        self._stats.consumed_events += 1
        self._stats.last_event_id = item.envelope.event_id
        self._stats.last_structure_skip = None
        try:
            await asyncio.to_thread(self._process_envelope, item.envelope)
            self._stats.db_connected = True
            self._stats.processed_events += 1
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
                "structure worker DLQ event_id=%s error=%s",
                item.envelope.event_id,
                exc,
            )

    def _process_envelope(self, env: EventEnvelope) -> None:
        if env.event_type != "candle_close":
            self._stats.last_structure_skip = "skip_non_candle_close"
            self._logger.debug(
                "structure worker skip event_type=%s id=%s", env.event_type, env.event_id
            )
            return
        timeframe = normalize_timeframe(_extract_timeframe(env))
        if not is_supported_timeframe(timeframe):
            self._stats.last_structure_skip = "unsupported_timeframe"
            self._logger.debug(
                "structure worker skip unsupported timeframe=%s id=%s",
                timeframe,
                env.event_id,
            )
            return
        start_ts_ms = _extract_start_ts_ms(env)
        symbol = str(env.symbol).strip()
        current = _stored_candle_from_envelope(env, timeframe)
        history = self._repo.fetch_candles(
            symbol=symbol,
            timeframe=timeframe,
            end_start_ts_ms=start_ts_ms,
            limit=self._settings.structure_lookback_candles,
        )
        merged = merge_candle_history(history, current)
        candles = stored_to_candles(merged)
        left_n, right_n = self._settings.pivot_for_timeframe(timeframe)
        min_len = left_n + right_n + 1
        if len(candles) < min_len:
            self._stats.last_structure_skip = "insufficient_candles"
            self._logger.warning(
                "structure worker zu wenig Candles symbol=%s tf=%s haben=%s need=%s",
                symbol,
                timeframe,
                len(candles),
                min_len,
            )
            return

        gap_step_ms = timeframe_to_ms(timeframe)
        max_gap_bars = int(
            analyze_sorted_candle_starts(
                [m.start_ts_ms for m in merged],
                step_ms=gap_step_ms,
            )["max_gap_bars"]
        )
        bos_allowed = coverage_ok(
            max_gap_bars,
            max_allowed_gap_bars=self._settings.structure_bos_choch_max_gap_bars,
        )
        fb_enabled = bos_allowed

        swing = detect_confirmed_swing(candles, left_n, right_n)
        swing_inserted = False
        if swing is not None:
            swing_inserted = self._repo.insert_swing_if_new(
                swing_id=uuid4(),
                symbol=symbol,
                timeframe=timeframe,
                start_ts_ms=swing.ts_ms,
                kind=swing.kind,
                price=swing.price,
                left_n=left_n,
                right_n=right_n,
                confirmed_ts_ms=confirmed_ts_ms(candles),
            )

        last_highs = self._repo.fetch_last_two_swings(
            symbol=symbol, timeframe=timeframe, kind="high"
        )
        last_lows = self._repo.fetch_last_two_swings(
            symbol=symbol, timeframe=timeframe, kind="low"
        )
        trend_dir = trend_from_swings(last_highs, last_lows)
        last_h = self._repo.fetch_last_swing_price(symbol=symbol, timeframe=timeframe, kind="high")
        last_l = self._repo.fetch_last_swing_price(symbol=symbol, timeframe=timeframe, kind="low")

        close = candles[-1].c
        prev_close = candles[-2].c if len(candles) >= 2 else None
        raw_struct_type, raw_struct_dir = structure_event_on_bar_edge(
            trend_dir, close, prev_close, last_h, last_l
        )
        if not bos_allowed:
            struct_type, struct_dir = None, None
            bos_choch_suppressed = raw_struct_type in ("BOS", "CHOCH")
        else:
            struct_type, struct_dir = raw_struct_type, raw_struct_dir
            bos_choch_suppressed = False

        feat = self._repo.get_feature_row(
            symbol=symbol, timeframe=timeframe, start_ts_ms=start_ts_ms
        )
        if feat is None:
            self._logger.warning(
                "structure-engine: keine Feature-Row (ATR) symbol=%s tf=%s ts=%s",
                symbol,
                timeframe,
                start_ts_ms,
            )
        atr_14 = float(feat["atr_14"]) if feat and feat.get("atr_14") is not None else None
        atrp_14 = float(feat["atrp_14"]) if feat and feat.get("atrp_14") is not None else None
        atr_ratio, _ = atr_pct_ratio_from_feature(atr_14, atrp_14, close)
        if math.isnan(atr_ratio):
            atr_ratio = fallback_atr_pct_ratio(candles)
            if math.isnan(atr_ratio):
                self._logger.warning(
                    "structure-engine: ATR%% nicht berechenbar symbol=%s tf=%s ts=%s",
                    symbol,
                    timeframe,
                    start_ts_ms,
                )
            else:
                self._logger.info(
                    "structure-engine: ATR%% aus lokaler TR-Schaetzung symbol=%s tf=%s ts=%s",
                    symbol,
                    timeframe,
                    start_ts_ms,
                )

        highs = [c.h for c in candles]
        lows = [c.l for c in candles]
        range20 = range_20_ratio(highs, lows, close)
        range20_prev: float | None = None
        if len(candles) >= 21:
            range20_prev = range_20_ratio(highs[:-1], lows[:-1], candles[-2].c)

        prev_state = self._repo.get_structure_state_row(symbol=symbol, timeframe=timeframe)
        prev_comp = bool(prev_state["compression_flag"]) if prev_state else False
        prev_box_raw: dict[str, Any] = {}
        if prev_state and isinstance(prev_state.get("breakout_box_json"), dict):
            prev_box_raw = prev_state["breakout_box_json"]

        cparams = CompressionParams(
            atrp_on=self._settings.compression_atrp_thresh,
            atrp_off=self._settings.compression_atrp_thresh_off,
            range_on=self._settings.compression_range_thresh,
            range_off=self._settings.compression_range_thresh_off,
        )
        comp_flag, comp_evt = next_compression_state(
            prev_comp, atr_ratio, range20, range20_prev, cparams
        )

        n_box = self._settings.box_window_for_timeframe(timeframe)
        breakout_box_payload: dict[str, Any] = {}
        br_store: list[tuple[str, dict[str, Any]]] = []

        if comp_flag:
            box = build_box(highs, lows, [c.ts_ms for c in candles], n_box)
            if box is None:
                self._logger.warning(
                    "structure-engine: Kompression aktiv aber Box unvollstaendig "
                    "symbol=%s tf=%s bars=%s n_box=%s",
                    symbol,
                    timeframe,
                    len(candles),
                    n_box,
                )
                breakout_box_payload = {}
            else:
                prebreak = prebreak_side(close, box, self._settings.box_prebreak_dist_bps)
                if fb_enabled:
                    pending = (
                        pending_from_json(prev_box_raw) if prev_comp else None
                    )
                    pending, br_ev = update_false_breakout_watch(
                        close=close,
                        box=box,
                        buffer_bps=self._settings.box_breakout_buffer_bps,
                        window_bars=self._settings.false_breakout_window_bars,
                        current_ts_ms=start_ts_ms,
                        pending=pending,
                    )
                    br_store.extend(br_ev)
                else:
                    pending = None
                breakout_box_payload = box_to_json(box, prebreak=prebreak, pending=pending)

        events_to_store: list[tuple[str, dict[str, Any]]] = []
        if comp_evt == "COMPRESSION_ON":
            events_to_store.append(("COMPRESSION_ON", {"range20": range20, "atr_pct": atr_ratio}))
        elif comp_evt == "COMPRESSION_OFF":
            events_to_store.append(("COMPRESSION_OFF", {"range20": range20, "atr_pct": atr_ratio}))

        if struct_type == "BOS" and struct_dir is not None:
            events_to_store.append(
                ("BOS", {"direction": struct_dir, "close": close}),
            )
        elif struct_type == "CHOCH" and struct_dir is not None:
            events_to_store.append(
                ("CHOCH", {"direction": struct_dir, "close": close}),
            )

        for typ, det in br_store:
            events_to_store.append((typ, det))

        for etype, details in events_to_store:
            self._repo.insert_structure_event(
                event_id=uuid4(),
                symbol=symbol,
                timeframe=timeframe,
                ts_ms=start_ts_ms,
                event_type=etype,
                details=details,
            )

        updated_ts_ms = int(time.time() * 1000)
        structure_input_provenance = build_structure_input_provenance(
            symbol=symbol,
            timeframe=timeframe,
            sorted_bar_starts_ms=[m.start_ts_ms for m in merged],
            bar_close_ts_ms=start_ts_ms,
            max_allowed_gap_bars=self._settings.structure_max_allowed_gap_bars,
            bos_choch_max_gap_bars=self._settings.structure_bos_choch_max_gap_bars,
            structure_lookback_bars=len(merged),
            updated_ts_ms=updated_ts_ms,
            source_event_id=env.event_id,
            bos_choch_suppressed=bos_choch_suppressed,
            false_breakout_watch_enabled=fb_enabled,
        )
        if env.instrument is not None:
            structure_input_provenance["instrument_context"] = {
                "schema_version": env.instrument.schema_version,
                "canonical_instrument_id": env.instrument.canonical_instrument_id,
                "market_family": env.instrument.market_family,
                "category_key": env.instrument.category_key,
                "analytics_eligible": env.instrument.analytics_eligible,
                "live_execution_enabled": env.instrument.live_execution_enabled,
            }
        self._repo.upsert_structure_state(
            symbol=symbol,
            timeframe=timeframe,
            last_ts_ms=start_ts_ms,
            trend_dir=trend_dir,
            last_swing_high_price=last_h,
            last_swing_low_price=last_l,
            compression_flag=comp_flag,
            breakout_box_json=breakout_box_payload,
            updated_ts_ms=updated_ts_ms,
            input_provenance=structure_input_provenance,
        )

        old_trend = str(prev_state["trend_dir"]) if prev_state else None
        old_box_s = _stable_json(prev_box_raw)
        new_box_s = _stable_json(breakout_box_payload)
        changed = (
            swing_inserted
            or old_trend != trend_dir
            or prev_comp != comp_flag
            or old_box_s != new_box_s
            or len(events_to_store) > 0
        )

        if changed:
            swings_payload = self._repo.fetch_recent_swing_ids(
                symbol=symbol, timeframe=timeframe, limit=8
            )
            box_pub: dict[str, Any] | None = None
            if comp_flag and breakout_box_payload.get("high") is not None:
                box_pub = {
                    "high": breakout_box_payload["high"],
                    "low": breakout_box_payload["low"],
                    "start_ts_ms": breakout_box_payload["start_ts_ms"],
                    "end_ts_ms": breakout_box_payload["end_ts_ms"],
                }
            sk = f"structure:{symbol}:{timeframe}:{start_ts_ms}"
            merged_trace = dict(env.trace or {})
            merged_trace["candle_close_event_id"] = env.event_id
            merged_trace["source_event_id"] = env.event_id
            out = EventEnvelope(
                event_id=stable_stream_event_id(
                    stream=STREAM_STRUCTURE_UPDATED,
                    dedupe_key=sk,
                ),
                event_type="structure_updated",
                symbol=symbol,
                timeframe=timeframe,
                exchange_ts_ms=start_ts_ms,
                dedupe_key=sk,
                payload={
                    "ts_ms": start_ts_ms,
                    "trend_dir": trend_dir,
                    "swings": swings_payload,
                    "compression_flag": comp_flag,
                    "breakout_box": box_pub,
                    "input_provenance": structure_input_provenance,
                },
                trace=merged_trace,
            )
            self._bus.publish(STREAM_STRUCTURE_UPDATED, out)
            self._logger.info(
                "published structure_updated symbol=%s tf=%s ts=%s",
                symbol,
                timeframe,
                start_ts_ms,
            )

        self._stats.last_structure_skip = None

    async def _publish_dlq(self, item: ConsumedEvent, exc: Exception) -> None:
        await asyncio.to_thread(
            self._bus.publish_dlq,
            item.envelope,
            {"stage": "structure_worker", "error": str(exc)},
        )
        self._stats.dlq_events += 1

    async def _ack(self, item: ConsumedEvent) -> None:
        await asyncio.to_thread(
            self._bus.ack,
            item.stream,
            self._settings.structure_group,
            item.message_id,
        )


def _extract_timeframe(event: EventEnvelope) -> str:
    if event.timeframe is not None and str(event.timeframe).strip():
        return str(event.timeframe).strip()
    payload = event.payload
    raw = payload.get("timeframe")
    if raw is not None and str(raw).strip():
        return str(raw).strip()
    raise ValueError("candle_close event ohne timeframe")


def _extract_start_ts_ms(event: EventEnvelope) -> int:
    payload = event.payload
    raw = payload.get("start_ts_ms")
    if raw is None:
        raise ValueError("candle_close payload ohne start_ts_ms")
    return int(str(raw))


def _stored_candle_from_envelope(event: EventEnvelope, timeframe: str) -> StoredCandle:
    payload = event.payload
    return StoredCandle(
        symbol=str(event.symbol).strip(),
        timeframe=timeframe,
        start_ts_ms=_extract_start_ts_ms(event),
        o=float(payload["open"]),
        h=float(payload["high"]),
        l=float(payload["low"]),
        c=float(payload["close"]),
    )
