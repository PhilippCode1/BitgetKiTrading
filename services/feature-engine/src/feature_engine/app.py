from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import ClassVar

import psycopg
from fastapi import FastAPI, HTTPException, Query
from pydantic import Field, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from config.settings import BaseServiceSettings
from feature_engine.correlation_worker import CorrelationGraphWorker
from feature_engine.storage import FeatureRepository
from feature_engine.tsfm_pipeline import TsfmPatchConsumer
from feature_engine.worker import FeatureWorker
from shared_py.bitget.catalog import BitgetInstrumentCatalog
from shared_py.bitget.config import BitgetSettings
from shared_py.bitget.metadata import BitgetInstrumentMetadataService
from shared_py.eventbus import (
    STREAM_CANDLE_CLOSE,
    STREAM_MARKET_TICK,
    STREAM_STRUCTURE_UPDATED,
)
from shared_py.observability import (
    append_peer_readiness_checks,
    check_postgres,
    check_redis_url,
    instrument_fastapi,
    merge_ready_details,
)

class FeatureEngineSettings(BaseServiceSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        populate_by_name=True,
    )
    production_required_fields: ClassVar[tuple[str, ...]] = (
        BaseServiceSettings.production_required_fields + ("database_url", "redis_url")
    )
    production_required_non_local_fields: ClassVar[tuple[str, ...]] = (
        BaseServiceSettings.production_required_non_local_fields
        + ("database_url", "redis_url")
    )

    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")
    feature_engine_port: int = Field(default=8020, alias="FEATURE_ENGINE_PORT")
    feature_stream: str = Field(default=STREAM_CANDLE_CLOSE, alias="FEATURE_STREAM")
    feature_group: str = Field(default="feature-engine", alias="FEATURE_GROUP")
    feature_consumer: str = Field(default="fe-1", alias="FEATURE_CONSUMER")
    feature_lookback_candles: int = Field(default=200, alias="FEATURE_LOOKBACK_CANDLES")
    feature_atr_window: int = Field(default=14, alias="FEATURE_ATR_WINDOW")
    feature_rsi_window: int = Field(default=14, alias="FEATURE_RSI_WINDOW")
    feature_volz_window: int = Field(default=50, alias="FEATURE_VOLZ_WINDOW")
    feature_max_event_age_ms: int = Field(default=120_000, alias="FEATURE_MAX_EVENT_AGE_MS")
    feature_max_allowed_gap_bars: int = Field(default=3, alias="FEATURE_MAX_ALLOWED_GAP_BARS")
    eventbus_default_block_ms: int = Field(default=2000, alias="EVENTBUS_DEFAULT_BLOCK_MS")
    eventbus_default_count: int = Field(default=50, alias="EVENTBUS_DEFAULT_COUNT")
    eventbus_dedupe_ttl_sec: int = Field(default=86400, alias="EVENTBUS_DEDUPE_TTL_SEC")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    tsfm_patch_pipeline_enabled: bool = Field(
        default=False, alias="FEATURE_TSFM_PATCH_PIPELINE_ENABLED"
    )
    tsfm_inference_grpc_target: str = Field(
        default="inference-server:50051",
        alias="FEATURE_TSFM_INFERENCE_GRPC_TARGET",
    )
    tsfm_model_id: str = Field(
        default="google/timesfm-1.0-200m",
        alias="FEATURE_TSFM_MODEL_ID",
    )
    tsfm_tick_stride: int = Field(default=10, ge=1, le=50_000, alias="FEATURE_TSFM_TICK_STRIDE")
    tsfm_context_len: int = Field(
        default=1024,
        ge=128,
        le=8192,
        alias="FEATURE_TSFM_CONTEXT_LEN",
    )
    tsfm_forecast_horizon: int = Field(
        default=64,
        ge=8,
        le=512,
        alias="FEATURE_TSFM_FORECAST_HORIZON",
    )
    tsfm_max_tick_gap_ms: int = Field(
        default=10_000,
        ge=50,
        alias="FEATURE_TSFM_MAX_TICK_GAP_MS",
    )
    tsfm_rolling_z_window: int = Field(
        default=256,
        ge=8,
        alias="FEATURE_TSFM_ROLLING_Z_WINDOW",
    )
    tsfm_online_drift_min_rank_to_block: int = Field(
        default=2,
        ge=0,
        le=4,
        alias="FEATURE_TSFM_ONLINE_DRIFT_MIN_RANK_TO_BLOCK",
        description=(
            "0=kein DB-Block; >=2 blockt shadow_only und hard_block "
            "(siehe shared_py.online_drift.action_rank)."
        ),
    )
    tsfm_use_numba: bool = Field(default=True, alias="FEATURE_TSFM_USE_NUMBA")
    tsfm_prepare_budget_ms: float = Field(
        default=5.0,
        gt=0.0,
        alias="FEATURE_TSFM_PREPARE_BUDGET_MS",
    )
    tsfm_tick_stream: str = Field(default=STREAM_MARKET_TICK, alias="FEATURE_TSFM_TICK_STREAM")
    tsfm_tick_group: str = Field(default="feature-engine-tsfm", alias="FEATURE_TSFM_TICK_GROUP")
    tsfm_tick_consumer: str = Field(default="fe-tsfm-1", alias="FEATURE_TSFM_TICK_CONSUMER")

    correlation_graph_enabled: bool = Field(default=False, alias="CORRELATION_GRAPH_ENABLED")
    correlation_publish_interval_sec: int = Field(
        default=60,
        ge=15,
        le=86_400,
        alias="CORRELATION_PUBLISH_INTERVAL_SEC",
    )

    @field_validator("feature_engine_port")
    @classmethod
    def _validate_port(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("FEATURE_ENGINE_PORT muss zwischen 1 und 65535 liegen")
        return value

    @field_validator(
        "feature_lookback_candles",
        "feature_atr_window",
        "feature_rsi_window",
        "feature_volz_window",
        "feature_max_allowed_gap_bars",
        "feature_max_event_age_ms",
        "eventbus_default_block_ms",
        "eventbus_default_count",
    )
    @classmethod
    def _validate_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Feature- und Eventbus-Werte muessen > 0 sein")
        return value

    @field_validator("eventbus_dedupe_ttl_sec")
    @classmethod
    def _validate_non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("EVENTBUS_DEDUPE_TTL_SEC darf nicht negativ sein")
        return value

    @field_validator("feature_stream")
    @classmethod
    def _validate_stream(cls, value: str) -> str:
        normalized = value.strip()
        if normalized not in (STREAM_CANDLE_CLOSE, STREAM_MARKET_TICK):
            raise ValueError(
                "FEATURE_STREAM muss events:candle_close oder events:market_tick sein "
                "(market_tick fuer USE_SHARED_MEMORY / Tick-Pfad)"
            )
        return normalized

    @field_validator("feature_group", "feature_consumer", mode="before")
    @classmethod
    def _validate_names(cls, value: object) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("Feature Worker Namen duerfen nicht leer sein")
        return normalized

    @field_validator("tsfm_tick_group", "tsfm_tick_consumer", mode="before")
    @classmethod
    def _validate_tsfm_names(cls, value: object) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("TSFM Consumer/Group duerfen nicht leer sein")
        return normalized

    @field_validator("tsfm_tick_stream")
    @classmethod
    def _validate_tsfm_stream(cls, value: str) -> str:
        normalized = value.strip()
        if normalized != STREAM_MARKET_TICK:
            raise ValueError("FEATURE_TSFM_TICK_STREAM muss events:market_tick sein")
        return normalized

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> str:
        if value is None:
            return "INFO"
        return str(value).strip().upper() or "INFO"

    @model_validator(mode="after")
    def _validate_windows(self) -> "FeatureEngineSettings":
        if self.feature_atr_window != 14:
            raise ValueError("FEATURE_ATR_WINDOW muss fuer die persistierte Spalte atr_14 aktuell 14 sein")
        if self.feature_rsi_window != 14:
            raise ValueError("FEATURE_RSI_WINDOW muss fuer die persistierte Spalte rsi_14 aktuell 14 sein")
        if self.feature_volz_window != 50:
            raise ValueError("FEATURE_VOLZ_WINDOW muss fuer die persistierte Spalte vol_z_50 aktuell 50 sein")
        minimum_lookback = max(
            self.feature_atr_window + 1,
            self.feature_rsi_window + 1,
            self.feature_volz_window + 1,
            30,
        )
        if self.feature_lookback_candles < minimum_lookback:
            raise ValueError(
                f"FEATURE_LOOKBACK_CANDLES muss mindestens {minimum_lookback} sein"
            )
        return self


class FeatureEngineRuntime:
    def __init__(self, settings: FeatureEngineSettings) -> None:
        self._logger = logging.getLogger("feature_engine")
        self._settings = settings
        self._repo = FeatureRepository(settings.database_url, logger=self._logger)
        bitget_settings = BitgetSettings()
        self._catalog = BitgetInstrumentCatalog(
            bitget_settings=bitget_settings,
            database_url=settings.database_url,
            redis_url=settings.redis_url,
            source_service="feature-engine",
            cache_ttl_sec=settings.instrument_catalog_cache_ttl_sec,
            max_stale_sec=settings.instrument_catalog_max_stale_sec,
        )
        self._metadata_service = BitgetInstrumentMetadataService(self._catalog)
        self._worker = FeatureWorker(
            settings,
            self._repo,
            self._metadata_service,
            logger=self._logger,
        )
        self._worker_task: asyncio.Task[None] | None = None
        self._tsfm: TsfmPatchConsumer | None = None
        self._tsfm_task: asyncio.Task[None] | None = None
        self._correlation_snapshot: dict[str, object] | None = None
        self._correlation_worker = CorrelationGraphWorker(
            settings,
            on_snapshot=self._set_correlation_snapshot,
            logger_=self._logger,
        )

    def _set_correlation_snapshot(self, snap: dict[str, object]) -> None:
        self._correlation_snapshot = snap

    @property
    def repo(self) -> FeatureRepository:
        return self._repo

    async def start(self) -> None:
        self._worker_task = asyncio.create_task(
            self._worker.run(),
            name="feature-engine-worker",
        )
        self._worker_task.add_done_callback(self._on_worker_done)
        await self._correlation_worker.start_background()
        if self._settings.tsfm_patch_pipeline_enabled:
            self._tsfm = TsfmPatchConsumer(self._settings, logger=self._logger)
            self._tsfm_task = asyncio.create_task(
                self._tsfm.run(),
                name="feature-engine-tsfm",
            )
            self._tsfm_task.add_done_callback(self._on_tsfm_done)
        self._logger.info(
            "feature-engine runtime started on port %s stream=%s group=%s consumer=%s tsfm=%s",
            self._settings.feature_engine_port,
            self._settings.feature_stream,
            self._settings.feature_group,
            self._settings.feature_consumer,
            bool(self._settings.tsfm_patch_pipeline_enabled),
        )

    async def stop(self) -> None:
        await self._correlation_worker.stop()
        if self._tsfm is not None:
            await self._tsfm.stop()
        if self._tsfm_task is not None:
            await asyncio.gather(self._tsfm_task, return_exceptions=True)
            self._tsfm_task = None
            self._tsfm = None
        await self._worker.stop()
        if self._worker_task is not None:
            await asyncio.gather(self._worker_task, return_exceptions=True)
        self._logger.info("feature-engine runtime stopped")

    def health_payload(self) -> dict[str, object]:
        return {
            "status": "ok",
            "service": "feature-engine",
            "port": self._settings.feature_engine_port,
            "instrument_catalog": self._catalog.health_payload(),
            "pipeline_expectations": {
                "ingress_stream": self._settings.feature_stream,
                "consumer_group": self._settings.feature_group,
                "writes_table": "features.candle_features",
                "reads_tables": ["tsdb.candles", "tsdb.ticker", "tsdb.orderbook_levels"],
                "upstream_services": ["market-stream"],
                "note_de": (
                    "Ohne Redis oder ohne Eintraege in `events:candle_close` bleibt die Tabelle leer; "
                    "DLQ/last_error zeigen Qualitaets- oder DB-Fehler."
                ),
                "downstream_streams_note": (
                    f"Weitere Consumer auf `{STREAM_CANDLE_CLOSE}` (z. B. structure-engine); "
                    f"Struktur publiziert `{STREAM_STRUCTURE_UPDATED}`."
                ),
            },
            "tsfm_patch_pipeline": {
                "enabled": bool(self._settings.tsfm_patch_pipeline_enabled),
                "running": bool(
                    self._tsfm_task is not None and not self._tsfm_task.done()
                ),
                "grpc_target": self._settings.tsfm_inference_grpc_target,
                "tick_stride": self._settings.tsfm_tick_stride,
                "context_len": self._settings.tsfm_context_len,
            },
            **self._worker.stats_payload(),
            **self._correlation_worker.stats_payload(),
        }

    def _on_worker_done(self, task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            return
        except Exception as exc:  # pragma: no cover - callback logging path
            self._logger.exception("feature worker crashed", exc_info=exc)

    def _on_tsfm_done(self, task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            return
        except Exception as exc:  # pragma: no cover - callback logging path
            self._logger.exception("tsfm patch consumer crashed", exc_info=exc)


def create_app() -> FastAPI:
    from config.bootstrap import bootstrap_from_settings

    settings = FeatureEngineSettings()
    bootstrap_from_settings("feature-engine", settings)
    runtime = FeatureEngineRuntime(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runtime = runtime
        await runtime.start()
        try:
            yield
        finally:
            await runtime.stop()

    app = FastAPI(
        title="feature-engine",
        version="0.1.0",
        description="Candle feature worker and query API.",
        lifespan=lifespan,
    )

    @app.get("/health")
    def health() -> dict[str, object]:
        return runtime.health_payload()

    @app.get("/features/latest")
    def features_latest(
        symbol: str = Query(...),
        timeframe: str = Query(...),
        canonical_instrument_id: str | None = Query(default=None),
        market_family: str | None = Query(default=None),
    ) -> dict[str, object]:
        try:
            row = runtime.repo.get_latest_feature(
                symbol=symbol,
                timeframe=timeframe,
                canonical_instrument_id=canonical_instrument_id,
                market_family=market_family,
            )
        except psycopg.Error as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "error",
                    "message": f"feature lookup failed: {exc}",
                },
            ) from exc
        if row is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "status": "error",
                    "message": "feature row nicht gefunden",
                },
            )
        return {"status": "ok", "feature": row}

    @app.get("/correlation/matrix")
    def correlation_matrix() -> dict[str, object]:
        """Letzte Apex-Korrelationsmatrix (JSON fuer Dashboard / MARL)."""
        snap = runtime._correlation_snapshot
        if snap is None:
            return {
                "status": "stale",
                "message": "Noch keine Berechnung; Worker aktivieren oder warten.",
                "correlation": None,
            }
        return {"status": "ok", "correlation": snap}

    @app.get("/features/at")
    def feature_at(
        symbol: str = Query(...),
        timeframe: str = Query(...),
        start_ts_ms: int = Query(..., ge=0),
        canonical_instrument_id: str | None = Query(default=None),
        market_family: str | None = Query(default=None),
    ) -> dict[str, object]:
        try:
            row = runtime.repo.get_feature_at(
                symbol=symbol,
                timeframe=timeframe,
                start_ts_ms=start_ts_ms,
                canonical_instrument_id=canonical_instrument_id,
                market_family=market_family,
            )
        except psycopg.Error as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "error",
                    "message": f"feature lookup failed: {exc}",
                },
            ) from exc
        if row is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "status": "error",
                    "message": "feature row nicht gefunden",
                },
            )
        return {"status": "ok", "feature": row}

    @app.get("/ready")
    def ready() -> dict[str, object]:
        parts = {
            "postgres": check_postgres(settings.database_url),
            "redis": check_redis_url(settings.redis_url),
        }
        parts = append_peer_readiness_checks(
            parts,
            settings.readiness_require_urls_raw,
            timeout_sec=float(settings.readiness_peer_timeout_sec),
        )
        ok, details = merge_ready_details(parts)
        return {"ready": ok, "checks": details}

    instrument_fastapi(app, "feature-engine")
    return app


app = create_app()
