from __future__ import annotations

from typing import ClassVar, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from config.settings import BaseServiceSettings, TriggerType
from shared_py.bitget import BitgetSettings
from shared_py.shadow_live_divergence import ShadowLiveThresholds
from shared_py.eventbus import (
    EVENT_STREAMS,
    STREAM_SIGNAL_CREATED,
    STREAM_TRADE_CLOSED,
    STREAM_TRADE_OPENED,
    STREAM_TRADE_UPDATED,
)

_DEFAULT_REFERENCE_STREAMS = ",".join(
    (STREAM_TRADE_OPENED, STREAM_TRADE_UPDATED, STREAM_TRADE_CLOSED)
)


def _split_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


class LiveBrokerSettings(BitgetSettings):
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

    database_url: str = Field(default="", alias="DATABASE_URL")
    redis_url: str = Field(default="", alias="REDIS_URL")
    live_broker_port: int = Field(default=8120, alias="LIVE_BROKER_PORT")
    live_broker_consumer_group: str = Field(
        default="live-broker",
        alias="LIVE_BROKER_CONSUMER_GROUP",
    )
    live_broker_consumer_name: str = Field(
        default="lb-1",
        alias="LIVE_BROKER_CONSUMER_NAME",
    )
    live_broker_signal_stream: str = Field(
        default=STREAM_SIGNAL_CREATED,
        alias="LIVE_BROKER_SIGNAL_STREAM",
    )
    live_broker_reference_streams_raw: str = Field(
        default=_DEFAULT_REFERENCE_STREAMS,
        alias="LIVE_BROKER_REFERENCE_STREAMS",
    )
    order_idempotency_prefix: str = Field(
        default="bgai",
        alias="ORDER_IDEMPOTENCY_PREFIX",
    )
    live_broker_http_timeout_sec: float = Field(
        default=10.0,
        alias="LIVE_BROKER_HTTP_TIMEOUT_SEC",
    )
    live_broker_http_max_retries: int = Field(
        default=2,
        alias="LIVE_BROKER_HTTP_MAX_RETRIES",
    )
    live_broker_http_retry_base_sec: float = Field(
        default=0.25,
        alias="LIVE_BROKER_HTTP_RETRY_BASE_SEC",
    )
    live_broker_http_retry_max_sec: float = Field(
        default=2.0,
        alias="LIVE_BROKER_HTTP_RETRY_MAX_SEC",
    )
    live_broker_circuit_fail_threshold: int = Field(
        default=3,
        alias="LIVE_BROKER_CIRCUIT_FAIL_THRESHOLD",
    )
    live_broker_circuit_open_sec: int = Field(
        default=30,
        alias="LIVE_BROKER_CIRCUIT_OPEN_SEC",
    )
    live_broker_server_time_sync_sec: int = Field(
        default=20,
        alias="LIVE_BROKER_SERVER_TIME_SYNC_SEC",
    )
    live_broker_server_time_max_skew_ms: int = Field(
        default=5000,
        alias="LIVE_BROKER_SERVER_TIME_MAX_SKEW_MS",
    )
    live_broker_private_ws_stale_after_sec: int = Field(
        default=90,
        alias="LIVE_BROKER_PRIVATE_WS_STALE_AFTER_SEC",
        description=(
            "Kein privates WS-Datenpush innerhalb dieser Sekunden → Stale-Eskalation und REST-Catchup."
        ),
    )
    live_broker_private_ws_stale_escalation_max_cycles: int = Field(
        default=10,
        alias="LIVE_BROKER_PRIVATE_WS_STALE_ESCALATION_MAX_CYCLES",
        description="Nach so vielen Stale-Zyklen ohne Erholung: Verbindung neu aufbauen.",
    )
    live_order_timeout_sec: int = Field(
        default=300,
        alias="LIVE_ORDER_TIMEOUT_SEC",
    )
    live_broker_rest_catchup_on_ws_connect: bool = Field(
        default=True,
        alias="LIVE_BROKER_REST_CATCHUP_ON_WS_CONNECT",
    )
    live_broker_rest_catchup_on_worker_start: bool = Field(
        default=True,
        alias="LIVE_BROKER_REST_CATCHUP_ON_WORKER_START",
    )
    live_broker_rest_catchup_max_age_sec: int = Field(
        default=180,
        alias="LIVE_BROKER_REST_CATCHUP_MAX_AGE_SEC",
    )
    live_reconcile_order_ack_stale_sec: int = Field(
        default=120,
        alias="LIVE_RECONCILE_ORDER_ACK_STALE_SEC",
    )
    live_reconcile_private_ws_stale_sec: int = Field(
        default=300,
        alias="LIVE_RECONCILE_PRIVATE_WS_STALE_SEC",
    )
    live_reconcile_journal_tail_limit: int = Field(
        default=200,
        alias="LIVE_RECONCILE_JOURNAL_TAIL_LIMIT",
    )
    live_reconcile_missing_exchange_ack_degrades: bool = Field(
        default=True,
        alias="LIVE_RECONCILE_MISSING_EXCHANGE_ACK_DEGRADES",
    )
    live_reconcile_fill_drift_degrades: bool = Field(
        default=False,
        alias="LIVE_RECONCILE_FILL_DRIFT_DEGRADES",
    )
    live_reconcile_ws_stale_contributes_to_drift: bool = Field(
        default=False,
        alias="LIVE_RECONCILE_WS_STALE_DEGRADES",
    )
    live_reconcile_rest_catchup_on_ws_stale: bool = Field(
        default=False,
        alias="LIVE_RECONCILE_REST_CATCHUP_ON_WS_STALE",
    )
    live_broker_block_live_without_exchange_truth: bool = Field(
        default=False,
        alias="LIVE_BROKER_BLOCK_LIVE_WITHOUT_EXCHANGE_TRUTH",
    )
    live_safety_latch_on_reconcile_fail: bool = Field(
        default=True,
        alias="LIVE_SAFETY_LATCH_ON_RECONCILE_FAIL",
    )
    live_order_replace_enabled: bool = Field(
        default=True,
        alias="LIVE_ORDER_REPLACE_ENABLED",
    )
    live_exits_enabled: bool = Field(default=True, alias="LIVE_EXITS_ENABLED")
    live_require_execution_binding: bool = Field(
        default=False,
        alias="LIVE_REQUIRE_EXECUTION_BINDING",
    )
    live_preflight_max_catalog_metadata_age_sec: int = Field(
        default=0,
        alias="LIVE_PREFLIGHT_MAX_CATALOG_METADATA_AGE_SEC",
    )
    live_execution_max_spread_half_bps_market: float | None = Field(
        default=None,
        alias="LIVE_EXECUTION_MAX_SPREAD_HALF_BPS_MARKET",
    )
    live_predatory_passive_maker_default: bool = Field(
        default=False,
        alias="LIVE_PREDATORY_PASSIVE_MAKER_DEFAULT",
        description=(
            "Signal-Events: trace.predatory_passive_maker setzen (Market-Opens werden "
            "im Order-Service zu post-only Limit am Best-Bid/Ask umgeschrieben, Futures)."
        ),
    )
    live_passive_max_slippage_bps_default: float = Field(
        default=25.0,
        alias="LIVE_PASSIVE_MAX_SLIPPAGE_BPS_DEFAULT",
        description="Max. Abweichung vom Anchor-Preis fuer Chase-Replace (Basis-Punkte).",
    )
    live_passive_iceberg_slices_default: int = Field(
        default=4,
        alias="LIVE_PASSIVE_ICEBERG_SLICES_DEFAULT",
        ge=1,
        le=500,
        description="Anzahl Tranchen (nur erste wird pro Submit platziert; Plan im Trace).",
    )
    live_passive_imbalance_pause_ms: int = Field(
        default=400,
        alias="LIVE_PASSIVE_IMBALANCE_PAUSE_MS",
        ge=0,
        le=60_000,
        description="Hinweis-Dauer im Fehlertext wenn Safety-Latch Orderbuch-Wall erkennt.",
    )
    live_passive_imbalance_against_threshold: float = Field(
        default=0.55,
        alias="LIVE_PASSIVE_IMBALANCE_AGAINST_THRESHOLD",
        description="|Imbalance| groesser als Schwelle gegen unsere Seite -> kein Submit (retry).",
    )
    live_preset_stop_min_distance_bps: float | None = Field(
        default=None,
        alias="LIVE_PRESET_STOP_MIN_DISTANCE_BPS",
    )
    live_preset_stop_min_spread_mult: float | None = Field(
        default=None,
        alias="LIVE_PRESET_STOP_MIN_SPREAD_MULT",
    )
    live_block_submit_on_reconcile_fail: bool = Field(
        default=True,
        alias="LIVE_BLOCK_SUBMIT_ON_RECONCILE_FAIL",
    )
    live_block_submit_on_reconcile_degraded: bool = Field(
        default=False,
        alias="LIVE_BLOCK_SUBMIT_ON_RECONCILE_DEGRADED",
    )
    live_require_exchange_position_for_reduce_only: bool = Field(
        default=True,
        alias="LIVE_REQUIRE_EXCHANGE_POSITION_FOR_REDUCE_ONLY",
    )
    live_probe_public_api_before_order_submit: bool = Field(
        default=False,
        alias="LIVE_PROBE_PUBLIC_API_BEFORE_ORDER_SUBMIT",
    )
    live_safety_latch_on_duplicate_recovery_fail: bool = Field(
        default=False,
        alias="LIVE_SAFETY_LATCH_ON_DUPLICATE_RECOVERY_FAIL",
    )
    live_operator_intel_outbox_enabled: bool = Field(
        default=False,
        alias="LIVE_OPERATOR_INTEL_OUTBOX_ENABLED",
        description="Publiziert operator_intel Events (Telegram via alert-engine Outbox)",
    )
    stop_trigger_type_default: TriggerType = Field(
        default="mark_price",
        alias="STOP_TRIGGER_TYPE_DEFAULT",
    )
    tp_trigger_type_default: TriggerType = Field(
        default="fill_price",
        alias="TP_TRIGGER_TYPE_DEFAULT",
    )
    tp1_pct: str = Field(default="0.30", alias="TP1_PCT")
    tp2_pct: str = Field(default="0.30", alias="TP2_PCT")
    tp3_pct: str = Field(default="0.40", alias="TP3_PCT")
    runner_trail_atr_mult: str = Field(default="1.0", alias="RUNNER_TRAIL_ATR_MULT")
    exit_break_even_after_tp_index: int = Field(
        default=0,
        alias="EXIT_BREAK_EVEN_AFTER_TP_INDEX",
    )
    exit_runner_enabled: bool = Field(default=True, alias="EXIT_RUNNER_ENABLED")
    eventbus_dedupe_ttl_sec: int = Field(default=0, alias="EVENTBUS_DEDUPE_TTL_SEC")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    require_shadow_match_before_live: bool = Field(
        default=False,
        alias="REQUIRE_SHADOW_MATCH_BEFORE_LIVE",
    )
    shadow_live_max_timing_skew_ms: int = Field(
        default=180_000,
        alias="SHADOW_LIVE_MAX_TIMING_SKEW_MS",
    )
    shadow_live_max_leverage_delta: int = Field(
        default=0,
        alias="SHADOW_LIVE_MAX_LEVERAGE_DELTA",
    )
    shadow_live_max_signal_shadow_divergence_0_1: float = Field(
        default=0.15,
        alias="SHADOW_LIVE_MAX_SIGNAL_SHADOW_DIVERGENCE_0_1",
    )
    shadow_live_timing_violation_hard: bool = Field(
        default=False,
        alias="SHADOW_LIVE_TIMING_VIOLATION_HARD",
    )
    shadow_live_max_slippage_expectation_bps: float | None = Field(
        default=None,
        alias="SHADOW_LIVE_MAX_SLIPPAGE_EXPECTATION_BPS",
    )
    billing_prepaid_gate_enabled: bool = Field(
        default=False,
        alias="BILLING_PREPAID_GATE_ENABLED",
        description="Opening-Orders nur bei ausreichendem app.customer_wallet (Tenant).",
    )
    billing_prepaid_tenant_id: str = Field(
        default="default",
        alias="BILLING_PREPAID_TENANT_ID",
    )
    billing_min_balance_new_trade_usd: str = Field(
        default="50",
        alias="BILLING_MIN_BALANCE_NEW_TRADE_USD",
    )
    modul_mate_gate_enforcement: bool = Field(
        default=False,
        alias="MODUL_MATE_GATE_ENFORCEMENT",
        description=(
            "Vor Exchange-Submit: app.tenant_modul_mate_gates pruefen "
            "(Demo vs. Live laut product_policy)."
        ),
    )
    modul_mate_gate_tenant_id: str = Field(
        default="default",
        alias="MODUL_MATE_GATE_TENANT_ID",
    )
    live_broker_require_commercial_gates: bool = Field(
        default=True,
        alias="LIVE_BROKER_REQUIRE_COMMERCIAL_GATES",
        description=(
            "Wenn true: vor Exchange-Submit immer app.tenant_modul_mate_gates pruefen "
            "(zusaetzlich oder statt MODUL_MATE_GATE_ENFORCEMENT). "
            "Production mit Live-Submit sollte nicht beides auf false setzen."
        ),
    )

    @property
    def commercial_gates_enforced_for_exchange_submit(self) -> bool:
        """True wenn Tenant-Kommerzgates vor Boersen-Submit geladen werden muessen."""
        return bool(
            self.modul_mate_gate_enforcement or self.live_broker_require_commercial_gates
        )

    @field_validator("shadow_live_max_slippage_expectation_bps", mode="before")
    @classmethod
    def _empty_slippage_cap(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @field_validator(
        "live_execution_max_spread_half_bps_market",
        "live_preset_stop_min_distance_bps",
        "live_preset_stop_min_spread_mult",
        mode="before",
    )
    @classmethod
    def _empty_optional_float_guard(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @field_validator("live_preflight_max_catalog_metadata_age_sec")
    @classmethod
    def _metadata_age_sec(cls, value: int) -> int:
        if value < 0 or value > 86_400:
            raise ValueError("LIVE_PREFLIGHT_MAX_CATALOG_METADATA_AGE_SEC muss 0..86400 sein")
        return value

    @field_validator(
        "live_execution_max_spread_half_bps_market",
        "live_preset_stop_min_distance_bps",
        "live_preset_stop_min_spread_mult",
    )
    @classmethod
    def _optional_positive_guards(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if value <= 0 or value > 1_000_000:
            raise ValueError("Execution-Guard-Schwellen muessen NULL oder > 0 und plausibel sein")
        return value

    @field_validator("live_broker_port")
    @classmethod
    def _port(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("LIVE_BROKER_PORT ungueltig")
        return value

    @field_validator(
        "live_broker_consumer_group",
        "live_broker_consumer_name",
        "live_broker_reference_streams_raw",
        "order_idempotency_prefix",
        mode="before",
    )
    @classmethod
    def _strip_string_fields(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("live_broker_signal_stream", mode="before")
    @classmethod
    def _normalize_signal_stream(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("live_broker_signal_stream")
    @classmethod
    def _validate_signal_stream(cls, value: str) -> str:
        if value not in EVENT_STREAMS:
            raise ValueError("LIVE_BROKER_SIGNAL_STREAM ist kein gueltiger Event-Stream")
        return value

    @field_validator("order_idempotency_prefix")
    @classmethod
    def _validate_order_prefix(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("ORDER_IDEMPOTENCY_PREFIX darf nicht leer sein")
        if len(normalized) > 13:
            raise ValueError("ORDER_IDEMPOTENCY_PREFIX darf max. 13 Zeichen lang sein")
        if any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-" for ch in normalized):
            raise ValueError(
                "ORDER_IDEMPOTENCY_PREFIX erlaubt nur a-z, 0-9 und '-'"
            )
        return normalized

    @field_validator("stop_trigger_type_default", "tp_trigger_type_default")
    @classmethod
    def _validate_trigger_types(cls, value: TriggerType) -> TriggerType:
        if value not in ("mark_price", "fill_price"):
            raise ValueError("Trigger-Typ muss mark_price oder fill_price sein")
        return value

    @field_validator("live_broker_http_timeout_sec")
    @classmethod
    def _validate_http_timeout(cls, value: float) -> float:
        if value <= 0 or value > 60:
            raise ValueError("LIVE_BROKER_HTTP_TIMEOUT_SEC muss > 0 und <= 60 sein")
        return value

    @field_validator("live_broker_http_max_retries")
    @classmethod
    def _validate_http_max_retries(cls, value: int) -> int:
        if value < 0 or value > 5:
            raise ValueError("LIVE_BROKER_HTTP_MAX_RETRIES muss im Bereich 0..5 liegen")
        return value

    @field_validator(
        "live_broker_http_retry_base_sec",
        "live_broker_http_retry_max_sec",
    )
    @classmethod
    def _validate_retry_window(cls, value: float) -> float:
        if value <= 0 or value > 60:
            raise ValueError("Retry-Intervalle muessen > 0 und <= 60 sein")
        return value

    @field_validator("live_broker_circuit_fail_threshold")
    @classmethod
    def _validate_circuit_fail_threshold(cls, value: int) -> int:
        if value < 1 or value > 20:
            raise ValueError("LIVE_BROKER_CIRCUIT_FAIL_THRESHOLD muss 1..20 sein")
        return value

    @field_validator("live_broker_circuit_open_sec", "live_broker_server_time_sync_sec")
    @classmethod
    def _validate_positive_seconds(cls, value: int) -> int:
        if value < 1 or value > 300:
            raise ValueError("Sekundenwerte muessen im Bereich 1..300 liegen")
        return value

    @field_validator("live_broker_server_time_max_skew_ms")
    @classmethod
    def _validate_time_skew(cls, value: int) -> int:
        if value < 100 or value > 30_000:
            raise ValueError(
                "LIVE_BROKER_SERVER_TIME_MAX_SKEW_MS muss im Bereich 100..30000 liegen"
            )
        return value

    @field_validator("live_broker_private_ws_stale_after_sec")
    @classmethod
    def _validate_private_ws_stale_sec(cls, value: int) -> int:
        if value < 20 or value > 600:
            raise ValueError("LIVE_BROKER_PRIVATE_WS_STALE_AFTER_SEC muss 20..600 sein")
        return value

    @field_validator("live_broker_private_ws_stale_escalation_max_cycles")
    @classmethod
    def _validate_private_ws_stale_cycles(cls, value: int) -> int:
        if value < 2 or value > 30:
            raise ValueError(
                "LIVE_BROKER_PRIVATE_WS_STALE_ESCALATION_MAX_CYCLES muss 2..30 sein"
            )
        return value

    @field_validator("live_order_timeout_sec")
    @classmethod
    def _validate_order_timeout(cls, value: int) -> int:
        if value < 0 or value > 86_400:
            raise ValueError("LIVE_ORDER_TIMEOUT_SEC muss im Bereich 0..86400 liegen")
        return value

    @field_validator("tp1_pct", "tp2_pct", "tp3_pct", "runner_trail_atr_mult")
    @classmethod
    def _validate_positive_decimal_strings(cls, value: str) -> str:
        normalized = value.strip()
        if float(normalized) <= 0:
            raise ValueError("Exit-Schwellen muessen > 0 sein")
        return normalized

    @field_validator("exit_break_even_after_tp_index")
    @classmethod
    def _validate_break_even_index(cls, value: int) -> int:
        if value < 0 or value > 2:
            raise ValueError("EXIT_BREAK_EVEN_AFTER_TP_INDEX muss im Bereich 0..2 liegen")
        return value

    @field_validator("shadow_live_max_timing_skew_ms")
    @classmethod
    def _validate_shadow_timing_skew(cls, value: int) -> int:
        if value < 5_000 or value > 3_600_000:
            raise ValueError("SHADOW_LIVE_MAX_TIMING_SKEW_MS muss 5000..3600000 sein")
        return value

    @field_validator("shadow_live_max_leverage_delta")
    @classmethod
    def _validate_shadow_lev_delta(cls, value: int) -> int:
        if value < 0 or value > 20:
            raise ValueError("SHADOW_LIVE_MAX_LEVERAGE_DELTA muss 0..20 sein")
        return value

    @field_validator("shadow_live_max_signal_shadow_divergence_0_1")
    @classmethod
    def _validate_shadow_div(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("SHADOW_LIVE_MAX_SIGNAL_SHADOW_DIVERGENCE_0_1 muss 0..1 sein")
        return value

    @field_validator("shadow_live_max_slippage_expectation_bps")
    @classmethod
    def _validate_shadow_slip_cap(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if value <= 0 or value > 500:
            raise ValueError("SHADOW_LIVE_MAX_SLIPPAGE_EXPECTATION_BPS muss NULL oder 0..500 sein")
        return value

    @field_validator("live_broker_base_url")
    @classmethod
    def _validate_base_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            return normalized
        if not (
            normalized.startswith("http://") or normalized.startswith("https://")
        ):
            raise ValueError(
                "LIVE_BROKER_BASE_URL muss mit http:// oder https:// beginnen"
            )
        return normalized.rstrip("/")

    @field_validator("live_broker_ws_private_url")
    @classmethod
    def _validate_ws_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            return normalized
        if not (
            normalized.startswith("ws://") or normalized.startswith("wss://")
        ):
            raise ValueError(
                "LIVE_BROKER_WS_PRIVATE_URL muss mit ws:// oder wss:// beginnen"
            )
        return normalized

    @model_validator(mode="after")
    def _validate_reference_streams(self) -> Self:
        if not self.live_broker_consumer_group:
            raise ValueError("LIVE_BROKER_CONSUMER_GROUP darf nicht leer sein")
        if not self.live_broker_consumer_name:
            raise ValueError("LIVE_BROKER_CONSUMER_NAME darf nicht leer sein")
        if self.live_broker_http_retry_base_sec > self.live_broker_http_retry_max_sec:
            raise ValueError(
                "LIVE_BROKER_HTTP_RETRY_BASE_SEC darf nicht groesser als "
                "LIVE_BROKER_HTTP_RETRY_MAX_SEC sein"
            )
        reference_streams = self.reference_streams
        if not reference_streams:
            raise ValueError("LIVE_BROKER_REFERENCE_STREAMS darf nicht leer sein")
        invalid = [stream for stream in reference_streams if stream not in EVENT_STREAMS]
        if invalid:
            raise ValueError(
                f"LIVE_BROKER_REFERENCE_STREAMS enthaelt ungueltige Streams: {invalid}"
            )
        if self.live_broker_signal_stream in reference_streams:
            raise ValueError(
                "LIVE_BROKER_SIGNAL_STREAM darf nicht zusaetzlich in "
                "LIVE_BROKER_REFERENCE_STREAMS auftauchen"
            )
        if self.live_trade_enable and not self.live_broker_enabled:
            raise ValueError(
                "LIVE_BROKER_ENABLED muss true sein, wenn LIVE_TRADE_ENABLE=true"
            )
        if self.live_trade_enable and self.execution_mode != "live":
            raise ValueError(
                "LIVE_TRADE_ENABLE=true ist nur mit EXECUTION_MODE=live erlaubt"
            )
        if self.private_exchange_access_enabled and (
            not self.effective_api_key
            or not self.effective_api_secret
            or not self.effective_api_passphrase
        ):
            raise ValueError(
                "BITGET API Credentials muessen gesetzt sein, wenn "
                "SHADOW_TRADE_ENABLE oder LIVE_TRADE_ENABLE aktiv ist"
            )
        age = self.live_broker_rest_catchup_max_age_sec
        if age < 30 or age > 3600:
            raise ValueError("LIVE_BROKER_REST_CATCHUP_MAX_AGE_SEC muss 30..3600 sein")
        ack = self.live_reconcile_order_ack_stale_sec
        if ack < 10 or ack > 3600:
            raise ValueError("LIVE_RECONCILE_ORDER_ACK_STALE_SEC muss 10..3600 sein")
        wst = self.live_reconcile_private_ws_stale_sec
        if wst < 30 or wst > 7200:
            raise ValueError("LIVE_RECONCILE_PRIVATE_WS_STALE_SEC muss 30..7200 sein")
        jlim = self.live_reconcile_journal_tail_limit
        if jlim < 20 or jlim > 2000:
            raise ValueError("LIVE_RECONCILE_JOURNAL_TAIL_LIMIT muss 20..2000 sein")
        if (self.production or self.app_env == "production") and self.bitget_demo_enabled:
            raise ValueError(
                "BITGET_DEMO_ENABLED=true ist fuer PRODUCTION / APP_ENV=production "
                "nicht zulaessig (Live-Broker: keine Demo/Paper-REST fuer Echtgeld-Pfad)"
            )
        if (self.production or self.app_env == "production") and self.bitget_relax_credential_isolation:
            raise ValueError(
                "BITGET_RELAX_CREDENTIAL_ISOLATION=true ist in Production nicht zulaessig"
            )
        if not self.bitget_relax_credential_isolation:
            if self.bitget_demo_enabled and self.private_exchange_access_enabled:
                if self.api_key or self.api_secret or self.api_passphrase:
                    raise ValueError(
                        "BITGET_DEMO_ENABLED=true mit privatem Exchange-Zugriff (Shadow/Live): "
                        "BITGET_API_KEY, BITGET_API_SECRET und BITGET_API_PASSPHRASE muessen leer sein "
                        "(keine Live-Credentials im Demo-Private-Pfad). "
                        "Ausnahme lokal: BITGET_RELAX_CREDENTIAL_ISOLATION=true."
                    )
            elif not self.bitget_demo_enabled and self.private_exchange_access_enabled:
                if self.demo_api_key or self.demo_api_secret or self.demo_api_passphrase:
                    raise ValueError(
                        "Private Exchange-Anbindung aktiv (Shadow/Live-Orders) ohne Demo-Modus: "
                        "BITGET_DEMO_API_KEY/SECRET/PASSPHRASE muessen leer sein — keine Demo-Keys im Live-Pfad. "
                        "Ausnahme lokal: BITGET_RELAX_CREDENTIAL_ISOLATION=true."
                    )
        if self.modul_mate_gate_enforcement and not (self.database_url or "").strip():
            raise ValueError(
                "MODUL_MATE_GATE_ENFORCEMENT=true erfordert eine gesetzte DATABASE_URL"
            )
        if self.live_broker_require_commercial_gates and not (self.database_url or "").strip():
            raise ValueError(
                "LIVE_BROKER_REQUIRE_COMMERCIAL_GATES=true erfordert eine gesetzte DATABASE_URL"
            )
        if (
            (self.production or self.app_env == "production")
            and self.live_order_submission_enabled
            and not self.bitget_demo_enabled
            and not self.commercial_gates_enforced_for_exchange_submit
        ):
            raise ValueError(
                "Production mit aktivem Live-Order-Submit: setze MODUL_MATE_GATE_ENFORCEMENT=true "
                "oder LIVE_BROKER_REQUIRE_COMMERCIAL_GATES=true (Tenant-Gates gegen Vertrag/Abo/Admin)."
            )
        return self

    @property
    def reference_streams(self) -> list[str]:
        return _split_csv(self.live_broker_reference_streams_raw)

    @property
    def allowed_symbols_set(self) -> set[str]:
        return {item.upper() for item in _split_csv(self.live_allowed_symbols)}

    @property
    def allowed_market_families_set(self) -> set[str]:
        return {item.lower() for item in _split_csv(self.live_allowed_market_families)}

    @property
    def allowed_product_types_set(self) -> set[str]:
        return {item.upper() for item in _split_csv(self.live_allowed_product_types)}

    def shadow_live_thresholds(self) -> ShadowLiveThresholds:
        return ShadowLiveThresholds(
            max_timing_skew_ms=self.shadow_live_max_timing_skew_ms,
            max_leverage_delta=self.shadow_live_max_leverage_delta,
            max_signal_shadow_divergence_0_1=self.shadow_live_max_signal_shadow_divergence_0_1,
            timing_violation_hard=self.shadow_live_timing_violation_hard,
            max_slippage_expectation_bps=self.shadow_live_max_slippage_expectation_bps,
        )
