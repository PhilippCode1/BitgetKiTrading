from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx
import redis

from monitor_engine.alerts.dedupe import PublishDedupe
from monitor_engine.alerts.publisher import process_alerts
from monitor_engine.alerts.rules import (
    AlertSpec,
    alert_stream_stalled,
    alerts_from_freshness,
    alerts_from_service_checks,
    alerts_from_stream_checks,
)
from monitor_engine.alerts.trading_sql_alerts import collect_trading_sql_alerts
from monitor_engine.checks.data_freshness import FreshnessRow, load_all_freshness
from monitor_engine.checks.live_broker import load_live_broker_service_checks
from monitor_engine.checks.online_drift import load_online_drift_service_check
from monitor_engine.checks.llm_health import check_llm_streams
from monitor_engine.checks.redis_streams import check_stream_groups, stream_length
from monitor_engine.checks.services_http import ServiceCheckResult, probe_service
from monitor_engine.config import MonitorEngineSettings
from monitor_engine.prom_metrics import (
    DATA_FRESHNESS_SECONDS,
    LIVE_CRITICAL_AUDITS_24H,
    LIVE_SAFETY_LATCH_ACTIVE,
    MONITOR_ENGINE_TICK_DURATION_SECONDS,
    ONLINE_DRIFT_ACTION_RANK,
    REDIS_STREAM_LAG,
    SHADOW_LIVE_GATE_BLOCKS_24H,
    SHADOW_LIVE_MATCH_FAILURES_24H,
)
from monitor_engine.trading_db_metrics import (
    apply_live_broker_check_gauges,
    refresh_trading_sql_metrics,
)
from shared_py.online_drift import action_rank
from monitor_engine.storage.repo_alerts import count_open_alerts
from monitor_engine.storage.repo_checks import (
    insert_data_freshness,
    insert_service_checks,
    insert_stream_checks,
)
from shared_py.observability import touch_worker_heartbeat

logger = logging.getLogger("monitor_engine.scheduler")


def _sanitize_label(s: str) -> str:
    return s.replace(":", "_").replace(" ", "_")


class MonitorScheduler:
    def __init__(self, settings: MonitorEngineSettings) -> None:
        self.settings = settings
        self._dedupe = PublishDedupe()
        self._wake = asyncio.Event()
        self._stream_prev_len: dict[str, int] = {}
        self._bus: Any = None
        self._stats: dict[str, Any] = {
            "last_run_ts_ms": None,
            "last_duration_ms": None,
            "last_alert_count": 0,
            "service_check_count": 0,
            "stream_check_count": 0,
            "freshness_check_count": 0,
            "live_broker_check_count": 0,
            "open_alert_count": 0,
            "last_error": None,
        }

    def bind_bus(self, bus: Any) -> None:
        self._bus = bus

    def wake(self) -> None:
        self._wake.set()

    def stats_snapshot(self) -> dict[str, Any]:
        return dict(self._stats)

    def _candle_thresholds(self) -> dict[str, int]:
        return {
            "1m": self.settings.thresh_stale_ms_1m,
            "5m": self.settings.thresh_stale_ms_5m,
            "15m": self.settings.thresh_stale_ms_15m,
            "1H": self.settings.thresh_stale_ms_1h,
            "4H": self.settings.thresh_stale_ms_4h,
        }

    async def run_forever(self) -> None:
        assert self._bus is not None
        async with httpx.AsyncClient() as client:
            while True:
                try:
                    await self._tick(client)
                    self._stats["last_error"] = None
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self._stats["last_error"] = str(exc)[:200]
                    logger.exception("monitor tick failed")
                finally:
                    touch_worker_heartbeat("monitor_engine")
                interval = max(1, self.settings.monitor_interval_sec)
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=interval)
                    self._wake.clear()
                except TimeoutError:
                    pass

    async def run_once(self, client: httpx.AsyncClient | None = None) -> None:
        assert self._bus is not None
        if client is None:
            async with httpx.AsyncClient() as hc:
                await self._tick(hc)
        else:
            await self._tick(client)

    async def _tick(self, client: httpx.AsyncClient) -> None:
        t0 = time.perf_counter()
        logger.info("run checks start")
        svc_results: list[Any] = []
        for name, base in self.settings.service_urls.items():
            svc_results.extend(await probe_service(client, name, base))
        try:
            live_broker_checks = load_live_broker_service_checks(
                self.settings.database_url,
                reconcile_stale_ms=self.settings.thresh_live_reconcile_stale_ms,
                error_lookback_ms=self.settings.thresh_live_error_lookback_ms,
                kill_switch_age_ms=self.settings.thresh_live_kill_switch_age_ms,
                now_ms=int(time.time() * 1000),
            )
        except Exception as exc:
            logger.warning("live-broker ops checks failed: %s", exc)
            live_broker_checks = [
                ServiceCheckResult(
                    service_name="live-broker",
                    check_type="ops_snapshot",
                    status="fail",
                    latency_ms=None,
                    details={"error": str(exc)[:300]},
                )
            ]
        svc_results.extend(live_broker_checks)
        LIVE_SAFETY_LATCH_ACTIVE.set(0.0)
        reconcile_details: dict | None = None
        kill_switch_details: dict | None = None
        for lb in live_broker_checks:
            if lb.check_type == "reconcile" and isinstance(lb.details, dict):
                reconcile_details = lb.details
            if lb.check_type == "kill_switch" and isinstance(lb.details, dict):
                kill_switch_details = lb.details
            if lb.check_type == "shadow_live_divergence" and isinstance(lb.details, dict):
                SHADOW_LIVE_GATE_BLOCKS_24H.set(
                    float(lb.details.get("gate_blocks_24h") or 0)
                )
                SHADOW_LIVE_MATCH_FAILURES_24H.set(
                    float(lb.details.get("match_failures_24h") or 0)
                )
            if lb.check_type == "safety_latch" and isinstance(lb.details, dict):
                LIVE_SAFETY_LATCH_ACTIVE.set(
                    1.0 if lb.details.get("safety_latch_active") else 0.0
                )
        apply_live_broker_check_gauges(
            reconcile_details=reconcile_details,
            kill_switch_details=kill_switch_details,
        )
        crit_audit_n = 0.0
        for lb in live_broker_checks:
            if lb.check_type == "audit" and isinstance(lb.details, dict):
                crit_audit_n = float(lb.details.get("critical_audit_count") or 0)
                break
        LIVE_CRITICAL_AUDITS_24H.set(crit_audit_n)
        try:
            refresh_trading_sql_metrics(self.settings.database_url)
        except Exception as exc:
            logger.warning("refresh_trading_sql_metrics failed: %s", exc)
        try:
            online_drift_checks = load_online_drift_service_check(self.settings.database_url)
        except Exception as exc:
            logger.warning("online-drift check failed: %s", exc)
            online_drift_checks = [
                ServiceCheckResult(
                    service_name="online-drift",
                    check_type="learn_online_drift_state",
                    status="fail",
                    latency_ms=None,
                    details={"error": str(exc)[:240]},
                )
            ]
        svc_results.extend(online_drift_checks)
        for od in online_drift_checks:
            if od.check_type == "learn_online_drift_state" and isinstance(od.details, dict):
                ONLINE_DRIFT_ACTION_RANK.set(
                    float(action_rank(str(od.details.get("effective_action") or "ok")))
                )

        insert_service_checks(self.settings.database_url, svc_results)

        stream_rows = check_stream_groups(
            self.settings.redis_url,
            self.settings.streams,
            self.settings.stream_groups,
            thresh_pending=self.settings.thresh_pending_max,
            thresh_lag=self.settings.thresh_lag_max,
        )
        insert_stream_checks(self.settings.database_url, stream_rows)

        for row in stream_rows:
            lag_val = float(row.lag) if row.lag is not None else 0.0
            REDIS_STREAM_LAG.labels(
                _sanitize_label(row.stream),
                _sanitize_label(row.group_name),
            ).set(lag_val)

        now_ms = int(time.time() * 1000)
        fresh_rows = load_all_freshness(
            self.settings.database_url,
            self.settings.symbol,
            stale_thresholds=self._candle_thresholds(),
            signal_stale_ms=self.settings.thresh_stale_signals_ms,
            drawing_stale_ms=self.settings.thresh_stale_drawings_ms,
            news_stale_ms=self.settings.thresh_stale_news_ms,
            funding_stale_ms=self.settings.thresh_stale_funding_ms,
            oi_stale_ms=self.settings.thresh_stale_oi_ms,
        )

        llm = check_llm_streams(
            self.settings.redis_url,
            warn_dlq=self.settings.thresh_dlq_len_warn,
            crit_dlq=self.settings.thresh_dlq_len_crit,
            stale_llm_ms=self.settings.thresh_stale_llm_ms,
            now_ms=now_ms,
        )
        llm_last = llm.llm_failed_last_ts_ms
        llm_age = now_ms - llm_last if llm_last is not None else None
        llm_status = "ok"
        if llm.dlq_len >= self.settings.thresh_dlq_len_crit:
            llm_status = "critical"
        elif llm.dlq_len >= self.settings.thresh_dlq_len_warn:
            llm_status = "warn"
        fresh_rows.append(
            FreshnessRow(
                datapoint="llm",
                last_ts_ms=llm_last,
                age_ms=llm_age,
                status=llm_status,
                details={"dlq_len": llm.dlq_len},
            )
        )

        candle_1m_critical = False
        for fr in fresh_rows:
            age_s = (fr.age_ms or 0) / 1000.0
            DATA_FRESHNESS_SECONDS.labels(fr.datapoint).set(age_s)
            if fr.datapoint == "candles_1m" and fr.status == "critical":
                candle_1m_critical = True

        insert_data_freshness(self.settings.database_url, fresh_rows)

        r = redis.Redis.from_url(
            self.settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        stalled_specs: list[AlertSpec] = []
        for stream in self.settings.streams:
            cur = stream_length(r, stream)
            prev = self._stream_prev_len.get(stream)
            if prev is not None and cur == prev and candle_1m_critical:
                spec = alert_stream_stalled(stream, candle_stale_critical=True)
                if spec is not None:
                    stalled_specs.append(spec)
            self._stream_prev_len[stream] = cur
        try:
            trading_sql_specs = collect_trading_sql_alerts(self.settings)
        except Exception as exc:
            logger.warning("collect_trading_sql_alerts failed in scheduler: %s", exc)
            trading_sql_specs = []

        specs = (
            alerts_from_service_checks(svc_results)
            + alerts_from_stream_checks(stream_rows)
            + alerts_from_freshness(fresh_rows)
            + stalled_specs
            + trading_sql_specs
        )
        specs.sort(
            key=lambda s: (
                s.priority,
                0 if s.severity == "critical" else 1,
                s.alert_key,
            )
        )

        process_alerts(
            self.settings.database_url,
            self._bus,
            specs,
            dedupe=self._dedupe,
            dedupe_sec=self.settings.monitor_alert_dedupe_sec,
        )

        dt = time.perf_counter() - t0
        try:
            open_alert_count = count_open_alerts(self.settings.database_url)
        except Exception as exc:
            logger.warning("count open alerts failed: %s", exc)
            open_alert_count = int(self._stats.get("open_alert_count") or 0)
        self._stats.update(
            {
                "last_run_ts_ms": int(time.time() * 1000),
                "last_duration_ms": int(dt * 1000),
                "last_alert_count": len(specs),
                "service_check_count": len(svc_results),
                "stream_check_count": len(stream_rows),
                "freshness_check_count": len(fresh_rows),
                "live_broker_check_count": len(live_broker_checks),
                "open_alert_count": open_alert_count,
            }
        )
        MONITOR_ENGINE_TICK_DURATION_SECONDS.observe(dt)
        logger.info("run checks done duration_sec=%.3f alerts=%s", dt, len(specs))
