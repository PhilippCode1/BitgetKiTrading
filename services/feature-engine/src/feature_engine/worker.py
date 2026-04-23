from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import psycopg
from redis.exceptions import RedisError
from shared_py.analysis import (
    FEATURE_NAMESPACE_BUNDLE_VERSION,
    compute_data_completeness_0_1,
    compute_pipeline_trade_mode,
    compute_staleness_score_0_1,
    family_foreign_namespace_violations,
    feature_namespaces_for_identity,
    gate_cross_family_derivative_leak,
    gate_tick_lot_vs_metadata,
    sanitize_ticker_snapshot_for_family,
    validate_event_vs_resolved_metadata,
)
from shared_py.bitget.catalog import (
    InstrumentCatalogUnavailableError,
    UnknownInstrumentError,
)
from shared_py.bitget.instruments import BitgetInstrumentIdentity
from shared_py.bitget.metadata import (
    BitgetInstrumentMetadataService,
    BitgetInstrumentResolvedMetadata,
)
from shared_py.eventbus import ConsumedEvent, RedisStreamBus, SharedMemoryBus, make_stream_bus_from_url
from shared_py.input_pipeline_provenance import (
    analyze_sorted_candle_starts,
    build_feature_input_provenance,
    realized_vol_std_log_returns,
)
from shared_py.model_contracts import (
    FEATURE_SCHEMA_HASH,
    FEATURE_SCHEMA_VERSION,
    MODEL_TIMEFRAMES,
    normalize_model_timeframe,
)
from shared_py.observability import arun_periodic_heartbeat

from feature_engine import numeric_hotpath as _num
from feature_engine.features import (
    OHLC,
    atr_percent,
    build_market_context_features,
    candle_impulse,
    confluence_score,
    momentum_score,
    range_score,
    simple_return,
    volume_zscore,
)
from feature_engine.storage import (
    CandleFeatureRow,
    FeatureRepository,
    StoredCandle,
    TickerSnapshot,
)

if TYPE_CHECKING:
    from feature_engine.app import FeatureEngineSettings


CONFLUENCE_TIMEFRAMES = MODEL_TIMEFRAMES
TIMEFRAME_TO_MS = {
    "1m": 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "1H": 60 * 60_000,
    "4H": 4 * 60 * 60_000,
}


@dataclass(slots=True)
class FeatureWorkerStats:
    running: bool = False
    redis_connected: bool = False
    db_connected: bool = False
    group_ready: bool = False
    consumed_events: int = 0
    processed_events: int = 0
    dlq_events: int = 0
    last_event_id: str | None = None
    last_feature_symbol: str | None = None
    last_feature_market_family: str | None = None
    last_feature_timeframe: str | None = None
    last_feature_start_ts_ms: int | None = None
    last_computed_ts_ms: int | None = None
    last_error: str | None = None


class FeatureWorker:
    def __init__(
        self,
        settings: FeatureEngineSettings,
        repo: FeatureRepository,
        metadata_service: BitgetInstrumentMetadataService,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._settings = settings
        self._repo = repo
        self._metadata_service = metadata_service
        self._logger = logger or logging.getLogger("feature_engine.worker")
        self._stats = FeatureWorkerStats()
        self._stop_event = asyncio.Event()
        self._bus: RedisStreamBus | SharedMemoryBus = make_stream_bus_from_url(
            settings.redis_url,
            dedupe_ttl_sec=settings.eventbus_dedupe_ttl_sec,
            default_block_ms=settings.eventbus_default_block_ms,
            default_count=settings.eventbus_default_count,
            logger=self._logger,
        )

    def stats_payload(self) -> dict[str, object]:
        return {
            "running": self._stats.running,
            "redis_connected": self._stats.redis_connected,
            "db_connected": self._stats.db_connected,
            "group_ready": self._stats.group_ready,
            "stream": self._settings.feature_stream,
            "group": self._settings.feature_group,
            "consumer": self._settings.feature_consumer,
            "consumed_events": self._stats.consumed_events,
            "processed_events": self._stats.processed_events,
            "dlq_events": self._stats.dlq_events,
            "last_event_id": self._stats.last_event_id,
            "last_feature_symbol": self._stats.last_feature_symbol,
            "last_feature_market_family": self._stats.last_feature_market_family,
            "last_feature_timeframe": self._stats.last_feature_timeframe,
            "last_feature_start_ts_ms": self._stats.last_feature_start_ts_ms,
            "last_computed_ts_ms": self._stats.last_computed_ts_ms,
            "last_error": self._stats.last_error,
        }

    async def run(self) -> None:
        self._stats.running = True
        hb_stop = asyncio.Event()
        hb_task = asyncio.create_task(
            arun_periodic_heartbeat("feature_engine", 10.0, hb_stop),
            name="feature_engine_heartbeat",
        )
        try:
            while not self._stop_event.is_set():
                try:
                    await self._ensure_group()
                    items = await asyncio.to_thread(
                        self._bus.consume,
                        self._settings.feature_stream,
                        self._settings.feature_group,
                        self._settings.feature_consumer,
                        self._settings.eventbus_default_count,
                        self._settings.eventbus_default_block_ms,
                    )
                    self._stats.redis_connected = True
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
                    self._logger.warning("feature worker redis error: %s", exc)
                    await asyncio.sleep(2)
                except Exception as exc:
                    self._stats.last_error = str(exc)
                    self._logger.exception("feature worker loop failed", exc_info=exc)
                    await asyncio.sleep(2)
        finally:
            hb_stop.set()
            hb_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await hb_task
            self._stats.running = False
            await self.close()

    async def stop(self) -> None:
        self._stop_event.set()

    async def close(self) -> None:
        await asyncio.to_thread(self._bus.close)

    async def _ensure_group(self) -> None:
        if self._stats.group_ready:
            return
        await asyncio.to_thread(
            self._bus.ensure_group,
            self._settings.feature_stream,
            self._settings.feature_group,
        )
        self._stats.group_ready = True

    async def _handle_item(self, item: ConsumedEvent) -> None:
        self._stats.consumed_events += 1
        self._stats.last_event_id = item.envelope.event_id
        if item.envelope.event_type != "candle_close":
            await self._ack(item)
            self._logger.debug(
                "feature worker ignoriert event_type=%s (nur candle_close wird persistiert)",
                item.envelope.event_type,
            )
            return
        try:
            feature_row = await self._build_feature_row(item)
            await asyncio.to_thread(self._repo.upsert_feature, feature_row)
            self._stats.db_connected = True
            self._stats.processed_events += 1
            self._stats.last_feature_symbol = feature_row.symbol
            self._stats.last_feature_market_family = feature_row.market_family
            self._stats.last_feature_timeframe = feature_row.timeframe
            self._stats.last_feature_start_ts_ms = feature_row.start_ts_ms
            self._stats.last_computed_ts_ms = feature_row.computed_ts_ms
            await self._ack(item)
            self._logger.info(
                "feature row upserted symbol=%s timeframe=%s start_ts_ms=%s source_event_id=%s",
                feature_row.symbol,
                feature_row.timeframe,
                feature_row.start_ts_ms,
                feature_row.source_event_id,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._stats.last_error = str(exc)
            if isinstance(exc, psycopg.Error):
                self._stats.db_connected = False
            await self._publish_dlq(item, exc)
            await self._ack(item)
            self._logger.warning(
                "feature worker sent event to DLQ event_id=%s error=%s",
                item.envelope.event_id,
                exc,
            )

    async def _build_feature_row(self, item: ConsumedEvent) -> CandleFeatureRow:
        event = item.envelope
        if event.event_type != "candle_close":
            raise ValueError(f"unexpected event_type for feature-engine: {event.event_type}")
        instrument = _require_event_instrument(event)
        timeframe = _extract_timeframe(event)
        start_ts_ms = _extract_start_ts_ms(event)
        symbol = instrument.symbol
        quality_issues = _validate_candle_close_event(
            event,
            max_event_age_ms=self._settings.feature_max_event_age_ms,
            now_ms=int(time.time() * 1000),
        )
        if quality_issues:
            raise ValueError(
                "candle_close data-quality gate failed: " + ", ".join(sorted(set(quality_issues)))
            )
        metadata = await asyncio.to_thread(self._resolve_metadata, instrument)
        entry = metadata.entry
        supports_funding = bool(
            entry.market_family == "futures" and entry.supports_funding
        )
        supports_open_interest = bool(
            entry.market_family == "futures" and entry.supports_open_interest
        )
        active_namespaces = feature_namespaces_for_identity(entry)
        hard_issues = list(
            validate_event_vs_resolved_metadata(instrument, entry)
        )
        hard_issues.extend(
            family_foreign_namespace_violations(
                market_family=entry.market_family,
                active_namespaces=active_namespaces,
            )
        )
        current_candle = _candle_from_event(event)
        history = await asyncio.to_thread(
            self._repo.fetch_candles,
            symbol=symbol,
            timeframe=timeframe,
            end_start_ts_ms=start_ts_ms,
            limit=self._settings.feature_lookback_candles,
        )
        self._stats.db_connected = True
        candles = _merge_candle_history(history, current_candle)
        if not candles:
            raise ValueError("keine Candle-History verfuegbar")

        ohlc = [OHLC(o=candle.o, h=candle.h, l=candle.l, c=candle.c) for candle in candles]
        opens = [candle.o for candle in candles]
        closes = [candle.c for candle in candles]
        highs = [candle.h for candle in candles]
        lows = [candle.l for candle in candles]
        volumes = [candle.usdt_vol for candle in candles]
        current = candles[-1]
        timeframe_ms = _timeframe_to_ms(timeframe)
        analysis_ts_ms = _extract_analysis_ts_ms(event, timeframe=timeframe, start_ts_ms=current.start_ts_ms)

        atr_value_raw = _num.atr_sma(
            ohlc,
            opens,
            highs,
            lows,
            closes,
            self._settings.feature_atr_window,
        )
        atrp_value_raw = atr_percent(atr_value_raw, current.c)
        rsi_value_raw = _num.rsi_sma(closes, self._settings.feature_rsi_window)
        ret_1_raw = simple_return(closes, 1)
        ret_5_raw = simple_return(closes, 5)
        ret_10_raw = simple_return(closes, 10)
        momentum_value_raw = momentum_score(ret_1_raw, ret_5_raw)
        impulse = candle_impulse(current.o, current.h, current.l, current.c)
        trend = _num.trend_snapshot(closes)
        latest_trend_dirs = await asyncio.to_thread(
            self._repo.get_latest_trend_dirs,
            symbol=symbol,
            timeframes=CONFLUENCE_TIMEFRAMES,
            canonical_instrument_id=metadata.canonical_instrument_id,
        )
        self._stats.db_connected = True
        confluence_value = confluence_score(
            latest_trend_dirs,
            current_timeframe=timeframe,
            current_trend_dir=trend.trend_dir,
        )
        orderbook_snapshot, ticker_raw, recent_tickers = await asyncio.gather(
            asyncio.to_thread(
                self._repo.fetch_orderbook_snapshot,
                symbol=symbol,
                max_ts_ms=analysis_ts_ms,
            ),
            asyncio.to_thread(
                self._repo.fetch_ticker_snapshot,
                symbol=symbol,
                max_ts_ms=analysis_ts_ms,
            ),
            asyncio.to_thread(
                self._repo.fetch_recent_ticker_snapshots,
                symbol=symbol,
                max_ts_ms=analysis_ts_ms,
                limit=12,
            ),
        )
        funding_snapshot = None
        if supports_funding:
            funding_snapshot = await asyncio.to_thread(
                self._repo.fetch_funding_snapshot,
                symbol=symbol,
                max_ts_ms=analysis_ts_ms,
            )
        open_interest_snapshot = None
        open_interest_prev = None
        if supports_open_interest:
            open_interest_snapshot, open_interest_prev = await asyncio.gather(
                asyncio.to_thread(
                    self._repo.fetch_open_interest_snapshot,
                    symbol=symbol,
                    max_ts_ms=analysis_ts_ms,
                ),
                asyncio.to_thread(
                    self._repo.fetch_open_interest_snapshot,
                    symbol=symbol,
                    max_ts_ms=max(0, analysis_ts_ms - timeframe_ms),
                ),
            )
        tick_lot_issues = gate_tick_lot_vs_metadata(
            open_=current.o,
            high=current.h,
            low=current.l,
            close=current.c,
            base_vol=current.base_vol,
            price_tick_size=entry.price_tick_size,
            quantity_step=entry.quantity_step,
        )
        hard_issues.extend(
            gate_cross_family_derivative_leak(
                market_family=entry.market_family,
                ticker_mark=ticker_raw.mark_price if ticker_raw else None,
                ticker_index=ticker_raw.index_price if ticker_raw else None,
                ticker_funding_rate=None,
                funding_snapshot_present=funding_snapshot is not None,
                open_interest_snapshot_present=open_interest_snapshot is not None,
            )
        )
        ticker_snapshot = sanitize_ticker_snapshot_for_family(
            ticker_raw,
            market_family=entry.market_family,
            supports_funding=supports_funding,
            supports_open_interest=supports_open_interest,
        )
        recent_tickers = [
            sanitize_ticker_snapshot_for_family(
                snap,
                market_family=entry.market_family,
                supports_funding=supports_funding,
                supports_open_interest=supports_open_interest,
            )
            for snap in recent_tickers
        ]
        market_context = build_market_context_features(
            market_family=metadata.entry.market_family,
            orderbook=orderbook_snapshot,
            ticker=ticker_snapshot,
            funding=funding_snapshot,
            open_interest=open_interest_snapshot,
            previous_open_interest=open_interest_prev,
            candle_usdt_vol=current.usdt_vol,
            timeframe_ms=timeframe_ms,
            analysis_ts_ms=analysis_ts_ms,
            atrp_14=_nullable(atrp_value_raw),
            supports_funding=supports_funding,
            supports_open_interest=supports_open_interest,
        )
        computed_ts_ms = int(time.time() * 1000)
        rv20 = realized_vol_std_log_returns(closes, 20)
        rv50 = realized_vol_std_log_returns(closes, 50)
        range_score_value = _nullable(
            range_score(
                closes,
                highs,
                lows,
                ema_fast=trend.ema_fast,
                ema_slow=trend.ema_slow,
            )
        )
        session_drift_bps = _session_drift_bps(candles, timeframe=timeframe)
        spread_persistence_bps = _spread_persistence_bps(recent_tickers)
        mean_reversion_pressure = _mean_reversion_pressure(
            close=current.c,
            ema_fast=_nullable(trend.ema_fast),
            atrp_14=_nullable(atrp_value_raw),
            range_score_value=range_score_value,
            orderbook_imbalance=market_context.orderbook_imbalance,
        )
        breakout_compression = _breakout_compression_score(
            range_score_value=range_score_value,
            atrp_14=_nullable(atrp_value_raw),
            depth_balance_ratio=market_context.depth_balance_ratio,
        )
        realized_vol_cluster = _realized_vol_cluster_score(rv20=rv20, rv50=rv50)
        gap_analysis = analyze_sorted_candle_starts(
            [c.start_ts_ms for c in candles],
            step_ms=timeframe_ms,
        )
        data_completeness = compute_data_completeness_0_1(
            market_family=metadata.entry.market_family,
            market_context=market_context,
            realized_vol_20=rv20,
            session_drift_bps=session_drift_bps,
            supports_funding=supports_funding,
            supports_open_interest=supports_open_interest,
        )
        staleness_score = compute_staleness_score_0_1(
            market_family=metadata.entry.market_family,
            market_context=market_context,
            timeframe_ms=timeframe_ms,
            supports_funding=supports_funding,
            supports_open_interest=supports_open_interest,
        )
        liquidation_distance_bps = _liquidation_distance_bps_max_leverage(metadata)
        event_distance_ms = _event_distance_ms(
            metadata=metadata,
            analysis_ts_ms=analysis_ts_ms,
            funding_time_to_next_ms=market_context.funding_time_to_next_ms,
        )
        feature_quality_status = _feature_quality_status(
            data_completeness=data_completeness,
            staleness_score=staleness_score,
            metadata=metadata,
            hard_issues=hard_issues,
            tick_lot_issues=tick_lot_issues,
        )
        pipeline_trade_mode = compute_pipeline_trade_mode(
            hard_issues=hard_issues,
            metadata_health_status=metadata.health_status,
            data_completeness=data_completeness,
            staleness_score=staleness_score,
            analytics_eligible=entry.analytics_eligible,
            live_execution_enabled=entry.live_execution_enabled,
            execution_disabled=entry.execution_disabled,
        )
        dq_issues = sorted(
            set(hard_issues + [f"tick_lot:{i}" for i in tick_lot_issues])
        )
        auxiliary_inputs: dict[str, object] = {
            "canonical_instrument_id": metadata.canonical_instrument_id,
            "market_family": metadata.entry.market_family,
            "product_type": metadata.entry.product_type,
            "margin_account_mode": metadata.entry.margin_account_mode,
            "instrument_metadata_snapshot_id": metadata.snapshot_id,
            "metadata_health_status": metadata.health_status,
            "metadata_health_reasons": list(metadata.health_reasons),
            "feature_namespaces": list(active_namespaces),
            "feature_namespace_bundle_version": FEATURE_NAMESPACE_BUNDLE_VERSION,
            "capability_supports_funding": entry.supports_funding,
            "capability_supports_open_interest": entry.supports_open_interest,
            "pipeline_trade_mode": pipeline_trade_mode,
            "data_quality_issues": dq_issues,
            "orderbook_present": orderbook_snapshot is not None,
            "orderbook_ts_ms": orderbook_snapshot.ts_ms if orderbook_snapshot else None,
            "ticker_ts_ms": ticker_snapshot.ts_ms if ticker_snapshot else None,
            "funding_ts_ms": funding_snapshot.ts_ms if funding_snapshot else None,
            "open_interest_ts_ms": (
                open_interest_snapshot.ts_ms if open_interest_snapshot else None
            ),
            "orderbook_age_ms": market_context.orderbook_age_ms,
            "funding_age_ms": market_context.funding_age_ms,
            "open_interest_age_ms": market_context.open_interest_age_ms,
            "data_completeness_0_1": data_completeness,
            "staleness_score_0_1": staleness_score,
            "gap_count_lookback": int(gap_analysis["gaps_ge_1_bar_count"]),
            "feature_quality_status": feature_quality_status,
            "event_distance_ms": event_distance_ms,
        }
        sorted_bar_starts = [c.start_ts_ms for c in candles]
        input_provenance = build_feature_input_provenance(
            symbol=symbol,
            timeframe=timeframe,
            sorted_bar_starts_ms=sorted_bar_starts,
            bar_close_ts_ms=current.start_ts_ms,
            max_allowed_gap_bars=self._settings.feature_max_allowed_gap_bars,
            rsi_window=self._settings.feature_rsi_window,
            atr_window=self._settings.feature_atr_window,
            vol_z_window=self._settings.feature_volz_window,
            source_event_id=event.event_id,
            computed_ts_ms=computed_ts_ms,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            feature_schema_hash=FEATURE_SCHEMA_HASH,
            analysis_ts_ms=analysis_ts_ms,
            ret_10=ret_10_raw if math.isfinite(ret_10_raw) else None,
            realized_vol_20=rv20,
            auxiliary_inputs=auxiliary_inputs,
        )
        row = CandleFeatureRow(
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            feature_schema_hash=FEATURE_SCHEMA_HASH,
            canonical_instrument_id=metadata.canonical_instrument_id,
            market_family=metadata.entry.market_family,
            product_type=metadata.entry.product_type,
            margin_account_mode=metadata.entry.margin_account_mode,
            instrument_metadata_snapshot_id=metadata.snapshot_id,
            symbol=symbol,
            timeframe=timeframe,
            start_ts_ms=current.start_ts_ms,
            atr_14=_nullable(atr_value_raw),
            atrp_14=_nullable(atrp_value_raw),
            rsi_14=_nullable(rsi_value_raw),
            ret_1=_nullable(ret_1_raw),
            ret_5=_nullable(ret_5_raw),
            momentum_score=_nullable(momentum_value_raw),
            impulse_body_ratio=_nullable(impulse.body_ratio),
            impulse_upper_wick_ratio=_nullable(impulse.upper_wick_ratio),
            impulse_lower_wick_ratio=_nullable(impulse.lower_wick_ratio),
            range_score=range_score_value,
            trend_ema_fast=_nullable(trend.ema_fast),
            trend_ema_slow=_nullable(trend.ema_slow),
            trend_slope_proxy=_nullable(trend.slope_proxy),
            trend_dir=trend.trend_dir,
            confluence_score_0_100=_nullable(confluence_value),
            vol_z_50=_nullable(volume_zscore(volumes, self._settings.feature_volz_window)),
            spread_bps=market_context.spread_bps,
            bid_depth_usdt_top25=market_context.bid_depth_usdt_top25,
            ask_depth_usdt_top25=market_context.ask_depth_usdt_top25,
            orderbook_imbalance=market_context.orderbook_imbalance,
            depth_balance_ratio=market_context.depth_balance_ratio,
            depth_to_bar_volume_ratio=market_context.depth_to_bar_volume_ratio,
            impact_buy_bps_5000=market_context.impact_buy_bps_5000,
            impact_sell_bps_5000=market_context.impact_sell_bps_5000,
            impact_buy_bps_10000=market_context.impact_buy_bps_10000,
            impact_sell_bps_10000=market_context.impact_sell_bps_10000,
            execution_cost_bps=market_context.execution_cost_bps,
            volatility_cost_bps=market_context.volatility_cost_bps,
            funding_rate=market_context.funding_rate,
            funding_rate_bps=market_context.funding_rate_bps,
            funding_cost_bps_window=market_context.funding_cost_bps_window,
            funding_time_to_next_ms=market_context.funding_time_to_next_ms,
            open_interest=market_context.open_interest,
            open_interest_change_pct=market_context.open_interest_change_pct,
            mark_index_spread_bps=market_context.mark_index_spread_bps,
            basis_bps=market_context.basis_bps,
            session_drift_bps=session_drift_bps,
            spread_persistence_bps=spread_persistence_bps,
            mean_reversion_pressure_0_100=mean_reversion_pressure,
            breakout_compression_score_0_100=breakout_compression,
            realized_vol_cluster_0_100=realized_vol_cluster,
            liquidation_distance_bps_max_leverage=liquidation_distance_bps,
            data_completeness_0_1=data_completeness,
            staleness_score_0_1=staleness_score,
            gap_count_lookback=int(gap_analysis["gaps_ge_1_bar_count"]),
            event_distance_ms=event_distance_ms,
            feature_quality_status=feature_quality_status,
            orderbook_age_ms=market_context.orderbook_age_ms,
            funding_age_ms=market_context.funding_age_ms,
            open_interest_age_ms=market_context.open_interest_age_ms,
            liquidity_source=market_context.liquidity_source,
            funding_source=market_context.funding_source,
            open_interest_source=market_context.open_interest_source,
            source_event_id=event.event_id,
            computed_ts_ms=computed_ts_ms,
            input_provenance=input_provenance,
        )
        return row

    def _resolve_metadata(
        self,
        instrument: BitgetInstrumentIdentity,
    ) -> BitgetInstrumentResolvedMetadata:
        try:
            return self._metadata_service.resolve_metadata(
                symbol=instrument.symbol,
                market_family=instrument.market_family,
                product_type=instrument.product_type,
                margin_account_mode=instrument.margin_account_mode,
                refresh_if_missing=False,
            )
        except (InstrumentCatalogUnavailableError, UnknownInstrumentError) as exc:
            raise ValueError(f"feature_metadata_unavailable: {exc}") from exc

    async def _publish_dlq(self, item: ConsumedEvent, exc: Exception) -> None:
        await asyncio.to_thread(
            self._bus.publish_dlq,
            item.envelope,
            {
                "stage": "feature_worker",
                "error": str(exc),
            },
        )
        self._stats.dlq_events += 1

    async def _ack(self, item: ConsumedEvent) -> None:
        await asyncio.to_thread(
            self._bus.ack,
            item.stream,
            self._settings.feature_group,
            item.message_id,
        )


def _extract_timeframe(event: object) -> str:
    if not hasattr(event, "timeframe"):
        raise ValueError("event ohne timeframe")
    timeframe = event.timeframe
    if isinstance(timeframe, str) and timeframe.strip():
        return normalize_model_timeframe(timeframe.strip())
    payload = getattr(event, "payload", {})
    if isinstance(payload, dict):
        raw = payload.get("timeframe")
        if raw is not None and str(raw).strip():
            return normalize_model_timeframe(str(raw).strip())
    raise ValueError("candle_close event ohne timeframe")


def _extract_start_ts_ms(event: object) -> int:
    payload = getattr(event, "payload", {})
    if not isinstance(payload, dict):
        raise ValueError("event payload fehlt")
    raw = payload.get("start_ts_ms")
    if raw is None:
        raise ValueError("candle_close payload ohne start_ts_ms")
    return int(str(raw))


def _extract_analysis_ts_ms(event: object, *, timeframe: str, start_ts_ms: int) -> int:
    exchange_ts_ms = int(getattr(event, "exchange_ts_ms", 0) or 0)
    if exchange_ts_ms > 0:
        return exchange_ts_ms
    return start_ts_ms + _timeframe_to_ms(timeframe)


def _candle_from_event(event: object) -> StoredCandle:
    payload = getattr(event, "payload", {})
    if not isinstance(payload, dict):
        raise ValueError("event payload fehlt")
    timeframe = _extract_timeframe(event)
    instrument = getattr(event, "instrument", None)
    symbol = str(getattr(instrument, "symbol", None) or event.symbol)
    return StoredCandle(
        symbol=symbol,
        timeframe=timeframe,
        start_ts_ms=_extract_start_ts_ms(event),
        o=float(payload["open"]),
        h=float(payload["high"]),
        l=float(payload["low"]),
        c=float(payload["close"]),
        base_vol=float(payload["base_vol"]),
        quote_vol=float(payload["quote_vol"]),
        usdt_vol=float(payload["usdt_vol"]),
    )


def _validate_candle_close_event(
    event: object,
    *,
    max_event_age_ms: int,
    now_ms: int,
) -> list[str]:
    issues: list[str] = []
    payload = getattr(event, "payload", {})
    if not isinstance(payload, dict):
        return ["payload_missing"]

    symbol = str(getattr(event, "symbol", "") or "").strip().upper()
    if not symbol:
        issues.append("symbol_missing")
    instrument = getattr(event, "instrument", None)
    if instrument is None:
        issues.append("instrument_missing")
    else:
        instrument_symbol = str(getattr(instrument, "symbol", "") or "").strip().upper()
        if not instrument_symbol:
            issues.append("instrument_symbol_missing")
        elif symbol and instrument_symbol != symbol:
            issues.append("instrument_symbol_mismatch")
        market_family = str(getattr(instrument, "market_family", "") or "").strip().lower()
        if market_family not in {"spot", "margin", "futures"}:
            issues.append("instrument_market_family_invalid")

    timeframe = _extract_timeframe(event)
    if timeframe not in MODEL_TIMEFRAMES:
        issues.append("timeframe_invalid")

    start_ts_ms = _extract_start_ts_ms(event)
    if start_ts_ms <= 0:
        issues.append("start_ts_invalid")

    ingest_ts_ms = int(getattr(event, "ingest_ts_ms", 0) or 0)
    if ingest_ts_ms <= 0:
        issues.append("ingest_ts_missing")
    elif now_ms - ingest_ts_ms > max_event_age_ms:
        issues.append("stale_market_event")
    exchange_ts_ms = int(getattr(event, "exchange_ts_ms", 0) or 0)
    timeframe_ms = _timeframe_to_ms(timeframe)
    if exchange_ts_ms > 0 and exchange_ts_ms < start_ts_ms + timeframe_ms:
        issues.append("exchange_ts_before_candle_close")

    required_prices = {}
    for key in ("open", "high", "low", "close"):
        try:
            required_prices[key] = float(payload[key])
        except (KeyError, TypeError, ValueError):
            issues.append(f"{key}_invalid")
            continue
        if not math.isfinite(required_prices[key]) or required_prices[key] <= 0:
            issues.append(f"{key}_invalid")

    if {"open", "high", "low", "close"} <= required_prices.keys():
        if required_prices["high"] < max(
            required_prices["open"],
            required_prices["close"],
            required_prices["low"],
        ):
            issues.append("high_below_body")
        if required_prices["low"] > min(
            required_prices["open"],
            required_prices["close"],
            required_prices["high"],
        ):
            issues.append("low_above_body")

    for key in ("base_vol", "quote_vol", "usdt_vol"):
        try:
            value = float(payload[key])
        except (KeyError, TypeError, ValueError):
            issues.append(f"{key}_invalid")
            continue
        if not math.isfinite(value) or value < 0:
            issues.append(f"{key}_invalid")

    return sorted(set(issues))


def _merge_candle_history(
    history: list[StoredCandle],
    current_candle: StoredCandle,
) -> list[StoredCandle]:
    merged: dict[int, StoredCandle] = {candle.start_ts_ms: candle for candle in history}
    merged[current_candle.start_ts_ms] = current_candle
    return [merged[key] for key in sorted(merged)]


def _require_event_instrument(event: object) -> BitgetInstrumentIdentity:
    instrument = getattr(event, "instrument", None)
    if not isinstance(instrument, BitgetInstrumentIdentity):
        raise ValueError("candle_close event ohne instrument identity")
    return instrument


def _session_drift_bps(candles: list[StoredCandle], *, timeframe: str) -> float | None:
    if not candles:
        return None
    horizon = {
        "1m": 240,
        "5m": 200,
        "15m": 96,
        "1H": 24,
        "4H": 6,
    }.get(timeframe, len(candles))
    window = candles[-min(len(candles), horizon) :]
    anchor = window[0].o if window[0].o > 0 else window[0].c
    if anchor <= 0:
        return None
    return ((window[-1].c - anchor) / anchor) * 10_000.0


def _spread_persistence_bps(tickers: list[TickerSnapshot]) -> float | None:
    spreads: list[float] = []
    for snapshot in tickers:
        if (
            snapshot.bid_pr is None
            or snapshot.ask_pr is None
            or snapshot.bid_pr <= 0
            or snapshot.ask_pr <= 0
            or snapshot.ask_pr < snapshot.bid_pr
        ):
            continue
        mid = (snapshot.bid_pr + snapshot.ask_pr) / 2.0
        if mid <= 0:
            continue
        spreads.append(((snapshot.ask_pr - snapshot.bid_pr) / mid) * 10_000.0)
    if not spreads:
        return None
    return sum(spreads) / len(spreads)


def _mean_reversion_pressure(
    *,
    close: float,
    ema_fast: float | None,
    atrp_14: float | None,
    range_score_value: float | None,
    orderbook_imbalance: float | None,
) -> float | None:
    if close <= 0 or ema_fast is None:
        return None
    deviation_bps = abs((close - ema_fast) / close) * 10_000.0
    atrp_bps = max((atrp_14 or 0.0) * 100.0, 20.0)
    deviation_score = min(100.0, (deviation_bps / atrp_bps) * 100.0)
    compression = max(0.0, min(range_score_value if range_score_value is not None else 50.0, 100.0))
    imbalance = max(-1.0, min(1.0, orderbook_imbalance or 0.0))
    counterflow = max(0.0, -imbalance if close >= ema_fast else imbalance) * 100.0
    return max(0.0, min(100.0, deviation_score * 0.45 + compression * 0.35 + counterflow * 0.20))


def _breakout_compression_score(
    *,
    range_score_value: float | None,
    atrp_14: float | None,
    depth_balance_ratio: float | None,
) -> float | None:
    if range_score_value is None and atrp_14 is None and depth_balance_ratio is None:
        return None
    compression = max(0.0, min(range_score_value if range_score_value is not None else 50.0, 100.0))
    atrp_score = 50.0 if atrp_14 is None else max(0.0, min(100.0, 100.0 - (atrp_14 * 200.0)))
    depth_score = 50.0 if depth_balance_ratio is None else max(0.0, min(depth_balance_ratio * 100.0, 100.0))
    return max(0.0, min(100.0, compression * 0.55 + atrp_score * 0.25 + depth_score * 0.20))


def _realized_vol_cluster_score(*, rv20: float | None, rv50: float | None) -> float | None:
    if rv20 is None or rv50 is None or rv50 <= 0:
        return None
    ratio = rv20 / rv50
    bounded = max(0.5, min(2.0, ratio))
    return ((bounded - 0.5) / 1.5) * 100.0


def _liquidation_distance_bps_max_leverage(
    metadata: BitgetInstrumentResolvedMetadata,
) -> float | None:
    leverage_max = metadata.entry.leverage_max
    if metadata.entry.market_family != "futures" or leverage_max is None or leverage_max <= 0:
        return None
    return (10_000.0 / float(leverage_max)) * 0.8


def _event_distance_ms(
    *,
    metadata: BitgetInstrumentResolvedMetadata,
    analysis_ts_ms: int,
    funding_time_to_next_ms: int | None,
) -> int | None:
    candidates: list[int] = []
    if funding_time_to_next_ms is not None:
        candidates.append(funding_time_to_next_ms)
    session_meta = dict(metadata.entry.session_metadata or {})
    for key in ("maintain_time", "delivery_start_time", "delivery_time"):
        value = session_meta.get(key)
        if isinstance(value, int) and value > analysis_ts_ms:
            candidates.append(value - analysis_ts_ms)
    if not candidates:
        return None
    return min(candidates)


def _feature_quality_status(
    *,
    data_completeness: float,
    staleness_score: float,
    metadata: BitgetInstrumentResolvedMetadata,
    hard_issues: list[str],
    tick_lot_issues: list[str],
) -> str:
    if hard_issues or tick_lot_issues:
        return "degraded"
    if data_completeness >= 0.85 and staleness_score <= 0.5 and metadata.health_status == "ok":
        return "ok"
    return "degraded"


def _nullable(value: float) -> float | None:
    if math.isnan(value) or math.isinf(value):
        return None
    return float(value)


def _timeframe_to_ms(timeframe: str) -> int:
    try:
        return TIMEFRAME_TO_MS[timeframe]
    except KeyError as exc:
        raise ValueError(f"unsupported timeframe: {timeframe}") from exc
