from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from shared_py.eventbus import RedisStreamBus
from shared_py.observability import start_thread_periodic_heartbeat

from live_broker.config import LiveBrokerSettings
from live_broker.execution.service import LiveExecutionService
from live_broker.exits.service import LiveExitService
from live_broker.orders.service import LiveBrokerOrderService
from live_broker.persistence.repo import LiveBrokerRepository
from live_broker.private_rest import BitgetPrivateRestClient
from live_broker.private_ws.sync import ExchangeStateSyncService
from live_broker.private_ws import PrivateWsClientStats
from live_broker.reconcile.rest_catchup import run_rest_snapshot_catchup
from live_broker.reconcile.service import LiveReconcileService

logger = logging.getLogger("live_broker.worker")


class LiveBrokerWorker:
    def __init__(
        self,
        settings: LiveBrokerSettings,
        bus: RedisStreamBus,
        repo: LiveBrokerRepository,
        execution_service: LiveExecutionService,
        order_service: LiveBrokerOrderService,
        exit_service: LiveExitService,
        reconcile_service: LiveReconcileService,
        exchange_state_sync: ExchangeStateSyncService,
        ws_queue: queue.Queue | None = None,
        *,
        catchup_queue: queue.Queue[str] | None = None,
        private_rest: BitgetPrivateRestClient | None = None,
        on_rest_catchup_success: Callable[[], None] | None = None,
        private_ws_stats: PrivateWsClientStats | None = None,
    ) -> None:
        self._settings = settings
        self._bus = bus
        self._repo = repo
        self._execution_service = execution_service
        self._order_service = order_service
        self._exit_service = exit_service
        self._reconcile_service = reconcile_service
        self._exchange_state_sync = exchange_state_sync
        self._ws_queue = ws_queue
        self._catchup_queue = catchup_queue
        self._private_rest = private_rest
        self._on_rest_catchup_success = on_rest_catchup_success
        self._private_ws_stats = private_ws_stats
        self._stats: dict[str, Any] = {
            "signals_consumed": 0,
            "signals_skipped_mode": 0,
            "paper_reference_events": 0,
            "dlq_published": 0,
            "last_error": None,
            "last_reconcile_ts": None,
            "last_timeout_run": None,
            "last_exit_run": None,
            "last_ws_event": None,
            "ws_events_processed": 0,
            "recovered_open_orders": 0,
            "recovered_exchange_positions": 0,
            "recovered_exchange_accounts": 0,
            "timed_out_orders": 0,
            "exit_orders_submitted": 0,
            "thread_running": False,
            "rest_catchups": 0,
        }

    def stats_payload(self) -> dict[str, Any]:
        return dict(self._stats)

    def _process_rest_catchup_queue(self) -> None:
        if self._catchup_queue is None or self._private_rest is None:
            return
        while True:
            try:
                reason = self._catchup_queue.get_nowait()
            except queue.Empty:
                break
            try:
                run_rest_snapshot_catchup(
                    self._settings,
                    self._repo,
                    self._private_rest,
                    reason=str(reason),
                    reconcile_run_id=None,
                )
                self._stats["rest_catchups"] = int(self._stats.get("rest_catchups") or 0) + 1
                if self._on_rest_catchup_success is not None:
                    self._on_rest_catchup_success()
            except Exception as exc:
                self._stats["last_error"] = str(exc)[:200]
                logger.exception(
                    "rest snapshot catchup failed reason=%s err=%s",
                    reason,
                    exc,
                )

    def _handle_ws_event(self, event: Any) -> None:
        self._stats["last_ws_event"] = event.event_type
        self._exchange_state_sync.handle_event(event)
        self._stats["ws_events_processed"] += 1

    def run_forever(self, stop_event: threading.Event) -> None:
        streams = [self._settings.live_broker_signal_stream, *self._settings.reference_streams]
        self._stats["thread_running"] = True
        hb_t = start_thread_periodic_heartbeat("live_broker", 8.0, stop_event)
        try:
            for stream in streams:
                self._bus.ensure_group(stream, self._settings.live_broker_consumer_group)
            if (
                self._private_rest is not None
                and self._catchup_queue is not None
                and self._settings.live_broker_rest_catchup_on_worker_start
                and self._settings.private_exchange_access_enabled
            ):
                try:
                    self._catchup_queue.put_nowait("worker_start")
                except queue.Full:
                    logger.warning("rest catchup queue full on worker start")
            try:
                recovery_state = self._reconcile_service.restore_runtime_state()
                self._stats["recovered_open_orders"] = int(
                    recovery_state.get("open_order_count") or 0
                )
                self._stats["recovered_exchange_positions"] = int(
                    recovery_state.get("exchange_position_snapshot_count") or 0
                )
                self._stats["recovered_exchange_accounts"] = int(
                    recovery_state.get("exchange_account_snapshot_count") or 0
                )
            except Exception as exc:
                self._stats["last_error"] = str(exc)[:200]
                logger.exception("runtime recovery snapshot failed: %s", exc)
            next_reconcile_at = 0.0
            while not stop_event.is_set():
                now = time.monotonic()
                if now >= next_reconcile_at:
                    try:
                        timeout_summary = self._order_service.run_order_timeouts()
                        self._stats["last_timeout_run"] = int(time.time() * 1000)
                        self._stats["timed_out_orders"] += int(
                            timeout_summary.get("timed_out") or 0
                        )
                        telemetry: dict[str, Any] = {
                            "worker": {
                                "last_ws_event": self._stats.get("last_ws_event"),
                                "ws_events_processed": self._stats.get("ws_events_processed"),
                            }
                        }
                        if self._private_ws_stats is not None:
                            telemetry["private_ws"] = asdict(self._private_ws_stats)
                        snapshot = self._reconcile_service.run_once(
                            reason="worker_interval",
                            worker_telemetry=telemetry,
                        )
                        self._stats["last_reconcile_ts"] = snapshot.get("created_ts")
                        div = (snapshot.get("details_json") or {}).get("drift", {}).get("divergence") or {}
                        pw = div.get("private_ws") or {}
                        if (
                            self._catchup_queue is not None
                            and self._private_rest is not None
                            and pw.get("enqueue_rest_catchup")
                        ):
                            try:
                                self._catchup_queue.put_nowait("ws_stale_reconcile")
                            except queue.Full:
                                logger.warning("rest catchup queue full (ws_stale_reconcile)")
                        exit_summary = self._exit_service.run_once(reason="worker_interval")
                        self._stats["last_exit_run"] = int(time.time() * 1000)
                        self._stats["exit_orders_submitted"] = int(
                            exit_summary.get("exit_orders_submitted") or 0
                        )
                    except Exception as exc:
                        self._stats["last_error"] = str(exc)[:200]
                        logger.exception("periodic reconcile failed: %s", exc)
                    next_reconcile_at = now + max(1, self._settings.live_reconcile_interval_sec)

                activity = False
                if self._ws_queue is not None:
                    while not self._ws_queue.empty():
                        try:
                            ws_event = self._ws_queue.get_nowait()
                            self._handle_ws_event(ws_event)
                            activity = True
                        except queue.Empty:
                            break
                        except Exception as exc:
                            self._stats["last_error"] = str(exc)[:200]
                            logger.exception("WS event handling failed: %s", exc)

                self._process_rest_catchup_queue()

                for index, stream in enumerate(streams):
                    items = self._bus.consume(
                        stream,
                        self._settings.live_broker_consumer_group,
                        self._settings.live_broker_consumer_name,
                        count=10,
                        block_ms=1000 if index == 0 else 1,
                    )
                    if not items:
                        continue
                    activity = True
                    for item in items:
                        try:
                            if item.envelope.event_type == "signal_created":
                                if self._settings.paper_path_active:
                                    self._stats["signals_skipped_mode"] += 1
                                    self._bus.ack(
                                        item.stream,
                                        self._settings.live_broker_consumer_group,
                                        item.message_id,
                                    )
                                    continue
                                self._execution_service.handle_signal_event(item.envelope)
                                self._stats["signals_consumed"] += 1
                            else:
                                self._execution_service.record_paper_reference_event(
                                    item.envelope,
                                    message_id=item.message_id,
                                )
                                self._stats["paper_reference_events"] += 1
                            self._bus.ack(item.stream, self._settings.live_broker_consumer_group, item.message_id)
                        except Exception as exc:
                            self._stats["last_error"] = str(exc)[:200]
                            logger.exception(
                                "worker event processing failed stream=%s message_id=%s error=%s",
                                item.stream,
                                item.message_id,
                                exc,
                            )
                            try:
                                self._bus.publish_dlq(
                                    item.envelope,
                                    {
                                        "stage": "live-broker-worker",
                                        "stream": item.stream,
                                        "message_id": item.message_id,
                                        "error": str(exc),
                                    },
                                )
                                self._stats["dlq_published"] += 1
                                self._bus.ack(
                                    item.stream,
                                    self._settings.live_broker_consumer_group,
                                    item.message_id,
                                )
                            except Exception as dlq_exc:
                                self._stats["last_error"] = str(dlq_exc)[:200]
                                logger.exception("worker DLQ publish failed: %s", dlq_exc)
                if not activity:
                    time.sleep(0.2)
        finally:
            if hb_t.is_alive():
                hb_t.join(timeout=2.0)
            self._stats["thread_running"] = False
