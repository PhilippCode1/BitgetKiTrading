from __future__ import annotations

# ruff: noqa: E402, I001 — Bootstrap-Reihenfolge / Import-Blocks
import logging
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from paper_broker.api.routes_accounts import build_accounts_router
from paper_broker.api.routes_health import build_health_router
from paper_broker.api.routes_plans import build_plans_router
from paper_broker.api.routes_positions import build_positions_router
from paper_broker.api.routes_sim import build_sim_router
from paper_broker.api.routes_strategy import build_strategy_router
from paper_broker.config import PaperBrokerSettings
from paper_broker.engine.broker import PaperBrokerService
from paper_broker.strategy.engine import StrategyExecutionEngine
from paper_broker.worker.consumer import run_consumer_loop
from shared_py.bitget import (
    BitgetInstrumentCatalog,
    BitgetInstrumentMetadataService,
    BitgetSettings,
)
from shared_py.eventbus import RedisStreamBus
from shared_py.observability import instrument_fastapi


def _ensure_paths() -> None:
    root = Path(__file__).resolve().parents[4]
    sp = root / "shared" / "python" / "src"
    for p in (root, sp):
        if p.is_dir():
            s = str(p)
            if s not in sys.path:
                sys.path.insert(0, s)


_ensure_paths()


class PaperRuntime:
    def __init__(self, settings: PaperBrokerSettings) -> None:
        self.settings = settings
        self.bus = RedisStreamBus.from_url(
            settings.redis_url,
            dedupe_ttl_sec=settings.eventbus_dedupe_ttl_sec,
        )
        self.catalog = BitgetInstrumentCatalog(
            bitget_settings=BitgetSettings(),
            database_url=settings.database_url,
            redis_url=settings.redis_url,
            source_service="paper-broker",
            cache_ttl_sec=settings.instrument_catalog_cache_ttl_sec,
            max_stale_sec=settings.instrument_catalog_max_stale_sec,
        )
        self.metadata_service = BitgetInstrumentMetadataService(self.catalog)
        self.catalog_block_reason: str | None = None
        self.broker = PaperBrokerService(settings=settings, bus=self.bus, catalog=self.catalog)
        self.strategy_engine = StrategyExecutionEngine(settings, self.broker)
        self.broker.strategy_engine = self.strategy_engine
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def refresh_catalog(self) -> None:
        try:
            self.catalog.refresh_catalog(refresh_reason="startup")
            self.metadata_service.resolve_metadata(
                symbol=self.settings.paper_default_symbol,
                market_family=self.settings.bitget_market_family,
                product_type=(
                    self.settings.bitget_product_type
                    if self.settings.bitget_market_family == "futures"
                    else None
                ),
                margin_account_mode=(
                    self.settings.bitget_margin_account_mode
                    if self.settings.bitget_market_family == "margin"
                    else None
                ),
                refresh_if_missing=False,
            )
            self.catalog_block_reason = None
        except Exception as exc:
            self.catalog_block_reason = str(exc)
            logging.getLogger("paper_broker").warning("instrument catalog refresh failed: %s", exc)

    def start_background(self) -> None:
        need_consumer = (
            not self.settings.paper_sim_mode
            or self.settings.strategy_exec_enabled
            or self.settings.strategy_registry_enabled
        )
        if not need_consumer:
            logging.getLogger("paper_broker").info(
                "PAPER_SIM_MODE=true — Redis-Consumer deaktiviert "
                "(STRATEGY_EXEC_ENABLED=false, STRATEGY_REGISTRY_ENABLED=false)"
            )
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=run_consumer_loop,
            args=(
                self.settings,
                self.broker,
                self.bus,
                self._stop,
                self.strategy_engine,
            ),
            name="paper-broker-consumer",
            daemon=True,
        )
        self._thread.start()

    def stop_background(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None


def create_app() -> FastAPI:
    from config.bootstrap import bootstrap_from_settings

    settings = PaperBrokerSettings()
    bootstrap_from_settings("paper-broker", settings)
    runtime = PaperRuntime(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runtime = runtime
        runtime.refresh_catalog()
        runtime.start_background()
        try:
            yield
        finally:
            runtime.stop_background()

    app = FastAPI(
        title="paper-broker",
        version="0.1.0",
        description="Paper broker for catalog-backed Bitget market families.",
        lifespan=lifespan,
    )
    app.include_router(build_health_router(runtime))
    app.include_router(build_accounts_router(runtime.broker, settings))
    app.include_router(build_positions_router(runtime.broker, settings))
    app.include_router(build_plans_router(runtime.broker))
    app.include_router(build_strategy_router(settings, runtime.strategy_engine))
    app.include_router(build_sim_router(runtime.broker))
    instrument_fastapi(app, "paper-broker")
    return app


app = create_app()
