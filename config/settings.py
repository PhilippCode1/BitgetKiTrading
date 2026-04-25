"""
Gemeinsame pydantic Settings fuer alle Python-Services (nur ENV, keine Secrets im Code).
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar, Literal, Self

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from config.paths import resolve_standard_env_files

LogFormat = Literal["json", "plain"]
VaultMode = Literal["false", "none", "hashicorp", "aws"]
AppEnv = Literal["local", "development", "shadow", "production", "test"]
ExecutionMode = Literal["paper", "bitget_demo", "shadow", "live"]
TradingRuntimeMode = ExecutionMode
StrategyExecutionMode = Literal["manual", "auto"]
ApiAuthMode = Literal["none", "api_key", "oauth2", "mtls"]
RiskDefaultAction = Literal["do_not_trade"]
ContractConfigMode = Literal["fixture", "live"]
TriggerType = Literal["mark_price", "fill_price"]
TelegramMode = Literal["getUpdates", "webhook"]
StrategyRegistryStatus = Literal["promoted", "candidate", "shadow", "retired"]

_PLACEHOLDER_MARKERS = (
    "<set_me>",
    "changeme",
    "example.com",
    "example.internal",
    "example.local",
    "replace_me",
)
_LOCAL_HOST_MARKERS = ("localhost", "127.0.0.1", "0.0.0.0")
_ALLOWED_MARKET_FAMILIES = ("spot", "margin", "futures")
_ALLOWED_MARGIN_ACCOUNT_MODES = ("cash", "isolated", "crossed")
_ALLOWED_FUTURES_PRODUCT_TYPES = ("USDT-FUTURES", "USDC-FUTURES", "COIN-FUTURES")
_DEFAULT_SCOPE_TIMEFRAMES = ("1m", "5m", "15m", "1H", "4H")

# Mindestlaenge fuer Kernsecrets bei PRODUCTION=true (Fail-Fast).
MIN_PRODUCTION_SECRET_LEN = 16


def _norm_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _norm_lower(value: Any) -> str:
    return _norm_str(value).lower()


def _is_blank_or_placeholder(value: str) -> bool:
    normalized = value.strip()
    if not normalized:
        return True
    lower = normalized.lower()
    if any(marker in lower for marker in _PLACEHOLDER_MARKERS):
        return True
    return False


def _contains_local_host(value: str) -> bool:
    lower = value.lower()
    return any(marker in lower for marker in _LOCAL_HOST_MARKERS)


def _iter_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _iter_csv_upper(value: str) -> list[str]:
    return [part.upper() for part in _iter_csv(value)]


def _iter_csv_lower(value: str) -> list[str]:
    return [part.lower() for part in _iter_csv(value)]


def _normalize_scope_timeframe(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    if raw.endswith("m") and raw[:-1].isdigit():
        return f"{int(raw[:-1])}m"
    upper = raw.upper()
    if upper.endswith(("H", "D", "W", "M")) and upper[:-1].isdigit():
        return f"{int(upper[:-1])}{upper[-1]}"
    raise ValueError(f"ungueltiges Scope-Timeframe: {value}")


class BaseServiceSettings(BaseSettings):
    """Kern-ENV: Produktion, Logging, Betriebsmodus, Risk, Auth und Secrets."""

    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        populate_by_name=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        dynamic_dotenv = DotEnvSettingsSource(
            settings_cls,
            env_file=resolve_standard_env_files(),
            env_file_encoding="utf-8",
        )
        # pydantic_settings merged mit state = deep_update(source_state, state): der bereits
        # gesammelte `state` ueberschreibt die aktuelle Quelle. Daher hat ein **frueheres**
        # Tuple-Element **hoehere** Prioritaet. Reihenfolge init -> OS-ENV -> Dotenv -> Secrets:
        # Compose/K8s-ENV schlaegt `.env.local`; leere OS-Variablen lassen Dotenv-Werte zu.
        return (
            init_settings,
            env_settings,
            dynamic_dotenv,
            file_secret_settings,
        )

    production_required_fields: ClassVar[tuple[str, ...]] = (
        "app_base_url",
        "frontend_url",
        "cors_allow_origins",
        "admin_token",
        "secret_key",
        "jwt_secret",
        "encryption_key",
    )
    production_required_non_local_fields: ClassVar[tuple[str, ...]] = (
        "app_base_url",
        "frontend_url",
        "cors_allow_origins",
    )

    production: bool = Field(default=False, alias="PRODUCTION")
    app_env: AppEnv = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: LogFormat = Field(default="plain", alias="LOG_FORMAT")

    vault_mode: VaultMode = Field(default="false", alias="VAULT_MODE")
    vault_addr: str = Field(default="", alias="VAULT_ADDR")
    vault_token: str = Field(default="", alias="VAULT_TOKEN")
    vault_role_id: str = Field(default="", alias="VAULT_ROLE_ID")
    vault_secret_id: str = Field(default="", alias="VAULT_SECRET_ID")
    kms_key_id: str = Field(default="", alias="KMS_KEY_ID")

    deploy_env: str = Field(default="development", alias="DEPLOY_ENV")
    deploy_script: str = Field(default="scripts/deploy.sh", alias="DEPLOY_SCRIPT")

    shadow_trade_enable: bool = Field(
        default=False,
        alias="SHADOW_TRADE_ENABLE",
        validation_alias=AliasChoices("SHADOW_TRADE_ENABLE", "ENABLE_SHADOW_MODE"),
    )
    enable_debug_metrics: bool = Field(default=False, alias="ENABLE_DEBUG_METRICS")

    worker_gc_interval_messages: int = Field(
        default=0,
        ge=0,
        le=10_000_000,
        alias="WORKER_GC_INTERVAL_MESSAGES",
        description=(
            "Optional: ``gc.collect()`` in synchronen Worker-Schleifen alle N Nachrichten "
            "(0=deaktiviert; fuer lange 24/7-Laeufe vorsichtig tunen)."
        ),
    )
    worker_gc_interval_async_loops: int = Field(
        default=0,
        ge=0,
        le=10_000_000,
        alias="WORKER_GC_INTERVAL_ASYNC_LOOPS",
        description=(
            "Optional: ``gc.collect()`` in periodischen asyncio-Schleifen alle N Iterationen "
            "(0=deaktiviert)."
        ),
    )

    app_name: str = Field(default="bitget-btc-ai", alias="APP_NAME")
    app_base_url: str = Field(default="", alias="APP_BASE_URL")
    frontend_url: str = Field(default="", alias="FRONTEND_URL")
    cors_allow_origins: str = Field(default="", alias="CORS_ALLOW_ORIGINS")

    database_url: str = Field(default="", alias="DATABASE_URL")
    redis_url: str = Field(default="", alias="REDIS_URL")
    database_url_docker: str = Field(default="", alias="DATABASE_URL_DOCKER")
    redis_url_docker: str = Field(default="", alias="REDIS_URL_DOCKER")
    use_docker_datastore_dsn: bool = Field(
        default=False,
        alias="BITGET_USE_DOCKER_DATASTORE_DSN",
    )

    readiness_require_urls_raw: str = Field(
        default="",
        alias="READINESS_REQUIRE_URLS",
        description="Kommagetrennte URLs (typisch .../ready); muessen JSON mit ready=true liefern.",
    )
    readiness_peer_timeout_sec: float = Field(
        default=2.5,
        ge=0.5,
        le=60.0,
        alias="READINESS_PEER_TIMEOUT_SEC",
    )

    execution_mode: ExecutionMode = Field(
        default="paper",
        alias="EXECUTION_MODE",
        validation_alias=AliasChoices("EXECUTION_MODE", "TRADING_RUNTIME_MODE"),
    )
    strategy_execution_mode: StrategyExecutionMode = Field(
        default="manual",
        alias="STRATEGY_EXEC_MODE",
    )
    api_auth_mode: ApiAuthMode = Field(
        default="none",
        alias="API_AUTH_MODE",
        validation_alias=AliasChoices("API_AUTH_MODE", "SECURITY_EDGE_AUTH_MODE"),
    )

    live_broker_enabled: bool = Field(default=False, alias="LIVE_BROKER_ENABLED")
    live_broker_base_url: str = Field(default="", alias="LIVE_BROKER_BASE_URL")
    live_broker_ws_private_url: str = Field(default="", alias="LIVE_BROKER_WS_PRIVATE_URL")
    live_trade_enable: bool = Field(
        default=False,
        alias="LIVE_TRADE_ENABLE",
        validation_alias=AliasChoices("LIVE_TRADE_ENABLE", "LIVE_ALLOW_ORDER_SUBMIT"),
    )
    live_reconcile_interval_sec: int = Field(default=15, alias="LIVE_RECONCILE_INTERVAL_SEC")
    live_kill_switch_enabled: bool = Field(default=True, alias="LIVE_KILL_SWITCH_ENABLED")
    instrument_catalog_refresh_interval_sec: int = Field(
        default=300,
        alias="INSTRUMENT_CATALOG_REFRESH_INTERVAL_SEC",
    )
    instrument_catalog_cache_ttl_sec: int = Field(
        default=900,
        alias="INSTRUMENT_CATALOG_CACHE_TTL_SEC",
    )
    instrument_catalog_max_stale_sec: int = Field(
        default=1800,
        alias="INSTRUMENT_CATALOG_MAX_STALE_SEC",
    )
    bitget_universe_market_families: str = Field(
        default="spot,margin,futures",
        alias="BITGET_UNIVERSE_MARKET_FAMILIES",
    )
    bitget_futures_allowed_product_types: str = Field(
        default="USDT-FUTURES,USDC-FUTURES,COIN-FUTURES",
        alias="BITGET_FUTURES_ALLOWED_PRODUCT_TYPES",
    )
    bitget_universe_symbols: str = Field(
        default="",
        alias="BITGET_UNIVERSE_SYMBOLS",
        validation_alias=AliasChoices("BITGET_UNIVERSE_SYMBOLS", "BITGET_DISCOVERY_SYMBOLS"),
    )
    bitget_watchlist_symbols: str = Field(
        default="",
        alias="BITGET_WATCHLIST_SYMBOLS",
    )
    feature_scope_symbols: str = Field(
        default="",
        alias="FEATURE_SCOPE_SYMBOLS",
    )
    feature_scope_timeframes: str = Field(
        default="1m,5m,15m,1H,4H",
        alias="FEATURE_SCOPE_TIMEFRAMES",
    )
    signal_scope_symbols: str = Field(
        default="",
        alias="SIGNAL_SCOPE_SYMBOLS",
    )
    bitget_spot_default_quote_coin: str = Field(
        default="USDT",
        alias="BITGET_SPOT_DEFAULT_QUOTE_COIN",
    )
    bitget_margin_default_quote_coin: str = Field(
        default="USDT",
        alias="BITGET_MARGIN_DEFAULT_QUOTE_COIN",
    )
    bitget_margin_default_account_mode: str = Field(
        default="isolated",
        alias="BITGET_MARGIN_DEFAULT_ACCOUNT_MODE",
    )
    bitget_margin_default_loan_type: str = Field(
        default="normal",
        alias="BITGET_MARGIN_DEFAULT_LOAN_TYPE",
    )
    bitget_futures_default_product_type: str = Field(
        default="",
        alias="BITGET_FUTURES_DEFAULT_PRODUCT_TYPE",
    )
    bitget_futures_default_margin_coin: str = Field(
        default="",
        alias="BITGET_FUTURES_DEFAULT_MARGIN_COIN",
    )
    live_allowed_symbols: str = Field(default="", alias="LIVE_ALLOWED_SYMBOLS")
    live_allowed_market_families: str = Field(
        default="",
        alias="LIVE_ALLOWED_MARKET_FAMILIES",
    )
    live_allowed_product_types: str = Field(
        default="",
        alias="LIVE_ALLOWED_PRODUCT_TYPES",
    )
    live_require_exchange_health: bool = Field(
        default=False,
        alias="LIVE_REQUIRE_EXCHANGE_HEALTH",
        description=(
            "Wenn true: Live-Broker/Reconcile blockiert ohne erreichbare Public-API. "
            "Shadow/Production explizit auf true setzen (.env.shadow / .env.production)."
        ),
    )
    live_require_operator_release_for_live_open: bool = Field(
        default=False,
        alias="LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN",
        description=(
            "Live-Opening-Orders nur nach auditiertem operator_release "
            "(Live-Broker; Gateway kann dasselbe ENV fuer Strict-Checks lesen)."
        ),
    )

    risk_hard_gating_enabled: bool = Field(default=True, alias="RISK_HARD_GATING_ENABLED")
    risk_allowed_leverage_min: int = Field(default=7, alias="RISK_ALLOWED_LEVERAGE_MIN")
    risk_allowed_leverage_max: int = Field(default=75, alias="RISK_ALLOWED_LEVERAGE_MAX")
    risk_elevated_leverage_live_ack: bool = Field(
        default=False,
        alias="RISK_ELEVATED_LEVERAGE_LIVE_ACK",
        description=(
            "Bei PRODUCTION + LIVE_TRADE_ENABLE: wenn RISK_ALLOWED_LEVERAGE_MAX > 7, "
            "muss true sein (schema 7..75 vs. operativer Erst-Burn-in MAX=7, LaunchChecklist)."
        ),
    )
    risk_require_7x_approval: bool = Field(default=True, alias="RISK_REQUIRE_7X_APPROVAL")
    risk_default_action: RiskDefaultAction = Field(
        default="do_not_trade",
        alias="RISK_DEFAULT_ACTION",
    )
    risk_min_signal_strength: int = Field(
        default=65,
        alias="RISK_MIN_SIGNAL_STRENGTH",
        validation_alias=AliasChoices(
            "RISK_MIN_SIGNAL_STRENGTH",
            "STRAT_MIN_SIGNAL_STRENGTH",
        ),
    )
    risk_min_probability: float = Field(
        default=0.65,
        alias="RISK_MIN_PROBABILITY",
        validation_alias=AliasChoices(
            "RISK_MIN_PROBABILITY",
            "STRAT_MIN_PROBABILITY",
        ),
    )
    risk_min_risk_score: int = Field(
        default=60,
        alias="RISK_MIN_RISK_SCORE",
        validation_alias=AliasChoices(
            "RISK_MIN_RISK_SCORE",
            "STRAT_MIN_RISK_SCORE",
        ),
    )
    risk_min_expected_return_bps: float = Field(
        default=5.0,
        alias="RISK_MIN_EXPECTED_RETURN_BPS",
        validation_alias=AliasChoices(
            "RISK_MIN_EXPECTED_RETURN_BPS",
            "STRAT_MIN_EXPECTED_RETURN_BPS",
        ),
    )
    risk_max_expected_mae_bps: float = Field(
        default=120.0,
        alias="RISK_MAX_EXPECTED_MAE_BPS",
        validation_alias=AliasChoices(
            "RISK_MAX_EXPECTED_MAE_BPS",
            "STRAT_MAX_EXPECTED_MAE_BPS",
        ),
    )
    risk_min_projected_rr: float = Field(
        default=1.15,
        alias="RISK_MIN_PROJECTED_RR",
        validation_alias=AliasChoices(
            "RISK_MIN_PROJECTED_RR",
            "STRAT_MIN_PROJECTED_RR",
        ),
    )
    risk_max_position_risk_pct: float = Field(
        default=0.02,
        alias="RISK_MAX_POSITION_RISK_PCT",
    )
    risk_portfolio_live_max_largest_position_risk_0_1: float = Field(
        default=0.22,
        alias="RISK_PORTFOLIO_LIVE_MAX_LARGEST_POSITION_RISK_0_1",
        description="Live-Stress wenn groesste offene Position Risiko zu Equity uebersteigt (Snapshot-Feld).",
    )
    risk_leverage_cap_daily_drawdown_threshold_0_1: float = Field(
        default=0.025,
        alias="RISK_LEVERAGE_CAP_DAILY_DRAWDOWN_THRESHOLD_0_1",
    )
    risk_leverage_cap_weekly_drawdown_threshold_0_1: float = Field(
        default=0.06,
        alias="RISK_LEVERAGE_CAP_WEEKLY_DRAWDOWN_THRESHOLD_0_1",
    )
    risk_leverage_max_under_drawdown: int = Field(
        default=10,
        alias="RISK_LEVERAGE_MAX_UNDER_DRAWDOWN",
        description="Obergrenze Hebel (Evidence-Cap), wenn Daily/Weekly-Drawdown-Schwelle erreicht.",
    )
    risk_max_account_margin_usage: float = Field(
        default=0.35,
        alias="RISK_MAX_ACCOUNT_MARGIN_USAGE",
        validation_alias=AliasChoices(
            "RISK_MAX_ACCOUNT_MARGIN_USAGE",
            "LEVERAGE_MAX_MARGIN_USAGE_PCT",
        ),
    )
    risk_max_account_drawdown_pct: float = Field(
        default=0.10,
        alias="RISK_MAX_ACCOUNT_DRAWDOWN_PCT",
    )
    risk_max_daily_drawdown_pct: float = Field(
        default=0.04,
        alias="RISK_MAX_DAILY_DRAWDOWN_PCT",
    )
    risk_max_weekly_drawdown_pct: float = Field(
        default=0.08,
        alias="RISK_MAX_WEEKLY_DRAWDOWN_PCT",
    )
    risk_max_daily_loss_usdt: float = Field(default=1000.0, alias="RISK_MAX_DAILY_LOSS_USDT")
    risk_max_position_notional_usdt: float = Field(
        default=5000.0,
        alias="RISK_MAX_POSITION_NOTIONAL_USDT",
    )
    risk_max_concurrent_positions: int = Field(
        default=1,
        alias="RISK_MAX_CONCURRENT_POSITIONS",
        validation_alias=AliasChoices(
            "RISK_MAX_CONCURRENT_POSITIONS",
            "MAX_CONCURRENT_POSITIONS",
        ),
    )
    risk_max_portfolio_exposure_pct: float = Field(
        default=0.25,
        alias="RISK_MAX_PORTFOLIO_EXPOSURE_PCT",
        description=(
            "Grenze fuer Summe (Notional = Einstieg * Menge * Hebel) aus live.positions "
            "plus geplante Order, relativ zur Equity; blockiert weitere Eroeffnungen (live-broker)."
        ),
    )
    risk_portfolio_diversification_buffer_per_instrument: float = Field(
        default=0.05,
        alias="RISK_PORTFOLIO_DIVERSIFICATION_BUFFER_PER_INSTRUMENT",
        description=(
            "Pro zusaetzlichem aktivem Instrument: Sicherheitsabschlag auf die effektive "
            "Exposure-Grenze (Korrelation / unkorrelierte Assets; survival_kernel + risk_adapter)."
        ),
    )
    risk_force_reduce_only_on_alert: bool = Field(
        default=True,
        alias="RISK_FORCE_REDUCE_ONLY_ON_ALERT",
    )
    risk_governor_loss_streak_max: int = Field(
        default=5,
        alias="RISK_GOVERNOR_LOSS_STREAK_MAX",
    )
    risk_governor_correlation_stress_abstain: float = Field(
        default=0.88,
        alias="RISK_GOVERNOR_CORRELATION_STRESS_ABSTAIN",
    )
    risk_governor_live_ramp_max_leverage: int = Field(
        default=7,
        alias="RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE",
    )
    risk_governor_account_stress_live_only: bool = Field(
        default=True,
        alias="RISK_GOVERNOR_ACCOUNT_STRESS_LIVE_ONLY",
        description=(
            "Wenn true: Margin/Drawdown/Serie/Korrelation/Gross/Positions/Side-Policy blocken nur "
            "Live-Execution; Paper/Shadow behalten signaltechnisches allow_trade (ohne LLM)."
        ),
    )
    risk_portfolio_live_max_family_exposure_0_1: float = Field(
        default=0.58,
        alias="RISK_PORTFOLIO_LIVE_MAX_FAMILY_EXPOSURE_0_1",
        description="Live-Block wenn portfolio_risk_json.family_exposure_fraction_0_1[familie] > Schwelle.",
    )
    risk_portfolio_live_max_direction_net_exposure_0_1: float = Field(
        default=0.72,
        alias="RISK_PORTFOLIO_LIVE_MAX_DIRECTION_NET_EXPOSURE_0_1",
    )
    risk_portfolio_live_max_cluster_exposure_0_1: float = Field(
        default=0.48,
        alias="RISK_PORTFOLIO_LIVE_MAX_CLUSTER_EXPOSURE_0_1",
    )
    risk_portfolio_live_max_funding_drag_bps: float = Field(
        default=95.0,
        alias="RISK_PORTFOLIO_LIVE_MAX_FUNDING_DRAG_BPS",
    )
    risk_portfolio_live_max_basis_stress_0_1: float = Field(
        default=0.62,
        alias="RISK_PORTFOLIO_LIVE_MAX_BASIS_STRESS_0_1",
    )
    risk_portfolio_live_max_session_concentration_0_1: float = Field(
        default=0.88,
        alias="RISK_PORTFOLIO_LIVE_MAX_SESSION_CONCENTRATION_0_1",
    )
    risk_portfolio_live_max_open_orders_notional_ratio_0_1: float = Field(
        default=0.42,
        alias="RISK_PORTFOLIO_LIVE_MAX_OPEN_ORDERS_NOTIONAL_RATIO_0_1",
    )
    risk_portfolio_live_max_pending_mirror_trades: int = Field(
        default=4,
        alias="RISK_PORTFOLIO_LIVE_MAX_PENDING_MIRROR_TRADES",
    )
    risk_portfolio_live_block_venue_degraded: bool = Field(
        default=True,
        alias="RISK_PORTFOLIO_LIVE_BLOCK_VENUE_DEGRADED",
    )

    leverage_auto_execution_fraction_of_recommended_0_1: float = Field(
        default=0.88,
        alias="LEVERAGE_AUTO_EXECUTION_FRACTION_OF_RECOMMENDED_0_1",
        description="Auto-Execution: Anteil des recommended Hebels (oberhalb wird gekappt).",
    )
    leverage_auto_execution_subtract_steps: int = Field(
        default=0,
        alias="LEVERAGE_AUTO_EXECUTION_SUBTRACT_STEPS",
        description="Zusaetzliche Ganzzahl-Reduktion fuer execution_leverage_cap.",
    )
    leverage_family_max_cap_spot: int = Field(
        default=5,
        alias="LEVERAGE_FAMILY_MAX_CAP_SPOT",
        description="Zusaetzliche Engine-Kappe Spot (vor Instrument-Metadaten).",
    )
    leverage_family_max_cap_margin: int = Field(
        default=25,
        alias="LEVERAGE_FAMILY_MAX_CAP_MARGIN",
    )
    leverage_family_max_cap_futures: int = Field(
        default=75,
        alias="LEVERAGE_FAMILY_MAX_CAP_FUTURES",
    )
    leverage_cold_start_max_cap: int = Field(
        default=12,
        alias="LEVERAGE_COLD_START_MAX_CAP",
        description="Max-Hebel bei fehlender Instrument-Evidenz / wenigen Prior-Signalen.",
    )
    leverage_cold_start_prior_signals_threshold: int = Field(
        default=20,
        alias="LEVERAGE_COLD_START_PRIOR_SIGNALS_THRESHOLD",
    )
    leverage_shadow_divergence_soft_cap_threshold_0_1: float = Field(
        default=0.38,
        alias="LEVERAGE_SHADOW_DIVERGENCE_SOFT_CAP_THRESHOLD_0_1",
    )
    leverage_shadow_divergence_soft_max_leverage: int = Field(
        default=14,
        alias="LEVERAGE_SHADOW_DIVERGENCE_SOFT_MAX_LEVERAGE",
    )
    leverage_stop_distance_scale_bps: float = Field(
        default=180.0,
        alias="LEVERAGE_STOP_DISTANCE_SCALE_BPS",
        description="Skalierung Hebel vs. Stop-Distanz (analog Paper-Broker).",
    )
    leverage_tight_stop_exposure_threshold_pct: float = Field(
        default=0.004,
        alias="LEVERAGE_TIGHT_STOP_EXPOSURE_THRESHOLD_PCT",
    )
    leverage_tight_stop_exposure_shrink_factor_0_1: float = Field(
        default=0.60,
        alias="LEVERAGE_TIGHT_STOP_EXPOSURE_SHRINK_FACTOR_0_1",
    )
    leverage_account_heat_margin_soft_threshold_0_1: float = Field(
        default=0.50,
        alias="LEVERAGE_ACCOUNT_HEAT_MARGIN_SOFT_THRESHOLD_0_1",
    )
    leverage_account_heat_execution_shrink_0_1: float = Field(
        default=0.75,
        alias="LEVERAGE_ACCOUNT_HEAT_EXECUTION_SHRINK_0_1",
    )

    model_ops_enabled: bool = Field(default=False, alias="MODEL_OPS_ENABLED")
    model_ops_registry_uri: str = Field(default="", alias="MODEL_OPS_REGISTRY_URI")
    model_ops_active_model_tag: str = Field(default="", alias="MODEL_OPS_ACTIVE_MODEL_TAG")
    model_ops_approval_required: bool = Field(
        default=True,
        alias="MODEL_OPS_APPROVAL_REQUIRED",
    )
    model_ops_shadow_eval_enabled: bool = Field(
        default=False,
        alias="MODEL_OPS_SHADOW_EVAL_ENABLED",
    )
    model_ops_drift_alert_threshold: float = Field(
        default=0.15,
        alias="MODEL_OPS_DRIFT_ALERT_THRESHOLD",
    )
    model_ops_rollback_on_drift: bool = Field(
        default=True,
        alias="MODEL_OPS_ROLLBACK_ON_DRIFT",
    )
    model_ops_min_sample_size: int = Field(default=50, alias="MODEL_OPS_MIN_SAMPLE_SIZE")

    enable_online_drift_block: bool = Field(default=False, alias="ENABLE_ONLINE_DRIFT_BLOCK")
    enable_online_drift_shadow_only_signal_hard_block: bool = Field(
        default=False,
        alias="ENABLE_ONLINE_DRIFT_SHADOW_ONLY_SIGNAL_HARD_BLOCK",
        description="Wenn true und ENABLE_ONLINE_DRIFT_BLOCK: shadow_only wie hard_block (Signale -> do_not_trade).",
    )

    security_require_internal_network: bool = Field(
        default=False,
        alias="SECURITY_REQUIRE_INTERNAL_NETWORK",
    )
    security_allow_event_debug_routes: bool = Field(
        default=False,
        alias="SECURITY_ALLOW_EVENT_DEBUG_ROUTES",
    )
    security_allow_db_debug_routes: bool = Field(
        default=False,
        alias="SECURITY_ALLOW_DB_DEBUG_ROUTES",
    )
    security_allow_alert_replay_routes: bool = Field(
        default=False,
        alias="SECURITY_ALLOW_ALERT_REPLAY_ROUTES",
    )
    service_internal_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("INTERNAL_API_KEY", "SERVICE_INTERNAL_API_KEY"),
    )
    admin_token: str = Field(default="", alias="ADMIN_TOKEN")
    secret_key: str = Field(default="", alias="SECRET_KEY")
    jwt_secret: str = Field(default="", alias="JWT_SECRET")
    encryption_key: str = Field(default="", alias="ENCRYPTION_KEY")

    bitget_demo_enabled: bool = Field(default=False, alias="BITGET_DEMO_ENABLED")
    news_fixture_mode: bool = Field(default=False, alias="NEWS_FIXTURE_MODE")
    llm_use_fake_provider: bool = Field(default=False, alias="LLM_USE_FAKE_PROVIDER")
    paper_sim_mode: bool = Field(default=False, alias="PAPER_SIM_MODE")
    paper_contract_config_mode: ContractConfigMode = Field(
        default="live",
        alias="PAPER_CONTRACT_CONFIG_MODE",
    )
    telegram_dry_run: bool = Field(default=False, alias="TELEGRAM_DRY_RUN")

    @field_validator(
        "vault_addr",
        "vault_token",
        "vault_role_id",
        "vault_secret_id",
        "kms_key_id",
        "deploy_env",
        "deploy_script",
        "app_name",
        "app_base_url",
        "frontend_url",
        "cors_allow_origins",
        "database_url",
        "redis_url",
        "live_broker_base_url",
        "live_broker_ws_private_url",
        "bitget_universe_market_families",
        "bitget_futures_allowed_product_types",
        "bitget_universe_symbols",
        "bitget_watchlist_symbols",
        "feature_scope_symbols",
        "feature_scope_timeframes",
        "signal_scope_symbols",
        "bitget_spot_default_quote_coin",
        "bitget_margin_default_quote_coin",
        "bitget_margin_default_account_mode",
        "bitget_margin_default_loan_type",
        "bitget_futures_default_product_type",
        "bitget_futures_default_margin_coin",
        "live_allowed_symbols",
        "live_allowed_market_families",
        "live_allowed_product_types",
        "model_ops_registry_uri",
        "model_ops_active_model_tag",
        "service_internal_api_key",
        "admin_token",
        "secret_key",
        "jwt_secret",
        "encryption_key",
        mode="before",
    )
    @classmethod
    def _normalize_string_fields(cls, value: Any) -> str:
        return _norm_str(value)

    @field_validator("app_env", mode="before")
    @classmethod
    def _normalize_app_env(cls, value: Any) -> Any:
        normalized = _norm_lower(value)
        if normalized in ("dev",):
            return "development"
        if normalized in ("prod",):
            return "production"
        return normalized or value

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: Any) -> str:
        normalized = _norm_str(value).upper()
        return normalized or "INFO"

    @field_validator("log_format", mode="before")
    @classmethod
    def _norm_log_format(cls, value: Any) -> Any:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("json", "plain"):
                return normalized
        return value

    @field_validator("vault_mode", mode="before")
    @classmethod
    def _norm_vault_mode(cls, value: Any) -> Any:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("false", "0", "no", "off"):
                return "false"
            if normalized in ("none",):
                return "none"
            if normalized in ("hashicorp", "vault", "hc"):
                return "hashicorp"
            if normalized in ("aws", "kms"):
                return "aws"
        return value

    @field_validator(
        "execution_mode",
        "strategy_execution_mode",
        "api_auth_mode",
        mode="before",
    )
    @classmethod
    def _normalize_mode_fields(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("paper_contract_config_mode", mode="before")
    @classmethod
    def _normalize_contract_config_mode(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator(
        "bitget_universe_market_families",
        "live_allowed_market_families",
        mode="before",
    )
    @classmethod
    def _normalize_market_family_csv(cls, value: Any) -> str:
        if value is None:
            return ""
        parts = [part for part in _iter_csv_lower(str(value)) if part]
        return ",".join(parts)

    @field_validator(
        "bitget_futures_allowed_product_types",
        "live_allowed_product_types",
        mode="before",
    )
    @classmethod
    def _normalize_product_type_csv(cls, value: Any) -> str:
        if value is None:
            return ""
        parts = [part for part in _iter_csv_upper(str(value)) if part]
        return ",".join(parts)

    @field_validator(
        "bitget_universe_symbols",
        "bitget_watchlist_symbols",
        "feature_scope_symbols",
        "signal_scope_symbols",
        "live_allowed_symbols",
        mode="before",
    )
    @classmethod
    def _normalize_symbol_csv(cls, value: Any) -> str:
        if value is None:
            return ""
        parts = [part for part in _iter_csv_upper(str(value)) if part]
        return ",".join(parts)

    @field_validator("feature_scope_timeframes", mode="before")
    @classmethod
    def _normalize_feature_scope_timeframes(cls, value: Any) -> str:
        if value is None:
            return ",".join(_DEFAULT_SCOPE_TIMEFRAMES)
        parts = [_normalize_scope_timeframe(part) for part in _iter_csv(str(value))]
        return ",".join(parts)

    @field_validator(
        "bitget_spot_default_quote_coin",
        "bitget_margin_default_quote_coin",
        "bitget_futures_default_margin_coin",
        mode="before",
    )
    @classmethod
    def _normalize_coin_defaults(cls, value: Any) -> str:
        normalized = _norm_str(value).upper()
        return normalized

    @field_validator(
        "bitget_margin_default_account_mode",
        mode="before",
    )
    @classmethod
    def _normalize_margin_default_mode(cls, value: Any) -> str:
        return _norm_lower(value)

    @field_validator(
        "bitget_margin_default_loan_type",
        mode="before",
    )
    @classmethod
    def _normalize_margin_default_loan_type(cls, value: Any) -> str:
        return _norm_str(value)

    @field_validator(
        "bitget_futures_default_product_type",
        mode="before",
    )
    @classmethod
    def _normalize_default_product_type(cls, value: Any) -> str:
        return _norm_str(value).upper()

    @field_validator(
        "live_reconcile_interval_sec",
        "instrument_catalog_refresh_interval_sec",
        "instrument_catalog_cache_ttl_sec",
        "instrument_catalog_max_stale_sec",
        "risk_max_concurrent_positions",
        "risk_min_signal_strength",
        "risk_min_risk_score",
        "model_ops_min_sample_size",
        "risk_governor_loss_streak_max",
    )
    @classmethod
    def _positive_ints(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Ganzzahlige Settings muessen > 0 sein")
        return value

    @field_validator("risk_governor_correlation_stress_abstain")
    @classmethod
    def _governor_correlation_unit(cls, value: float) -> float:
        if value <= 0 or value > 1:
            raise ValueError("RISK_GOVERNOR_CORRELATION_STRESS_ABSTAIN muss in (0, 1] liegen")
        return value

    @field_validator("risk_governor_live_ramp_max_leverage")
    @classmethod
    def _governor_ramp_leverage(cls, value: int) -> int:
        if value < 7 or value > 75:
            raise ValueError("RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE muss 7..75 sein")
        return value

    @field_validator(
        "risk_portfolio_live_max_family_exposure_0_1",
        "risk_portfolio_live_max_direction_net_exposure_0_1",
        "risk_portfolio_live_max_cluster_exposure_0_1",
        "risk_portfolio_live_max_basis_stress_0_1",
        "risk_portfolio_live_max_session_concentration_0_1",
        "risk_portfolio_live_max_open_orders_notional_ratio_0_1",
    )
    @classmethod
    def _portfolio_live_unit_interval(cls, value: float) -> float:
        if value <= 0 or value > 1:
            raise ValueError("RISK_PORTFOLIO_LIVE_*_0_1 muss in (0, 1] liegen")
        return value

    @field_validator("risk_portfolio_live_max_funding_drag_bps")
    @classmethod
    def _portfolio_funding_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("RISK_PORTFOLIO_LIVE_MAX_FUNDING_DRAG_BPS muss > 0 sein")
        return value

    @field_validator("risk_portfolio_live_max_pending_mirror_trades")
    @classmethod
    def _portfolio_mirror_nonneg(cls, value: int) -> int:
        if value < 0:
            raise ValueError("RISK_PORTFOLIO_LIVE_MAX_PENDING_MIRROR_TRADES darf nicht negativ sein")
        return value

    @field_validator(
        "leverage_auto_execution_fraction_of_recommended_0_1",
        "leverage_tight_stop_exposure_shrink_factor_0_1",
        "leverage_account_heat_execution_shrink_0_1",
        "leverage_shadow_divergence_soft_cap_threshold_0_1",
    )
    @classmethod
    def _unified_leverage_unit_interval(cls, value: float) -> float:
        if value <= 0 or value > 1:
            raise ValueError("LEVERAGE_*_0_1 Schwellen muessen in (0, 1] liegen")
        return value

    @field_validator("leverage_auto_execution_subtract_steps", "leverage_cold_start_prior_signals_threshold")
    @classmethod
    def _unified_leverage_non_negative_int(cls, value: int) -> int:
        if value < 0:
            raise ValueError("LEVERAGE_*_SUBTRACT/STEPS duerfen nicht negativ sein")
        return value

    @field_validator(
        "leverage_cold_start_max_cap",
        "leverage_shadow_divergence_soft_max_leverage",
        "leverage_family_max_cap_spot",
        "leverage_family_max_cap_margin",
        "leverage_family_max_cap_futures",
    )
    @classmethod
    def _unified_leverage_cap_int(cls, value: int) -> int:
        if value < 0 or value > 75:
            raise ValueError("LEVERAGE_*_CAP muss 0..75 sein")
        return value

    @field_validator("leverage_stop_distance_scale_bps", "leverage_tight_stop_exposure_threshold_pct")
    @classmethod
    def _unified_leverage_positive_float(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("LEVERAGE_STOP_DISTANCE_SCALE_BPS und THRESHOLD_PCT muessen > 0 sein")
        return value

    @field_validator(
        "risk_max_daily_loss_usdt",
        "risk_max_position_notional_usdt",
        "risk_min_expected_return_bps",
        "risk_max_expected_mae_bps",
        "risk_min_projected_rr",
        "model_ops_drift_alert_threshold",
    )
    @classmethod
    def _positive_floats(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Numerische Settings muessen > 0 sein")
        return value

    @field_validator(
        "risk_min_probability",
        "risk_max_position_risk_pct",
        "risk_max_account_margin_usage",
        "risk_max_account_drawdown_pct",
        "risk_max_daily_drawdown_pct",
        "risk_max_weekly_drawdown_pct",
        "risk_max_portfolio_exposure_pct",
    )
    @classmethod
    def _unit_interval_risk_thresholds(cls, value: float) -> float:
        if value <= 0 or value > 1:
            raise ValueError("Risk-Schwellen muessen > 0 und <= 1 sein")
        return value

    @field_validator("risk_portfolio_diversification_buffer_per_instrument")
    @classmethod
    def _portfolio_diversification_buffer_unit(cls, value: float) -> float:
        if value <= 0 or value > 0.5:
            raise ValueError("RISK_PORTFOLIO_DIVERSIFICATION_BUFFER_PER_INSTRUMENT muss in (0, 0.5] liegen")
        return value

    @field_validator("risk_min_signal_strength", "risk_min_risk_score")
    @classmethod
    def _score_thresholds(cls, value: int) -> int:
        if value < 1 or value > 100:
            raise ValueError("Score-Schwellen muessen im Bereich 1..100 liegen")
        return value

    @field_validator("risk_allowed_leverage_min")
    @classmethod
    def _validate_risk_leverage_min(cls, value: int) -> int:
        if value != 7:
            raise ValueError("RISK_ALLOWED_LEVERAGE_MIN muss exakt 7 sein")
        return value

    @field_validator("risk_allowed_leverage_max")
    @classmethod
    def _validate_risk_leverage_max(cls, value: int) -> int:
        if value < 7 or value > 75:
            raise ValueError("RISK_ALLOWED_LEVERAGE_MAX muss im Bereich 7..75 liegen")
        return value

    def bitget_universe_market_families_list(self) -> list[str]:
        return _iter_csv_lower(self.bitget_universe_market_families)

    def bitget_futures_allowed_product_types_list(self) -> list[str]:
        return _iter_csv_upper(self.bitget_futures_allowed_product_types)

    def bitget_universe_symbols_list(self) -> list[str]:
        return _iter_csv_upper(self.bitget_universe_symbols)

    def bitget_watchlist_symbols_list(self) -> list[str]:
        explicit = _iter_csv_upper(self.bitget_watchlist_symbols)
        if explicit:
            return explicit
        universe = self.bitget_universe_symbols_list()
        if universe:
            return universe
        return _iter_csv_upper(self.live_allowed_symbols)

    def default_operational_symbol(self) -> str:
        candidates = self.bitget_watchlist_symbols_list()
        return candidates[0] if candidates else ""

    def default_futures_product_type(self) -> str:
        if self.bitget_futures_default_product_type:
            return self.bitget_futures_default_product_type
        allowed = self.bitget_futures_allowed_product_types_list()
        return allowed[0] if allowed else ""

    def default_futures_margin_coin(self) -> str:
        if self.bitget_futures_default_margin_coin:
            return self.bitget_futures_default_margin_coin
        product = self.default_futures_product_type()
        if product == "USDT-FUTURES":
            return "USDT"
        if product == "USDC-FUTURES":
            return "USDC"
        return ""

    def feature_scope_symbols_list(self) -> list[str]:
        explicit = _iter_csv_upper(self.feature_scope_symbols)
        return explicit or self.bitget_watchlist_symbols_list()

    def signal_scope_symbols_list(self) -> list[str]:
        explicit = _iter_csv_upper(self.signal_scope_symbols)
        return explicit or self.feature_scope_symbols_list()

    def feature_scope_timeframes_list(self) -> list[str]:
        values = [_normalize_scope_timeframe(part) for part in _iter_csv(self.feature_scope_timeframes)]
        return values or list(_DEFAULT_SCOPE_TIMEFRAMES)

    def family_defaults_snapshot(self) -> dict[str, Any]:
        return {
            "spot": {
                "quote_coin": self.bitget_spot_default_quote_coin,
                "market_family": "spot",
            },
            "margin": {
                "quote_coin": self.bitget_margin_default_quote_coin,
                "margin_account_mode": self.bitget_margin_default_account_mode,
                "loan_type": self.bitget_margin_default_loan_type,
            },
            "futures": {
                "default_product_type": self.bitget_futures_default_product_type,
                "allowed_product_types": self.bitget_futures_allowed_product_types_list(),
                "default_margin_coin": self.bitget_futures_default_margin_coin,
            },
        }

    def market_universe_snapshot(self) -> dict[str, Any]:
        return {
            "market_families": self.bitget_universe_market_families_list(),
            "universe_symbols": self.bitget_universe_symbols_list(),
            "watchlist_symbols": self.bitget_watchlist_symbols_list(),
            "feature_scope": {
                "symbols": self.feature_scope_symbols_list(),
                "timeframes": self.feature_scope_timeframes_list(),
            },
            "signal_scope_symbols": self.signal_scope_symbols_list(),
            "family_defaults": self.family_defaults_snapshot(),
            "live_allowlists": {
                "symbols": _iter_csv_upper(self.live_allowed_symbols),
                "market_families": _iter_csv_lower(self.live_allowed_market_families),
                "product_types": _iter_csv_upper(self.live_allowed_product_types),
            },
            "catalog_policy": {
                "refresh_interval_sec": self.instrument_catalog_refresh_interval_sec,
                "cache_ttl_sec": self.instrument_catalog_cache_ttl_sec,
                "max_stale_sec": self.instrument_catalog_max_stale_sec,
                "unknown_instrument_action": "no_trade_no_subscribe",
            },
        }

    def configuration_runtime_snapshot(self) -> dict[str, Any]:
        return {
            "app_env": self.app_env,
            "production": self.production,
            "api_auth_mode": self.api_auth_mode,
            "security_require_internal_network": self.security_require_internal_network,
            "market_universe": self.market_universe_snapshot(),
        }

    def _required_production_fields(self) -> tuple[str, ...]:
        names = list(self.production_required_fields)
        if self.model_ops_enabled:
            names.append("model_ops_registry_uri")
        if self.execution_mode in ("shadow", "live") or self.live_broker_enabled:
            names.extend(("live_broker_base_url", "live_broker_ws_private_url"))
        if self.vault_mode == "hashicorp":
            names.append("vault_addr")
        if self.vault_mode == "aws":
            names.append("kms_key_id")
        deduped: list[str] = []
        for name in names:
            if name not in deduped:
                deduped.append(name)
        return tuple(deduped)

    def _required_production_non_local_fields(self) -> tuple[str, ...]:
        names = list(self.production_required_non_local_fields)
        if self.model_ops_enabled:
            names.append("model_ops_registry_uri")
        if self.execution_mode in ("shadow", "live") or self.live_broker_enabled:
            names.extend(("live_broker_base_url", "live_broker_ws_private_url"))
        deduped: list[str] = []
        for name in names:
            if name not in deduped:
                deduped.append(name)
        return tuple(deduped)

    @field_validator("use_docker_datastore_dsn", mode="before")
    @classmethod
    def _norm_use_docker_datastore_dsn(cls, v: Any) -> Any:
        if v is None or (isinstance(v, str) and not str(v).strip()):
            return False
        return v

    @model_validator(mode="after")
    def _resolve_runtime_datastore_dsns(self) -> Self:
        if not self.use_docker_datastore_dsn:
            return self
        du = _norm_str(self.database_url_docker)
        ru = _norm_str(self.redis_url_docker)
        if du:
            object.__setattr__(self, "database_url", du)
        if ru:
            object.__setattr__(self, "redis_url", ru)
        return self

    @model_validator(mode="after")
    def _universe_scope_consistency(self) -> Self:
        families = self.bitget_universe_market_families_list()
        if not families:
            raise ValueError("BITGET_UNIVERSE_MARKET_FAMILIES darf nicht leer sein")
        invalid_families = [family for family in families if family not in _ALLOWED_MARKET_FAMILIES]
        if invalid_families:
            raise ValueError(
                "BITGET_UNIVERSE_MARKET_FAMILIES enthaelt ungueltige Familien: "
                + ", ".join(invalid_families)
            )

        live_families = _iter_csv_lower(self.live_allowed_market_families)
        invalid_live_families = [family for family in live_families if family not in families]
        if invalid_live_families:
            raise ValueError(
                "LIVE_ALLOWED_MARKET_FAMILIES muss Teil von BITGET_UNIVERSE_MARKET_FAMILIES sein: "
                + ", ".join(invalid_live_families)
            )

        allowed_products = self.bitget_futures_allowed_product_types_list()
        if not allowed_products:
            raise ValueError("BITGET_FUTURES_ALLOWED_PRODUCT_TYPES darf nicht leer sein")
        invalid_products = [
            product for product in allowed_products if product not in _ALLOWED_FUTURES_PRODUCT_TYPES
        ]
        if invalid_products:
            raise ValueError(
                "BITGET_FUTURES_ALLOWED_PRODUCT_TYPES enthaelt ungueltige Werte: "
                + ", ".join(invalid_products)
            )
        if not self.bitget_futures_default_product_type:
            object.__setattr__(
                self,
                "bitget_futures_default_product_type",
                allowed_products[0],
            )
        if self.bitget_futures_default_product_type not in allowed_products:
            raise ValueError(
                "BITGET_FUTURES_DEFAULT_PRODUCT_TYPE muss Teil von BITGET_FUTURES_ALLOWED_PRODUCT_TYPES sein"
            )
        if not self.bitget_futures_default_margin_coin:
            object.__setattr__(
                self,
                "bitget_futures_default_margin_coin",
                self.default_futures_margin_coin(),
            )
        live_products = _iter_csv_upper(self.live_allowed_product_types)
        invalid_live_products = [product for product in live_products if product not in allowed_products]
        if invalid_live_products:
            raise ValueError(
                "LIVE_ALLOWED_PRODUCT_TYPES muss Teil von BITGET_FUTURES_ALLOWED_PRODUCT_TYPES sein: "
                + ", ".join(invalid_live_products)
            )

        if self.bitget_margin_default_account_mode not in ("isolated", "crossed"):
            raise ValueError(
                "BITGET_MARGIN_DEFAULT_ACCOUNT_MODE muss isolated oder crossed sein"
            )

        if self.instrument_catalog_refresh_interval_sec > self.instrument_catalog_max_stale_sec:
            raise ValueError(
                "INSTRUMENT_CATALOG_REFRESH_INTERVAL_SEC darf INSTRUMENT_CATALOG_MAX_STALE_SEC nicht uebersteigen"
            )
        if self.instrument_catalog_cache_ttl_sec > self.instrument_catalog_max_stale_sec:
            raise ValueError(
                "INSTRUMENT_CATALOG_CACHE_TTL_SEC darf INSTRUMENT_CATALOG_MAX_STALE_SEC nicht uebersteigen"
            )
        if self.risk_governor_live_ramp_max_leverage > self.risk_allowed_leverage_max:
            raise ValueError(
                "RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE darf nicht ueber RISK_ALLOWED_LEVERAGE_MAX liegen"
            )
        if self.leverage_cold_start_max_cap < self.risk_allowed_leverage_min:
            raise ValueError(
                "LEVERAGE_COLD_START_MAX_CAP darf nicht unter RISK_ALLOWED_LEVERAGE_MIN liegen"
            )
        for name, cap in (
            ("LEVERAGE_FAMILY_MAX_CAP_SPOT", self.leverage_family_max_cap_spot),
            ("LEVERAGE_FAMILY_MAX_CAP_MARGIN", self.leverage_family_max_cap_margin),
            ("LEVERAGE_FAMILY_MAX_CAP_FUTURES", self.leverage_family_max_cap_futures),
        ):
            if cap > self.risk_allowed_leverage_max:
                raise ValueError(f"{name} darf RISK_ALLOWED_LEVERAGE_MAX nicht uebersteigen")

        universe_symbols = self.bitget_universe_symbols_list()
        watchlist = _iter_csv_upper(self.bitget_watchlist_symbols)
        if universe_symbols and watchlist:
            invalid_watchlist = [symbol for symbol in watchlist if symbol not in universe_symbols]
            if invalid_watchlist:
                raise ValueError(
                    "BITGET_WATCHLIST_SYMBOLS muss Teil von BITGET_UNIVERSE_SYMBOLS sein: "
                    + ", ".join(invalid_watchlist)
                )

        feature_symbols = _iter_csv_upper(self.feature_scope_symbols)
        feature_parent = watchlist or universe_symbols or _iter_csv_upper(self.live_allowed_symbols)
        if feature_parent and feature_symbols:
            invalid_feature_symbols = [
                symbol for symbol in feature_symbols if symbol not in feature_parent
            ]
            if invalid_feature_symbols:
                raise ValueError(
                    "FEATURE_SCOPE_SYMBOLS muss Teil von Watchlist/Universe sein: "
                    + ", ".join(invalid_feature_symbols)
                )

        signal_symbols = _iter_csv_upper(self.signal_scope_symbols)
        signal_parent = feature_symbols or feature_parent
        if signal_parent and signal_symbols:
            invalid_signal_symbols = [
                symbol for symbol in signal_symbols if symbol not in signal_parent
            ]
            if invalid_signal_symbols:
                raise ValueError(
                    "SIGNAL_SCOPE_SYMBOLS muss Teil von FEATURE_SCOPE_SYMBOLS oder Watchlist/Universe sein: "
                    + ", ".join(invalid_signal_symbols)
                )

        timeframe_values = self.feature_scope_timeframes_list()
        if not timeframe_values:
            raise ValueError("FEATURE_SCOPE_TIMEFRAMES darf nicht leer sein")
        return self

    @model_validator(mode="after")
    def _prod_safety(self) -> Self:
        if self.risk_max_daily_drawdown_pct > self.risk_max_weekly_drawdown_pct:
            raise ValueError(
                "RISK_MAX_DAILY_DRAWDOWN_PCT darf nicht groesser als "
                "RISK_MAX_WEEKLY_DRAWDOWN_PCT sein"
            )
        if self.risk_max_weekly_drawdown_pct > self.risk_max_account_drawdown_pct:
            raise ValueError(
                "RISK_MAX_WEEKLY_DRAWDOWN_PCT darf nicht groesser als "
                "RISK_MAX_ACCOUNT_DRAWDOWN_PCT sein"
            )
        if self.production and self.debug:
            raise ValueError("DEBUG=true ist mit PRODUCTION=true nicht erlaubt.")
        if self.production and self.log_level.upper() == "DEBUG":
            object.__setattr__(self, "log_level", "INFO")

        if self.shadow_trade_enable and self.execution_mode != "shadow":
            raise ValueError(
                "SHADOW_TRADE_ENABLE=true verlangt EXECUTION_MODE=shadow"
            )
        if self.execution_mode == "shadow" and not self.shadow_trade_enable:
            raise ValueError(
                "EXECUTION_MODE=shadow verlangt SHADOW_TRADE_ENABLE=true "
                "(Shadow = echte Signale/Risk/Reconcile, keine Exchange-Orders)"
            )
        if self.live_trade_enable and self.execution_mode != "live":
            raise ValueError(
                "LIVE_TRADE_ENABLE=true ist nur mit EXECUTION_MODE=live erlaubt"
            )
        if self.execution_mode == "live" and not self.live_broker_enabled:
            raise ValueError(
                "EXECUTION_MODE=live verlangt LIVE_BROKER_ENABLED=true"
            )
        if self.execution_mode == "live" and self.bitget_demo_enabled:
            raise ValueError(
                "EXECUTION_MODE=live darf nicht zusammen mit BITGET_DEMO_ENABLED=true "
                "gesetzt sein (Echtgeld-Live und Bitget-Paper-Trading/Sandbox strikt trennen)."
            )
        if not self.risk_hard_gating_enabled:
            raise ValueError("RISK_HARD_GATING_ENABLED muss true sein")
        if not self.risk_require_7x_approval:
            raise ValueError("RISK_REQUIRE_7X_APPROVAL muss true sein")
        if not self.live_kill_switch_enabled:
            raise ValueError("LIVE_KILL_SWITCH_ENABLED muss true sein")

        if self.news_fixture_mode and self.app_env in ("shadow", "production"):
            raise ValueError(
                "NEWS_FIXTURE_MODE=true ist fuer APP_ENV shadow/production verboten "
                "(Fixture-/Demo-Ingest nur local/development/test)"
            )
        if (
            self.news_fixture_mode
            and self.bitget_demo_enabled
            and self.app_env not in ("local", "development", "test")
        ):
            raise ValueError(
                "NEWS_FIXTURE_MODE=true mit BITGET_DEMO_ENABLED=true ist nur fuer "
                "APP_ENV local/development/test erlaubt"
            )
        if self.llm_use_fake_provider and self.app_env in ("shadow", "production"):
            raise ValueError(
                "LLM_USE_FAKE_PROVIDER=true ist fuer APP_ENV shadow/production verboten"
            )

        if not self.production:
            return self

        if self.app_env not in ("shadow", "production"):
            raise ValueError(
                "Bei PRODUCTION=true muss APP_ENV shadow oder production sein"
            )
        if self.api_auth_mode == "none":
            raise ValueError("API_AUTH_MODE=none ist in Produktion nicht erlaubt")
        if not self.security_require_internal_network:
            raise ValueError(
                "SECURITY_REQUIRE_INTERNAL_NETWORK muss in Produktion true sein"
            )
        if self.security_allow_event_debug_routes:
            raise ValueError(
                "SECURITY_ALLOW_EVENT_DEBUG_ROUTES=true ist in Produktion nicht erlaubt"
            )
        if self.security_allow_db_debug_routes:
            raise ValueError(
                "SECURITY_ALLOW_DB_DEBUG_ROUTES=true ist in Produktion nicht erlaubt"
            )
        if self.security_allow_alert_replay_routes:
            raise ValueError(
                "SECURITY_ALLOW_ALERT_REPLAY_ROUTES=true ist in Produktion nicht erlaubt"
            )
        if self.bitget_demo_enabled:
            raise ValueError("BITGET_DEMO_ENABLED=true ist in Produktion nicht erlaubt")
        if self.news_fixture_mode:
            raise ValueError("NEWS_FIXTURE_MODE=true ist in Produktion nicht erlaubt")
        if self.llm_use_fake_provider:
            raise ValueError("LLM_USE_FAKE_PROVIDER=true ist in Produktion nicht erlaubt")
        if self.paper_sim_mode:
            raise ValueError("PAPER_SIM_MODE=true ist in Produktion nicht erlaubt")
        if self.paper_contract_config_mode != "live":
            raise ValueError(
                "PAPER_CONTRACT_CONFIG_MODE muss in Produktion auf live stehen"
            )
        if self.telegram_dry_run:
            raise ValueError("TELEGRAM_DRY_RUN=true ist in Produktion nicht erlaubt")
        if self.vault_mode not in ("hashicorp", "aws"):
            raise ValueError(
                "VAULT_MODE muss in Produktion hashicorp oder aws sein"
            )
        if self.vault_mode == "hashicorp" and not (
            self.vault_token or (self.vault_role_id and self.vault_secret_id)
        ):
            raise ValueError(
                "HashiCorp Vault verlangt VAULT_TOKEN oder VAULT_ROLE_ID+VAULT_SECRET_ID"
            )

        missing_fields = [
            name
            for name in self._required_production_fields()
            if _is_blank_or_placeholder(_norm_str(getattr(self, name, "")))
        ]
        if missing_fields:
            raise ValueError(
                "Pflicht-Settings fuer Produktion fehlen oder sind Platzhalter: "
                + ", ".join(sorted(missing_fields))
            )

        local_host_fields: list[str] = []
        for name in self._required_production_non_local_fields():
            value = _norm_str(getattr(self, name, ""))
            if not value:
                continue
            if name == "cors_allow_origins":
                if any(_contains_local_host(origin) for origin in _iter_csv(value)):
                    local_host_fields.append(name)
            elif _contains_local_host(value):
                local_host_fields.append(name)
        if local_host_fields:
            raise ValueError(
                "Produktion verlangt echte Hosts statt localhost: "
                + ", ".join(sorted(local_host_fields))
            )

        _min = MIN_PRODUCTION_SECRET_LEN
        for fname, envname in (
            ("service_internal_api_key", "INTERNAL_API_KEY"),
            ("jwt_secret", "JWT_SECRET"),
            ("encryption_key", "ENCRYPTION_KEY"),
            ("secret_key", "SECRET_KEY"),
            ("admin_token", "ADMIN_TOKEN"),
        ):
            v = _norm_str(getattr(self, fname, ""))
            if len(v) < _min:
                raise ValueError(
                    f"{envname} muss in Produktion mindestens {_min} Zeichen haben"
                )

        for fname, envname in (
            ("app_base_url", "APP_BASE_URL"),
            ("frontend_url", "FRONTEND_URL"),
        ):
            v = _norm_str(getattr(self, fname, ""))
            if v and not v.lower().startswith("https://"):
                raise ValueError(
                    f"{envname} muss in Produktion mit https:// beginnen"
                )

        cors = _norm_str(self.cors_allow_origins)
        for origin in _iter_csv(cors):
            lo = origin.strip().lower()
            if not lo:
                continue
            if lo == "*" or lo.startswith("http://"):
                raise ValueError(
                    "CORS_ALLOW_ORIGINS: in Produktion nur https-Origins "
                    "(kein '*', kein http://)"
                )
            if not lo.startswith("https://"):
                raise ValueError(
                    "CORS_ALLOW_ORIGINS: jeder Origin muss in Produktion "
                    "mit https:// beginnen"
                )

        if (
            self.live_trade_enable
            and self.risk_allowed_leverage_max > 7
            and not self.risk_elevated_leverage_live_ack
        ):
            raise ValueError(
                "PRODUCTION mit LIVE_TRADE_ENABLE und RISK_ALLOWED_LEVERAGE_MAX > 7 "
                "verlangt RISK_ELEVATED_LEVERAGE_LIVE_ACK=true "
                "(Erst-Burn-in laut LaunchChecklist bei MAX=7; hoeheren Deckel nur nach Freigabe)."
            )

        return self

    @property
    def trading_runtime_mode(self) -> TradingRuntimeMode:
        return self.execution_mode

    @property
    def enable_shadow_mode(self) -> bool:
        return self.shadow_trade_enable

    @property
    def live_allow_order_submit(self) -> bool:
        return self.live_trade_enable

    @property
    def paper_path_active(self) -> bool:
        return self.execution_mode == "paper"

    @property
    def shadow_path_active(self) -> bool:
        return self.execution_mode == "shadow" and self.shadow_trade_enable

    @property
    def live_order_submission_enabled(self) -> bool:
        return (
            self.execution_mode == "live"
            and self.live_trade_enable
            and self.live_broker_enabled
        )

    @property
    def private_exchange_access_enabled(self) -> bool:
        return self.shadow_path_active or self.live_order_submission_enabled

    def execution_runtime_snapshot(self) -> dict[str, Any]:
        """Siehe `config.execution_runtime` — einheitliches Modusmodell."""
        from config.execution_runtime import build_execution_runtime_snapshot

        return build_execution_runtime_snapshot(self)


def emit_secret_management_warning(
    logger: logging.Logger,
    settings: BaseServiceSettings,
) -> None:
    """
    Hinweis, wenn in Produktion keine Vault/KMS-Integration aktiviert ist.
    Keine Secrets loggen.
    """
    if not settings.production:
        return
    mode = str(settings.vault_mode).lower()
    if mode in ("hashicorp", "aws"):
        return
    logger.warning(
        "secret_management: PRODUCTION=true aber VAULT_MODE=%s — "
        "API-Keys und DB-Passwoerter sollten aus Vault/KMS/Secret-Manager "
        "kommen, nicht aus statischen Container-ENV.",
        settings.vault_mode,
    )
