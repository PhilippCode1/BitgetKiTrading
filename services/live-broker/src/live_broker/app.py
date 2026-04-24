from __future__ import annotations

# ruff: noqa: E402, I001 - Bootstrap-Reihenfolge / Monorepo-Pfade
import logging
import os
import queue
import sys
import threading
import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI


def _ensure_paths() -> None:
    root = Path(__file__).resolve().parents[4]
    shared_src = root / "shared" / "python" / "src"
    for candidate in (root, shared_src):
        if candidate.is_dir():
            value = str(candidate)
            if value not in sys.path:
                sys.path.insert(0, value)


_ensure_paths()

from live_broker.api import build_health_router, build_ops_router
from live_broker.commercial_permissions import commercial_runtime_payload
from live_broker.config import LiveBrokerSettings
from live_broker.control_plane.service import BitgetControlPlaneService
from live_broker.exchange_client import BitgetExchangeClient
from live_broker.execution.service import LiveExecutionService
from live_broker.exits.service import LiveExitService
from live_broker.global_halt_latch import GlobalHaltLatch
from live_broker.orders.service import LiveBrokerOrderService
from live_broker.persistence.repo import LiveBrokerRepository
from live_broker.private_rest import BitgetPrivateRestClient, BitgetRestError
from live_broker.private_ws import BitgetPrivateWsClient, PrivateWsClientStats, NormalizedPrivateEvent
from live_broker.private_ws.sync import ExchangeStateSyncService
from live_broker.reconcile.service import LiveReconcileService
from live_broker.safety_oracle_bootstrap import (
    join_runtime_safety_oracle_thread,
    start_runtime_safety_oracle_thread,
)
from live_broker.worker import LiveBrokerWorker
from shared_py.bitget import BitgetInstrumentCatalog, BitgetInstrumentMetadataService
from shared_py.resilience import merge_survival_truth
from shared_py.eventbus import RedisStreamBus
from shared_py.observability import (
    append_peer_readiness_checks,
    check_postgres,
    check_redis_url,
    instrument_fastapi,
    merge_ready_details,
)

logger = logging.getLogger("live_broker.app")


class LiveBrokerRuntime:
    def __init__(self, settings: LiveBrokerSettings) -> None:
        self.settings = settings
        self._strategy_config_guard_failed = False
        self.bus = RedisStreamBus.from_url(
            settings.redis_url,
            dedupe_ttl_sec=settings.eventbus_dedupe_ttl_sec,
        )
        self.catalog = BitgetInstrumentCatalog(
            bitget_settings=settings,
            database_url=settings.database_url,
            redis_url=settings.redis_url,
            source_service="live-broker",
            cache_ttl_sec=settings.instrument_catalog_cache_ttl_sec,
            max_stale_sec=settings.instrument_catalog_max_stale_sec,
        )
        self.metadata_service = BitgetInstrumentMetadataService(self.catalog)
        self.catalog_entry = None
        self.catalog_block_reason: str | None = None
        self.repo = LiveBrokerRepository(settings.database_url)
        self.exchange_client = BitgetExchangeClient(settings)
        self.private_rest_client = BitgetPrivateRestClient(settings)
        self.global_halt = GlobalHaltLatch(settings.redis_url)
        self.order_service = LiveBrokerOrderService(
            settings,
            self.repo,
            self.private_rest_client,
            bus=self.bus,
            catalog=self.catalog,
            metadata_service=self.metadata_service,
            global_halt=self.global_halt,
        )
        self.exit_service = LiveExitService(
            settings,
            self.repo,
            self.exchange_client,
            self.order_service,
        )
        self.order_service.set_exit_service(self.exit_service)
        self.order_service.set_exchange_client(self.exchange_client)
        self.execution_service = LiveExecutionService(
            settings,
            self.exchange_client,
            self.repo,
            catalog=self.catalog,
            metadata_service=self.metadata_service,
        )
        self.execution_service.set_event_bus(self.bus)
        self.exit_service.set_event_bus(self.bus)
        self.reconcile_service = LiveReconcileService(
            settings,
            self.exchange_client,
            self.repo,
            bus=self.bus,
            private_rest=self.private_rest_client,
        )
        self.control_plane = BitgetControlPlaneService(
            settings,
            self.private_rest_client,
            self.repo,
        )
        self.exchange_state_sync = ExchangeStateSyncService(
            settings,
            self.repo,
        )
        self._last_rest_catchup_ts_ms: int = 0
        self.catchup_queue: queue.Queue[str] = queue.Queue(maxsize=8)
        self.ws_queue: queue.Queue[NormalizedPrivateEvent] = queue.Queue()
        self.ws_stats = PrivateWsClientStats()
        self.worker = LiveBrokerWorker(
            settings,
            self.bus,
            self.repo,
            self.execution_service,
            self.order_service,
            self.exit_service,
            self.reconcile_service,
            self.exchange_state_sync,
            ws_queue=self.ws_queue,
            catchup_queue=self.catchup_queue,
            private_rest=self.private_rest_client,
            on_rest_catchup_success=self._touch_rest_catchup_ts,
            private_ws_stats=self.ws_stats,
        )
        self.ws_client = BitgetPrivateWsClient(
            bitget_settings=settings,
            stats=self.ws_stats,
            message_handlers=[self._handle_ws_message],
            connected_callbacks=[self._on_private_ws_connected],
            on_stale_recover=self._enqueue_private_ws_stale_catchup,
        )
        self.execution_service.set_truth_state_fn(self._truth_state_for_execution)
        self._stop = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._safety_oracle_thread: threading.Thread | None = None
        self._ws_thread: threading.Thread | None = None

    async def _handle_ws_message(self, event: NormalizedPrivateEvent) -> None:
        self.ws_queue.put(event)

    def _touch_rest_catchup_ts(self) -> None:
        self._last_rest_catchup_ts_ms = int(time.time() * 1000)

    async def _on_private_ws_connected(self, is_reconnect: bool) -> None:
        if not self.settings.live_broker_rest_catchup_on_ws_connect:
            return
        if not self.settings.private_exchange_access_enabled:
            return
        try:
            self.catchup_queue.put_nowait("ws_reconnect" if is_reconnect else "ws_connect")
        except queue.Full:
            logger.warning("rest catchup queue full after private ws connect")

    def _enqueue_private_ws_stale_catchup(self) -> None:
        if not self.settings.live_broker_rest_catchup_on_ws_connect:
            return
        if not self.settings.private_exchange_access_enabled:
            return
        try:
            self.catchup_queue.put_nowait("ws_stale_private")
        except queue.Full:
            logger.warning("rest catchup queue full after private ws stale recover")

    def _private_ws_telemetry(self) -> dict[str, Any]:
        now_ms = int(time.time() * 1000)
        last_ev = self.ws_stats.last_event_ts_ms
        age_ms = (now_ms - last_ev) if last_ev is not None else None
        thr_ms = int(self.settings.live_broker_private_ws_stale_after_sec) * 1000
        data_stale = (
            age_ms is not None
            and age_ms >= thr_ms
            and self.ws_stats.connection_state == "connected"
        )
        return {
            "state": self.ws_stats.connection_state,
            "received_events": self.ws_stats.received_events,
            "reconnects": self.ws_stats.reconnect_count,
            "last_event_ts_ms": last_ev,
            "last_event_age_ms": age_ms,
            "last_exchange_ts_ms": self.ws_stats.last_exchange_ts_ms,
            "last_ingest_latency_ms": self.ws_stats.last_ingest_latency_ms,
            "last_ping_ts_ms": self.ws_stats.last_ping_ts_ms,
            "last_pong_ts_ms": self.ws_stats.last_pong_ts_ms,
            "ping_count": self.ws_stats.ping_count,
            "pong_count": self.ws_stats.pong_count,
            "channel_coverage": list(self.ws_stats.channel_coverage),
            "ws_endpoint_host": self.ws_stats.ws_endpoint_host,
            "stale_escalation_count": self.ws_stats.stale_escalation_count,
            "gap_recovery_triggers": self.ws_stats.gap_recovery_triggers,
            "last_stale_catchup_ts_ms": self.ws_stats.last_stale_catchup_ts_ms,
            "data_stale_suspected": data_stale,
            "stale_threshold_sec": self.settings.live_broker_private_ws_stale_after_sec,
        }

    def _truth_state_for_execution(self) -> dict[str, Any]:
        try:
            snap = self.repo.latest_reconcile_snapshot() or {}
        except Exception as exc:
            logger.warning("latest_reconcile_snapshot failed (truth gate): %s", exc)
            now_ms = int(time.time() * 1000)
            catchup_ms = self._last_rest_catchup_ts_ms
            ws_ok = self.ws_stats.connection_state == "connected"
            max_age_ms = self.settings.live_broker_rest_catchup_max_age_sec * 1000
            catchup_fresh = catchup_ms > 0 and (now_ms - catchup_ms) < max_age_ms
            try:
                safety_latch = self.repo.safety_latch_is_active()
            except Exception:
                safety_latch = False
            return merge_survival_truth(
                {
                    "truth_channel_ok": ws_ok or catchup_fresh,
                    "truth_reason": "reconcile_snapshot_unavailable",
                    "drift_blocked": True,
                    "drift_total": -1,
                    "snapshot_missing": 0,
                    "snapshot_stale": 0,
                    "ws_connected": ws_ok,
                    "last_rest_catchup_age_ms": (now_ms - catchup_ms) if catchup_ms else None,
                    "safety_latch_blocks_live": safety_latch,
                },
                redis=self.bus.redis,
            )

        details = snap.get("details_json") or {}
        drift = details.get("drift") or {}
        total = int(drift.get("total_count") or 0)
        sh = drift.get("snapshot_health") or {}
        missing = int(sh.get("missing_count") or 0)
        stale = int(sh.get("stale_count") or 0)
        drift_blocked = total > 0 or missing > 0 or stale > 0

        now_ms = int(time.time() * 1000)
        ws_ok = self.ws_stats.connection_state == "connected"
        max_age_ms = self.settings.live_broker_rest_catchup_max_age_sec * 1000
        catchup_ms = self._last_rest_catchup_ts_ms
        catchup_fresh = catchup_ms > 0 and (now_ms - catchup_ms) < max_age_ms
        truth_channel_ok = ws_ok or catchup_fresh
        truth_reason = (
            "ws_connected"
            if ws_ok
            else ("rest_catchup_fresh" if catchup_fresh else "no_fresh_exchange_truth_channel")
        )
        try:
            safety_latch = self.repo.safety_latch_is_active()
        except Exception:
            safety_latch = False
        return merge_survival_truth(
            {
                "truth_channel_ok": truth_channel_ok,
                "truth_reason": truth_reason,
                "drift_blocked": drift_blocked,
                "drift_total": total,
                "snapshot_missing": missing,
                "snapshot_stale": stale,
                "ws_connected": ws_ok,
                "last_rest_catchup_age_ms": (now_ms - catchup_ms) if catchup_ms else None,
                "safety_latch_blocks_live": safety_latch,
            },
            redis=self.bus.redis,
        )

    def _run_ws_client_sync(self) -> None:
        try:
            asyncio.run(self.ws_client.run())
        except Exception as exc:
            logger.exception("Private WS loop failed: %s", exc)

    def start_background(self) -> None:
        if self._worker_thread is not None:
            return
        if getattr(self, "_strategy_config_guard_failed", False):
            return
        try:
            self.catalog.refresh_catalog(refresh_reason="startup")
            self.catalog_entry = self.catalog.current_configured_instrument(
                refresh_if_missing=False,
                require_subscription=False,
            )
            self.catalog_block_reason = None
        except Exception as exc:
            self.catalog_entry = None
            self.catalog_block_reason = str(exc)
            logger.error("live-broker catalog blocked: %s", exc)
            return
        dsn = (self.settings.database_url or "").strip()
        try:
            from live_broker.strategy_config_guard import should_verify, verify_bound_strategy_version_or_raise

            if dsn and should_verify(self.settings):
                verify_bound_strategy_version_or_raise(
                    dsn,
                    version_id=self.settings.live_broker_strategy_version_id,
                    expected_hash=self.settings.live_broker_strategy_config_expected_hash,
                )
        except Exception as exc:
            self._strategy_config_guard_failed = True
            self.catalog_block_reason = f"strategy_registry_config_guard: {exc}"
            logger.critical("live-broker strategy config guard: %s", exc)
            return
        self._stop.clear()
        self.global_halt.start()
        start_runtime_safety_oracle_thread(self)

        self._worker_thread = threading.Thread(
            target=self.worker.run_forever,
            args=(self._stop,),
            name="live-broker-worker",
            daemon=True,
        )
        self._worker_thread.start()
        logger.info("live-broker worker started")

        if self.settings.private_exchange_access_enabled:
            self._ws_thread = threading.Thread(
                target=self._run_ws_client_sync,
                name="live-broker-private-ws",
                daemon=True,
            )
            self._ws_thread.start()
            logger.info("live-broker private WS thread started")

    def stop_background(self) -> None:
        self._stop.set()
        join_runtime_safety_oracle_thread(self)
        self.global_halt.stop()
        self.repo.close()

        # WS Client graceful stop
        if self._ws_thread is not None:
            try:
                # We need to run stop() in a new loop just to signal the event
                asyncio.run(self.ws_client.stop())
            except Exception as exc:
                logger.warning("Error stopping ws client: %s", exc)
            self._ws_thread.join(timeout=5.0)
            self._ws_thread = None
            
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=5.0)
            self._worker_thread = None
        logger.info("live-broker background threads stopped")

    def runtime_payload(self) -> dict[str, Any]:
        latest_reconcile = None
        decision_counts: dict[str, int] = {}
        schema_ok, schema_detail = self.repo.schema_ready()
        if schema_ok:
            try:
                latest_reconcile = self.reconcile_service.latest_snapshot()
                decision_counts = self.repo.decision_action_counts()
            except Exception as exc:
                schema_ok = False
                schema_detail = str(exc)[:200]
        return {
            "service": "live-broker",
            "global_halt": self.global_halt.is_halted,
            "execution_mode": self.settings.execution_mode,
            "runtime_mode": self.settings.execution_mode,
            "strategy_execution_mode": self.settings.strategy_execution_mode,
            "execution_runtime": self.settings.execution_runtime_snapshot(),
            "api_auth_mode": self.settings.api_auth_mode,
            "instrument_catalog": self.catalog.health_payload(),
            "instrument_metadata": self.metadata_service.health_payload(),
            "catalog_block_reason": self.catalog_block_reason,
            "paper_path_active": self.settings.paper_path_active,
            "shadow_trade_enable": self.settings.shadow_trade_enable,
            "shadow_path_active": self.settings.shadow_path_active,
            "live_trade_enable": self.settings.live_trade_enable,
            "live_order_submission_enabled": self.settings.live_order_submission_enabled,
            "exchange": self.exchange_client.describe(),
            "orders": self.order_service.state_snapshot(),
            "interfaces": self.execution_service.interfaces_payload(),
            "persistence": {
                "schema_ready": schema_ok,
                "schema_detail": schema_detail,
                "decision_counts": decision_counts,
            },
            "latest_reconcile": latest_reconcile,
            "worker": self.worker.stats_payload(),
            "private_ws": self._private_ws_telemetry(),
            "fill_liquidity": self.exchange_state_sync.liquidity_fill_counters(),
            "exchange_truth": self.execution_service.truth_status_snapshot(),
            "instrument": (
                self.catalog_entry.identity().model_dump(mode="json")
                if self.catalog_entry is not None
                else self.settings.instrument_identity().model_dump(mode="json")
            ),
            "control_plane": self.control_plane.matrix_payload(),
            "commercial_gates": commercial_runtime_payload(
                self.settings,
                schema_ready=schema_ok,
            ),
        }

    def health_payload(self) -> dict[str, Any]:
        runtime = self.runtime_payload()
        fill_liquidity = runtime.get("fill_liquidity") or {}
        latest_reconcile = runtime.get("latest_reconcile") or {}
        latest_status = str(latest_reconcile.get("status") or "ok")
        persistence_ok = bool(runtime["persistence"]["schema_ready"])
        metadata_ok = runtime.get("instrument_metadata", {}).get("status") == "ok"
        keys_ok, keys_detail = self.exchange_client.private_api_configured()
        bitget_rest_health: dict[str, Any] = {
            "credential_profile": "demo" if self.settings.bitget_demo_enabled else "live",
            "paptrading_header_active": bool(self.settings.bitget_demo_enabled),
            "credential_isolation_relaxed": bool(self.settings.bitget_relax_credential_isolation),
            "private_api_configured": keys_ok,
            "private_detail": keys_detail,
            "private_rest": self.private_rest_client.state_snapshot(),
        }
        return {
            "status": "ok" if latest_status == "ok" and persistence_ok and metadata_ok else "degraded",
            "service": "live-broker",
            "execution_mode": runtime["execution_mode"],
            "runtime_mode": runtime["runtime_mode"],
            "strategy_execution_mode": runtime["strategy_execution_mode"],
            "paper_path_active": runtime["paper_path_active"],
            "shadow_trade_enable": runtime["shadow_trade_enable"],
            "shadow_path_active": runtime["shadow_path_active"],
            "live_trade_enable": runtime["live_trade_enable"],
            "live_order_submission_enabled": runtime["live_order_submission_enabled"],
            "execution_runtime": runtime.get("execution_runtime"),
            "persistence": runtime["persistence"],
            "orders": runtime["orders"],
            "worker": runtime["worker"],
            "private_ws": runtime["private_ws"],
            "interfaces": runtime["interfaces"],
            "latest_reconcile": latest_reconcile,
            "bitget_rest": bitget_rest_health,
            "commercial_gates": runtime.get("commercial_gates"),
            "fill_liquidity": fill_liquidity,
        }

    def ready_payload(self) -> dict[str, Any]:
        try:
            eb_ok = bool(self.bus.ping())
            eb_detail = "ok"
        except Exception as exc:
            eb_ok = False
            eb_detail = str(exc)[:200]
        parts = {
            "postgres": check_postgres(self.settings.database_url),
            "redis": check_redis_url(self.settings.redis_url),
            "eventbus": (eb_ok, eb_detail),
            "persistence_schema": self.repo.schema_ready(),
            "instrument_catalog": (
                self.catalog_block_reason is None,
                self.catalog_block_reason or self.catalog.health_payload().get("status", "ok"),
            ),
            "instrument_metadata": (
                self.catalog_block_reason is None
                and self.metadata_service.health_payload().get("status") == "ok",
                self.metadata_service.health_payload().get("status", "unavailable"),
            ),
        }
        probe: dict[str, Any] | None = None
        exchange_required = self.settings.private_exchange_access_enabled
        if exchange_required and self.settings.live_require_exchange_health:
            probe = self.exchange_client.probe_exchange()
            parts["bitget_public"] = (
                bool(probe.get("public_api_ok")),
                str(probe.get("public_detail")),
            )
        if self.settings.live_order_submission_enabled:
            if probe is None:
                probe = self.exchange_client.probe_exchange()
            parts["bitget_private_config"] = (
                bool(probe.get("private_api_configured")),
                str(probe.get("private_detail")),
            )
            try:
                state = self.private_rest_client.sync_server_time(force=True)
                offset = abs(int(state["server_time_offset_ms"]))
                parts["bitget_server_time"] = (
                    bool(state["offset_within_budget"]) and offset <= 30_000,
                    (
                        f"offset_ms={offset} "
                        f"budget_ms={self.settings.live_broker_server_time_max_skew_ms} "
                        f"rtt_ms={state['last_server_rtt_ms']}"
                    ),
                )
            except BitgetRestError as exc:
                parts["bitget_server_time"] = (False, str(exc))
        parts = append_peer_readiness_checks(
            parts,
            self.settings.readiness_require_urls_raw,
            timeout_sec=float(self.settings.readiness_peer_timeout_sec),
        )
        ok, details = merge_ready_details(parts)
        details["execution_mode"] = self.settings.execution_mode
        details["runtime_mode"] = self.settings.execution_mode
        details["strategy_execution_mode"] = self.settings.strategy_execution_mode
        details["paper_path_active"] = self.settings.paper_path_active
        details["shadow_trade_enable"] = self.settings.shadow_trade_enable
        details["shadow_path_active"] = self.settings.shadow_path_active
        details["live_trade_enable"] = self.settings.live_trade_enable
        details["live_order_submission_enabled"] = self.settings.live_order_submission_enabled
        details["execution_runtime"] = self.settings.execution_runtime_snapshot()
        details["interfaces"] = self.execution_service.interfaces_payload()
        details["orders"] = self.order_service.state_snapshot()
        if probe is not None:
            details["exchange_probe"] = {
                "public_api_ok": probe.get("public_api_ok"),
                "private_api_configured": probe.get("private_api_configured"),
                "market_snapshot": probe.get("market_snapshot"),
            }
        return {"ready": ok, "service": "live-broker", "checks": details}


def create_app(*, start_background: bool = True) -> FastAPI:
    from config.bootstrap import bootstrap_from_settings

    settings = LiveBrokerSettings()
    bootstrap_from_settings("live-broker", settings)
    runtime = LiveBrokerRuntime(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        dsn = (settings.database_url or "").strip()
        skip = (os.environ.get("BITGET_SKIP_MIGRATION_LATCH") or "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        if dsn and not skip:
            from shared_py.datastore.sqlalchemy_async import create_pooled_async_engine
            from shared_py.migration_latch import assert_repo_migrations_applied_async

            eng = create_pooled_async_engine(dsn)
            app.state.db_async_engine = eng
            try:
                await assert_repo_migrations_applied_async(eng)
            except Exception:
                await eng.dispose()
                app.state.db_async_engine = None
                raise
        else:
            app.state.db_async_engine = None
        app.state.runtime = runtime
        if start_background:
            runtime.start_background()
        try:
            yield
        finally:
            if start_background:
                runtime.stop_background()
            eng = getattr(app.state, "db_async_engine", None)
            if eng is not None:
                await eng.dispose()
                app.state.db_async_engine = None

    app = FastAPI(
        title="live-broker",
        version="0.1.0",
        description=(
            "Live broker runtime member with shadow execution intake, "
            "Bitget exchange probes, persistence and reconcile."
        ),
        lifespan=lifespan,
    )
    app.include_router(build_health_router(runtime))
    app.include_router(build_ops_router(runtime))
    instrument_fastapi(app, "live-broker")
    return app


app = create_app()
