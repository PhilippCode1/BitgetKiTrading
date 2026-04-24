from __future__ import annotations

from typing import ClassVar

from pydantic import Field, model_validator
from pydantic_settings import SettingsConfigDict

from config.settings import BaseServiceSettings


def _parse_service_urls(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, url = part.split("=", 1)
        name, url = name.strip(), url.strip().rstrip("/")
        if name and url:
            out[name] = url
    return out


def _split_csv(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


class MonitorEngineSettings(BaseServiceSettings):
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

    monitor_readiness_boot_grace_ms: int = Field(
        default=120_000,
        ge=5_000,
        le=600_000,
        alias="MONITOR_READINESS_BOOT_GRACE_MS",
        description="Nach Prozessstart: /ready erlaubt fehlenden ersten Scheduler-Tick nur innerhalb dieses Fensters.",
    )
    monitor_http_ready_fails_to_degrade: int = Field(
        default=2,
        ge=1,
        le=10,
        alias="MONITOR_HTTP_READY_FAILS_TO_DEGRADE",
        description=(
            "Kern-HTTP-Requests /ready: so viele aufeinanderfolgende JSON ready=false, "
            "ehe der Check als 'degraded' (statt transiente Warnung) zaehlt."
        ),
    )
    monitor_heartbeat_stale_warn_sec: float = Field(
        default=10.0,
        ge=1.0,
        le=300.0,
        alias="MONITOR_HEARTBEAT_STALE_WARN_SEC",
        description="Pre-Alert: ab diesem Alter (s) des Prometheus worker_heartbeat WARNING-Log, vor Degradation.",
    )
    monitor_heartbeat_stale_degrade_sec: float = Field(
        default=15.0,
        ge=2.0,
        le=600.0,
        alias="MONITOR_HEARTBEAT_STALE_DEGRADE_SEC",
        description="Grace-Periode: /metrics-Check erst ab diesem Alter (s) als 'degraded'.",
    )
    monitor_scheduler_stale_multiplier: float = Field(
        default=1.35,
        ge=1.0,
        le=3.0,
        alias="MONITOR_SCHEDULER_STALE_MULTIPLIER",
        description="Erweitert die Altersgrenze fuer 'letzter Monitor-Tick' (transiente Last/Spikes).",
    )

    monitor_engine_port: int = Field(default=8110, alias="MONITOR_ENGINE_PORT")
    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")

    monitor_interval_sec: int = Field(default=10, alias="MONITOR_INTERVAL_SEC")
    monitor_alert_dedupe_sec: int = Field(default=300, alias="MONITOR_ALERT_DEDUPE_SEC")
    monitor_enable_prometheus: bool = Field(default=True, alias="MONITOR_ENABLE_PROMETHEUS")

    monitor_service_urls_raw: str = Field(
        default=(
            "api-gateway=http://localhost:8000,"
            "market-stream=http://localhost:8010,"
            "feature-engine=http://localhost:8020,"
            "structure-engine=http://localhost:8030,"
            "drawing-engine=http://localhost:8040,"
            "signal-engine=http://localhost:8050,"
            "news-engine=http://localhost:8060,"
            "llm-orchestrator=http://localhost:8070,"
            "inference-server=http://localhost:8140/ready,"
            "paper-broker=http://localhost:8085,"
            "learning-engine=http://localhost:8090,"
            "alert-engine=http://localhost:8100,"
            "monitor-engine=http://localhost:8110,"
            "live-broker=http://localhost:8120,"
            "onchain-sniffer=http://localhost:8160,"
            "audit-ledger=http://localhost:8180,"
            "adversarial-engine=http://localhost:8220"
        ),
        alias="MONITOR_SERVICE_URLS",
    )
    monitor_incident_rca_enabled: bool = Field(
        default=True,
        alias="MONITOR_INCIDENT_RCA_ENABLED",
        description="P79: global_halt -> Post-Mortem + LLM + optional Telegram",
    )
    monitor_incident_rca_debounce_sec: int = Field(
        default=120,
        ge=0,
        le=86_400,
        alias="MONITOR_INCIDENT_RCA_DEBOUNCE_SEC",
        description="Mindestabstand zwischen zwei auto Post-Mortems (gleicher Latch-Flanke 0->1).",
    )
    monitor_incident_rca_global_budget_sec: float = Field(
        default=9.0,
        ge=2.0,
        le=60.0,
        alias="MONITOR_INCIDENT_RCA_GLOBAL_BUDGET_SEC",
        description="Gesamtbudget fuer Event-Sampling+Health+LLM im Async-Lauf (DoD ~10s).",
    )
    monitor_llm_orchestrator_url: str = Field(
        default="http://localhost:8070",
        alias="MONITOR_LLM_ORCHESTRATOR_URL",
    )
    monitor_alert_engine_url: str = Field(
        default="http://localhost:8100",
        alias="MONITOR_ALERT_ENGINE_URL",
    )
    monitor_telegram_post_mortem_enabled: bool = Field(
        default=True,
        alias="MONITOR_TELEGRAM_POST_MORTEM_ENABLED",
        description="POST /admin/test-alert benoetigt ADMIN_TOKEN + X-Internal-Service-Key",
    )
    monitor_streams_raw: str = Field(
        default=(
            "events:signal_created,events:trade_opened,events:trade_updated,"
            "events:trade_closed,events:candle_close,events:news_scored,"
            "events:market_feed_health,events:system_alert,events:dlq"
        ),
        alias="MONITOR_STREAMS",
    )
    monitor_stream_groups_raw: str = Field(
        default=(
            "signal-engine,feature-engine,structure-engine,drawing-engine,"
            "paper-broker,learning-engine,alert-engine,monitor-engine,live-broker"
        ),
        alias="MONITOR_STREAM_GROUPS",
    )

    symbol: str = Field(default="", alias="MONITOR_SYMBOL")

    thresh_stale_ms_1m: int = Field(default=180_000, alias="THRESH_STALE_MS_1M")
    thresh_stale_ms_5m: int = Field(default=600_000, alias="THRESH_STALE_MS_5M")
    thresh_stale_ms_15m: int = Field(default=1_800_000, alias="THRESH_STALE_MS_15M")
    thresh_stale_ms_1h: int = Field(default=7_200_000, alias="THRESH_STALE_MS_1H")
    thresh_stale_ms_4h: int = Field(default=28_800_000, alias="THRESH_STALE_MS_4H")

    thresh_stale_signals_ms: int = Field(default=600_000, alias="THRESH_STALE_SIGNALS_MS")
    thresh_stale_drawings_ms: int = Field(default=600_000, alias="THRESH_STALE_DRAWINGS_MS")
    thresh_stale_news_ms: int = Field(default=3_600_000, alias="THRESH_STALE_NEWS_MS")
    thresh_stale_llm_ms: int = Field(default=900_000, alias="THRESH_STALE_LLM_MS")
    thresh_stale_funding_ms: int = Field(default=3_600_000, alias="THRESH_STALE_FUNDING_MS")
    thresh_stale_oi_ms: int = Field(default=3_600_000, alias="THRESH_STALE_OI_MS")

    thresh_pending_max: int = Field(default=1000, alias="THRESH_PENDING_MAX")
    thresh_lag_max: int = Field(default=5000, alias="THRESH_LAG_MAX")
    thresh_dlq_len_warn: int = Field(default=50, alias="THRESH_DLQ_LEN_WARN")
    thresh_dlq_len_crit: int = Field(default=200, alias="THRESH_DLQ_LEN_CRIT")
    thresh_live_reconcile_stale_ms: int = Field(
        default=90_000,
        alias="THRESH_LIVE_RECONCILE_STALE_MS",
    )
    thresh_live_error_lookback_ms: int = Field(
        default=900_000,
        alias="THRESH_LIVE_ERROR_LOOKBACK_MS",
    )
    thresh_live_kill_switch_age_ms: int = Field(
        default=300_000,
        alias="THRESH_LIVE_KILL_SWITCH_AGE_MS",
    )

    monitor_trading_sql_alerts_enabled: bool = Field(
        default=True,
        alias="MONITOR_TRADING_SQL_ALERTS_ENABLED",
        description="Zusaetzliche ops.alerts aus SQL-SLOs (No-Trade-Spike, Stop-Fragilitaet, Outbox, Drift).",
    )
    monitor_min_signals_for_do_not_trade_ratio: int = Field(
        default=8,
        ge=1,
        le=50_000,
        alias="MONITOR_MIN_SIGNALS_FOR_DO_NOT_TRADE_RATIO",
    )
    thresh_signal_do_not_trade_ratio_warn: float = Field(
        default=0.82,
        ge=0.0,
        le=1.0,
        alias="THRESH_SIGNAL_DO_NOT_TRADE_RATIO_WARN",
    )
    thresh_stop_fragility_p90_warn: float = Field(
        default=0.78,
        ge=0.0,
        le=1.0,
        alias="THRESH_STOP_FRAGILITY_P90_WARN",
    )
    thresh_signal_router_switches_24h_warn: int = Field(
        default=12,
        ge=1,
        le=1_000_000,
        alias="THRESH_SIGNAL_ROUTER_SWITCHES_24H_WARN",
    )
    thresh_signal_specialist_disagreement_ratio_warn: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        alias="THRESH_SIGNAL_SPECIALIST_DISAGREEMENT_RATIO_WARN",
    )
    thresh_alert_outbox_failed_warn: int = Field(
        default=3,
        ge=1,
        le=1_000_000,
        alias="THRESH_ALERT_OUTBOX_FAILED_WARN",
    )
    thresh_telegram_operator_errors_24h_warn: int = Field(
        default=2,
        ge=1,
        le=1_000_000,
        alias="THRESH_TELEGRAM_OPERATOR_ERRORS_24H_WARN",
    )
    thresh_gateway_auth_failures_1h_warn: int = Field(
        default=10,
        ge=1,
        le=1_000_000,
        alias="THRESH_GATEWAY_AUTH_FAILURES_1H_WARN",
    )
    thresh_reconcile_drift_total_warn: int = Field(
        default=5,
        ge=1,
        le=1_000_000,
        alias="THRESH_RECONCILE_DRIFT_TOTAL_WARN",
    )

    @model_validator(mode="after")
    def _derive_monitor_symbol(self) -> "MonitorEngineSettings":
        if not self.symbol:
            object.__setattr__(self, "symbol", self.default_operational_symbol())
        if not self.symbol:
            raise ValueError(
                "MONITOR_SYMBOL fehlt und konnte nicht aus Watchlist/Universe/Allowlist abgeleitet werden"
            )
        w = float(self.monitor_heartbeat_stale_warn_sec)
        d = float(self.monitor_heartbeat_stale_degrade_sec)
        if w >= d:
            raise ValueError(
                "MONITOR_HEARTBEAT_STALE_WARN_SEC must be < MONITOR_HEARTBEAT_STALE_DEGRADE_SEC"
            )
        crit = float(self.monitor_self_healing_heartbeat_crit_sec)
        if crit <= d:
            raise ValueError(
                "MONITOR_SELF_HEALING_HEARTBEAT_CRIT_SEC muss > MONITOR_HEARTBEAT_STALE_DEGRADE_SEC"
            )
        return self

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    eventbus_dedupe_ttl_sec: int = Field(default=0, alias="EVENTBUS_DEDUPE_TTL_SEC")

    monitor_self_healing_coordinator_enabled: bool = Field(
        default=True,
        alias="MONITOR_SELF_HEALING_COORDINATOR_ENABLED",
        description="Automatische Recovery-Requests (stateless Worker) im Scheduler-Tick.",
    )
    monitor_self_healing_stateless_services: str = Field(
        default="feature-engine,drawing-engine,signal-engine",
        alias="MONITOR_SELF_HEALING_STATELESS",
        description="CSV; bei CRITICAL-Checks RECOVERY_REQUEST + optional Restart-Stub.",
    )
    monitor_self_healing_heartbeat_crit_sec: float = Field(
        default=300.0,
        ge=30.0,
        le=7200.0,
        alias="MONITOR_SELF_HEALING_HEARTBEAT_CRIT_SEC",
        description=(
            "Ab dieser Heartbeat-Alter in Sekunden gilt Auto-Healing als kritisch "
            "(5 Min. wie Audit-Vorgabe). Groesser als DEGRADE-Grace, sonst sinnlos."
        ),
    )
    monitor_self_healing_max_restarts_per_hour: int = Field(
        default=3,
        ge=1,
        le=10,
        alias="MONITOR_SELF_HEALING_MAX_RESTARTS_PER_HOUR",
    )
    monitor_self_healing_restarter_mode: str = Field(
        default="mock",
        alias="MONITOR_SELF_HEALING_RESTARTER_MODE",
        description="mock | docker | compose_exec (siehe ServiceRestarter).",
    )
    monitor_self_healing_docker_name_map: str = Field(
        default="",
        alias="MONITOR_SELF_HEALING_DOCKER_NAME_MAP",
        description="Optional: CSV feature-engine=fe_svc,... fuer Docker/compose.",
    )
    monitor_self_healing_canary_enabled: bool = Field(
        default=False,
        alias="MONITOR_SELF_HEALING_CANARY_ENABLED",
        description=(
            "Simuliert CRITICAL_RUNTIME_EXCEPTION (falscher REST-Pfad) fuer Self-Healing-Tests. "
            "In Produktion aus lassen."
        ),
    )

    @property
    def service_urls(self) -> dict[str, str]:
        return _parse_service_urls(self.monitor_service_urls_raw)

    @property
    def streams(self) -> list[str]:
        return _split_csv(self.monitor_streams_raw)

    @property
    def stream_groups(self) -> list[str]:
        return _split_csv(self.monitor_stream_groups_raw)
