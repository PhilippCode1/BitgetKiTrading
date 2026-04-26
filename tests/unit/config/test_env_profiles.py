from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_FILES = (
    ".env.example",
    ".env.local.example",
    ".env.demo.example",
    ".env.shadow.example",
    ".env.production.example",
    ".env.test.example",
)

LIVE_KEYS = (
    "EXECUTION_MODE",
    "STRATEGY_EXEC_MODE",
    "SHADOW_TRADE_ENABLE",
    "LIVE_BROKER_PORT",
    "LIVE_BROKER_ENABLED",
    "LIVE_BROKER_BASE_URL",
    "LIVE_BROKER_WS_PRIVATE_URL",
    "LIVE_BROKER_CONSUMER_GROUP",
    "LIVE_BROKER_CONSUMER_NAME",
    "LIVE_BROKER_SIGNAL_STREAM",
    "LIVE_BROKER_REFERENCE_STREAMS",
    "ORDER_IDEMPOTENCY_PREFIX",
    "LIVE_TRADE_ENABLE",
    "LIVE_RECONCILE_INTERVAL_SEC",
    "LIVE_KILL_SWITCH_ENABLED",
    "INSTRUMENT_CATALOG_REFRESH_INTERVAL_SEC",
    "INSTRUMENT_CATALOG_CACHE_TTL_SEC",
    "INSTRUMENT_CATALOG_MAX_STALE_SEC",
    "LIVE_ALLOWED_SYMBOLS",
    "LIVE_ALLOWED_MARKET_FAMILIES",
    "LIVE_ALLOWED_PRODUCT_TYPES",
    "LIVE_REQUIRE_EXCHANGE_HEALTH",
    "LIVE_REQUIRE_EXECUTION_BINDING",
    "LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN",
    "LIVE_BROKER_HTTP_TIMEOUT_SEC",
    "LIVE_BROKER_HTTP_MAX_RETRIES",
    "LIVE_BROKER_HTTP_RETRY_BASE_SEC",
    "LIVE_BROKER_HTTP_RETRY_MAX_SEC",
    "LIVE_BROKER_CIRCUIT_FAIL_THRESHOLD",
    "LIVE_BROKER_CIRCUIT_OPEN_SEC",
    "LIVE_BROKER_SERVER_TIME_SYNC_SEC",
    "LIVE_BROKER_SERVER_TIME_MAX_SKEW_MS",
    "LIVE_ORDER_TIMEOUT_SEC",
    "LIVE_EXITS_ENABLED",
    "REQUIRE_SHADOW_MATCH_BEFORE_LIVE",
)
EXIT_KEYS = (
    "STOP_TRIGGER_TYPE_DEFAULT",
    "TP_TRIGGER_TYPE_DEFAULT",
    "TP1_PCT",
    "TP2_PCT",
    "TP3_PCT",
    "RUNNER_TRAIL_ATR_MULT",
    "EXIT_BREAK_EVEN_AFTER_TP_INDEX",
    "EXIT_RUNNER_ENABLED",
)
BITGET_PRIVATE_KEYS = (
    "BITGET_UNIVERSE_MARKET_FAMILIES",
    "BITGET_FUTURES_ALLOWED_PRODUCT_TYPES",
    "BITGET_UNIVERSE_SYMBOLS",
    "BITGET_WATCHLIST_SYMBOLS",
    "FEATURE_SCOPE_SYMBOLS",
    "FEATURE_SCOPE_TIMEFRAMES",
    "SIGNAL_SCOPE_SYMBOLS",
    "BITGET_SPOT_DEFAULT_QUOTE_COIN",
    "BITGET_MARGIN_DEFAULT_QUOTE_COIN",
    "BITGET_MARGIN_DEFAULT_ACCOUNT_MODE",
    "BITGET_FUTURES_DEFAULT_PRODUCT_TYPE",
    "BITGET_FUTURES_DEFAULT_MARGIN_COIN",
    "BITGET_MARKET_FAMILY",
    "BITGET_MARGIN_ACCOUNT_MODE",
    "BITGET_MARGIN_LOAN_TYPE",
    "BITGET_DISCOVERY_SYMBOLS",
    "BITGET_MARGIN_COIN",
    "BITGET_REST_LOCALE",
)
RISK_KEYS = (
    "RISK_HARD_GATING_ENABLED",
    "RISK_ALLOWED_LEVERAGE_MIN",
    "RISK_ALLOWED_LEVERAGE_MAX",
    "RISK_REQUIRE_7X_APPROVAL",
    "RISK_DEFAULT_ACTION",
    "RISK_MIN_SIGNAL_STRENGTH",
    "RISK_MIN_PROBABILITY",
    "RISK_MIN_RISK_SCORE",
    "RISK_MIN_EXPECTED_RETURN_BPS",
    "RISK_MAX_EXPECTED_MAE_BPS",
    "RISK_MIN_PROJECTED_RR",
    "RISK_MAX_POSITION_RISK_PCT",
    "RISK_MAX_ACCOUNT_MARGIN_USAGE",
    "RISK_MAX_ACCOUNT_DRAWDOWN_PCT",
    "RISK_MAX_DAILY_DRAWDOWN_PCT",
    "RISK_MAX_WEEKLY_DRAWDOWN_PCT",
    "RISK_MAX_DAILY_LOSS_USDT",
    "RISK_MAX_POSITION_NOTIONAL_USDT",
    "RISK_MAX_CONCURRENT_POSITIONS",
    "RISK_FORCE_REDUCE_ONLY_ON_ALERT",
    "RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE",
)
ONLINE_DRIFT_KEYS = (
    "ENABLE_ONLINE_DRIFT_BLOCK",
    "ONLINE_DRIFT_LOOKBACK_MINUTES",
    "ONLINE_DRIFT_EVALUATE_ON_ANALYTICS_RUN",
)
MODEL_OPS_KEYS = (
    "MODEL_OPS_ENABLED",
    "MODEL_OPS_REGISTRY_URI",
    "MODEL_OPS_ACTIVE_MODEL_TAG",
    "MODEL_OPS_APPROVAL_REQUIRED",
    "MODEL_OPS_SHADOW_EVAL_ENABLED",
    "MODEL_OPS_DRIFT_ALERT_THRESHOLD",
    "MODEL_OPS_ROLLBACK_ON_DRIFT",
    "MODEL_OPS_MIN_SAMPLE_SIZE",
)
MODEL_CONTRACT_KEYS = (
    "FEATURE_MAX_EVENT_AGE_MS",
    "SIGNAL_MAX_DATA_AGE_MS",
    "SIGNAL_MAX_STRUCTURE_AGE_MS",
    "SIGNAL_MAX_DRAWING_AGE_MS",
    "SIGNAL_MAX_NEWS_AGE_MS",
    "SIGNAL_MAX_ORDERBOOK_AGE_MS",
    "SIGNAL_MAX_FUNDING_FEATURE_AGE_MS",
    "SIGNAL_MAX_OPEN_INTEREST_AGE_MS",
    "SIGNAL_MAX_SPREAD_BPS",
    "SIGNAL_MAX_EXECUTION_COST_BPS",
    "SIGNAL_MAX_ADVERSE_FUNDING_BPS",
    "LEARN_STALE_SIGNAL_MS",
    "LEARN_MAX_FEATURE_AGE_MS",
)
SECURITY_KEYS = (
    "API_AUTH_MODE",
    "SECURITY_REQUIRE_INTERNAL_NETWORK",
    "SECURITY_ALLOW_EVENT_DEBUG_ROUTES",
    "SECURITY_ALLOW_DB_DEBUG_ROUTES",
    "SECURITY_ALLOW_ALERT_REPLAY_ROUTES",
    "INTERNAL_API_KEY",
    "ADMIN_TOKEN",
    "SECRET_KEY",
    "JWT_SECRET",
    "ENCRYPTION_KEY",
)
GATEWAY_HEALTH_KEYS = (
    "HEALTH_URL_MARKET_STREAM",
    "HEALTH_URL_FEATURE_ENGINE",
    "HEALTH_URL_STRUCTURE_ENGINE",
    "HEALTH_URL_SIGNAL_ENGINE",
    "HEALTH_URL_DRAWING_ENGINE",
    "HEALTH_URL_NEWS_ENGINE",
    "HEALTH_URL_LLM_ORCHESTRATOR",
    "HEALTH_URL_PAPER_BROKER",
    "HEALTH_URL_LEARNING_ENGINE",
    "HEALTH_URL_ALERT_ENGINE",
    "HEALTH_URL_MONITOR_ENGINE",
    "HEALTH_URL_LIVE_BROKER",
)
SCRIPT_HEALTH_KEYS = (
    "API_GATEWAY_URL",
    "MARKET_STREAM_URL",
    "FEATURE_ENGINE_URL",
    "STRUCTURE_ENGINE_URL",
    "DRAWING_ENGINE_URL",
    "SIGNAL_ENGINE_URL",
    "NEWS_ENGINE_URL",
    "LLM_ORCH_URL",
    "PAPER_BROKER_URL",
    "LEARNING_ENGINE_URL",
    "ALERT_ENGINE_URL",
    "MONITOR_ENGINE_URL",
    "LIVE_BROKER_URL",
    "DASHBOARD_URL",
)
COMPOSE_DATASTORE_KEYS = (
    "DATABASE_URL_DOCKER",
    "REDIS_URL_DOCKER",
)


def _parse_env_file(path: Path) -> tuple[dict[str, str], list[str]]:
    data: dict[str, str] = {}
    duplicates: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key in data:
            duplicates.append(key)
        data[key] = value
    return data, duplicates


@pytest.mark.parametrize("filename", EXAMPLE_FILES)
def test_example_env_files_have_no_duplicate_keys(filename: str) -> None:
    path = REPO_ROOT / filename
    assert path.is_file(), f"{filename} fehlt"
    _, duplicates = _parse_env_file(path)
    assert duplicates == [], f"doppelte Keys in {filename}: {duplicates}"


def test_env_catalog_contains_required_control_keys() -> None:
    data, _ = _parse_env_file(REPO_ROOT / ".env.example")
    for key in (
        LIVE_KEYS
        + EXIT_KEYS
        + RISK_KEYS
        + MODEL_OPS_KEYS
        + ONLINE_DRIFT_KEYS
        + MODEL_CONTRACT_KEYS
        + SECURITY_KEYS
        + GATEWAY_HEALTH_KEYS
        + SCRIPT_HEALTH_KEYS
        + COMPOSE_DATASTORE_KEYS
        + BITGET_PRIVATE_KEYS
    ):
        assert key in data, f"{key} fehlt in .env.example"


def test_local_profile_keeps_demo_fixture_and_fake_paths_local_only() -> None:
    data, _ = _parse_env_file(REPO_ROOT / ".env.local.example")
    assert data["PRODUCTION"] == "false"
    assert data["APP_ENV"] == "local"
    assert data["ADMIN_TOKEN"] == "example_only_admin_token_32_chars_min_________"
    assert data["INTERNAL_API_KEY"] == "example_only_internal_svc_key_32chrs_______"
    assert data["GATEWAY_JWT_SECRET"] == "example_only_gateway_jwt_secret_32char___"
    assert data["EXECUTION_MODE"] == "paper"
    assert data["STRATEGY_EXEC_MODE"] == "manual"
    assert data["SHADOW_TRADE_ENABLE"] == "false"
    assert data["LIVE_TRADE_ENABLE"] == "false"
    assert data["LIVE_BROKER_ENABLED"] == "false"
    assert data["API_AUTH_MODE"] == "none"
    assert data["LIVE_BROKER_PORT"] == "8120"
    assert data["BITGET_DEMO_ENABLED"] == "true"
    assert data["PAPER_SIM_MODE"] == "true"
    assert data["PAPER_CONTRACT_CONFIG_MODE"] == "fixture"
    assert data["NEWS_FIXTURE_MODE"] == "true"
    assert data["LLM_USE_FAKE_PROVIDER"] == "true"
    assert data["TELEGRAM_DRY_RUN"] == "true"
    assert data["PAPER_DEFAULT_LEVERAGE"] == "7"
    assert data["PAPER_MAX_LEVERAGE"] == "75"
    assert data["RISK_DEFAULT_ACTION"] == "do_not_trade"
    assert "localhost" in data["APP_BASE_URL"] or "127.0.0.1" in data["APP_BASE_URL"]
    assert "localhost" in data["NEXT_PUBLIC_API_BASE_URL"] or "127.0.0.1" in data["NEXT_PUBLIC_API_BASE_URL"]
    assert "@postgres:" in data["DATABASE_URL_DOCKER"]
    assert data["REDIS_URL_DOCKER"].startswith("redis://redis:")
    assert data["HEALTH_URL_LIVE_BROKER"].endswith("/ready")
    assert data["STRUCTURE_ENGINE_URL"] == "http://localhost:8030"
    assert data["ORDER_IDEMPOTENCY_PREFIX"] == "bgai-local"
    assert data["INSTRUMENT_CATALOG_REFRESH_INTERVAL_SEC"] == "120"
    assert data["INSTRUMENT_CATALOG_CACHE_TTL_SEC"] == "300"
    assert data["INSTRUMENT_CATALOG_MAX_STALE_SEC"] == "900"
    assert data["LIVE_ALLOWED_MARKET_FAMILIES"] == ""
    assert data["LIVE_REQUIRE_EXECUTION_BINDING"] == "false"
    assert data["LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN"] == "false"
    assert data["REQUIRE_SHADOW_MATCH_BEFORE_LIVE"] == "false"
    assert data["BITGET_UNIVERSE_MARKET_FAMILIES"] == "spot,margin,futures"
    assert data["BITGET_FUTURES_ALLOWED_PRODUCT_TYPES"] == "USDT-FUTURES,USDC-FUTURES,COIN-FUTURES"
    assert data["BITGET_UNIVERSE_SYMBOLS"] == "BTCUSDT,ETHUSDT"
    assert data["BITGET_WATCHLIST_SYMBOLS"] == "BTCUSDT,ETHUSDT"
    assert data["FEATURE_SCOPE_SYMBOLS"] == "BTCUSDT,ETHUSDT"
    assert data["FEATURE_SCOPE_TIMEFRAMES"] == "1m,5m,15m,1H,4H"
    assert data["SIGNAL_SCOPE_SYMBOLS"] == "BTCUSDT,ETHUSDT"
    assert data["BITGET_MARKET_FAMILY"] == ""
    assert data["BITGET_MARGIN_ACCOUNT_MODE"] == "isolated"
    assert data["BITGET_MARGIN_LOAN_TYPE"] == "normal"
    assert data["BITGET_SPOT_DEFAULT_QUOTE_COIN"] == "USDT"
    assert data["BITGET_MARGIN_DEFAULT_QUOTE_COIN"] == "USDT"
    assert data["BITGET_MARGIN_DEFAULT_ACCOUNT_MODE"] == "isolated"
    assert data["BITGET_FUTURES_DEFAULT_PRODUCT_TYPE"] == ""
    assert data["BITGET_FUTURES_DEFAULT_MARGIN_COIN"] == ""
    assert data["BITGET_MARGIN_COIN"] == "USDT"
    assert data["BITGET_REST_LOCALE"] == "en-US"
    assert data["LIVE_ORDER_TIMEOUT_SEC"] == "300"
    assert data["LIVE_BROKER_SIGNAL_STREAM"] == "events:signal_created"
    assert "events:trade_opened" in data["LIVE_BROKER_REFERENCE_STREAMS"]
    assert "live-broker=http://localhost:8120" in data["MONITOR_SERVICE_URLS"]
    assert "live-broker" in data["MONITOR_STREAM_GROUPS"]


def test_shadow_profile_is_real_host_and_non_live_execution() -> None:
    data, _ = _parse_env_file(REPO_ROOT / ".env.shadow.example")
    assert data["PRODUCTION"] == "true"
    assert data["APP_ENV"] == "shadow"
    assert data["EXECUTION_MODE"] == "shadow"
    assert data["GATEWAY_ENFORCE_SENSITIVE_AUTH"] == "true"
    assert data["GATEWAY_ALLOW_LEGACY_ADMIN_TOKEN"] == "false"
    assert data["GATEWAY_JWT_SECRET"] == "<CHANGEME>"
    assert data["INTERNAL_API_KEY"] == "<CHANGEME>"
    assert data["STRATEGY_EXEC_MODE"] == "manual"
    assert data["API_AUTH_MODE"] == "api_key"
    assert data["LIVE_BROKER_PORT"] == "8120"
    assert data["LIVE_BROKER_ENABLED"] == "true"
    assert data["SHADOW_TRADE_ENABLE"] == "true"
    assert data["BITGET_DEMO_ENABLED"] == "false"
    assert data["PAPER_SIM_MODE"] == "false"
    assert data["PAPER_CONTRACT_CONFIG_MODE"] == "live"
    assert data["NEWS_FIXTURE_MODE"] == "false"
    assert data["LLM_USE_FAKE_PROVIDER"] == "false"
    assert data["TELEGRAM_DRY_RUN"] == "false"
    assert data["LIVE_TRADE_ENABLE"] == "false"
    assert data["PAPER_DEFAULT_LEVERAGE"] == "7"
    assert data["PAPER_MAX_LEVERAGE"] == "75"
    assert data["RISK_ALLOWED_LEVERAGE_MAX"] == "7"
    assert data["RISK_DEFAULT_ACTION"] == "do_not_trade"
    assert data["RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE"] == "7"
    assert "@postgres:" in data["DATABASE_URL_DOCKER"]
    assert "localhost" not in data["DATABASE_URL"]
    assert data["REDIS_URL_DOCKER"].startswith("redis://redis:")
    assert "localhost" not in data["REDIS_URL"]
    assert data["HEALTH_URL_MONITOR_ENGINE"].endswith("/ready")
    assert data["ORDER_IDEMPOTENCY_PREFIX"] == "bgai-shadow"
    assert data["INSTRUMENT_CATALOG_REFRESH_INTERVAL_SEC"] == "300"
    assert data["INSTRUMENT_CATALOG_CACHE_TTL_SEC"] == "900"
    assert data["INSTRUMENT_CATALOG_MAX_STALE_SEC"] == "1800"
    assert data["LIVE_ALLOWED_MARKET_FAMILIES"] == "futures,spot,margin"
    assert data["LIVE_REQUIRE_EXECUTION_BINDING"] == "true"
    assert data["LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN"] == "true"
    assert data["REQUIRE_SHADOW_MATCH_BEFORE_LIVE"] == "true"
    assert data["BITGET_UNIVERSE_MARKET_FAMILIES"] == "spot,margin,futures"
    assert data["BITGET_UNIVERSE_SYMBOLS"] == "<SET_REAL_VISIBLE_UNIVERSE_SYMBOLS_FROM_DISCOVERY>"
    assert data["BITGET_MARKET_FAMILY"] == ""
    assert data["BITGET_MARGIN_ACCOUNT_MODE"] == "isolated"
    assert data["BITGET_MARGIN_LOAN_TYPE"] == "normal"
    assert data["BITGET_MARGIN_COIN"] == "USDT"
    assert data["BITGET_REST_LOCALE"] == "en-US"
    assert data["LIVE_ORDER_TIMEOUT_SEC"] == "300"
    assert data["LIVE_BROKER_SIGNAL_STREAM"] == "events:signal_created"
    assert "events:trade_updated" in data["LIVE_BROKER_REFERENCE_STREAMS"]
    assert "live-broker=http://live-broker:8120" in data["MONITOR_SERVICE_URLS"]
    assert "live-broker" in data["MONITOR_STREAM_GROUPS"]
    for key in (
        "APP_BASE_URL",
        "FRONTEND_URL",
        "DATABASE_URL",
        "REDIS_URL",
        "NEXT_PUBLIC_API_BASE_URL",
    ):
        assert "localhost" not in data[key], f"{key} darf im shadow-Profil nicht localhost sein"


def test_production_profile_is_real_host_and_fake_free() -> None:
    data, _ = _parse_env_file(REPO_ROOT / ".env.production.example")
    assert data["PRODUCTION"] == "true"
    assert data["APP_ENV"] == "production"
    assert data["GATEWAY_ENFORCE_SENSITIVE_AUTH"] == "true"
    assert data["GATEWAY_ALLOW_LEGACY_ADMIN_TOKEN"] == "false"
    assert data["GATEWAY_JWT_SECRET"] == "YOUR_API_KEY_HERE"
    assert data["INTERNAL_API_KEY"] == "YOUR_API_KEY_HERE"
    assert data["DEBUG"] == "false"
    assert data["LOG_FORMAT"] == "json"
    assert data["VAULT_MODE"] == "hashicorp"
    assert data["EXECUTION_MODE"] == "shadow"
    assert data["STRATEGY_EXEC_MODE"] == "manual"
    assert data["SHADOW_TRADE_ENABLE"] == "true"
    assert data["API_AUTH_MODE"] == "api_key"
    assert data["LIVE_BROKER_PORT"] == "8120"
    assert data["LIVE_BROKER_ENABLED"] == "true"
    assert data["BITGET_DEMO_ENABLED"] == "false"
    assert data["PAPER_SIM_MODE"] == "false"
    assert data["PAPER_CONTRACT_CONFIG_MODE"] == "live"
    assert data["NEWS_FIXTURE_MODE"] == "false"
    assert data["LLM_USE_FAKE_PROVIDER"] == "false"
    assert data["TELEGRAM_DRY_RUN"] == "false"
    assert data["NODE_ENV"] == "production"
    assert data["NEXT_PUBLIC_ENABLE_ADMIN"] == "false"
    assert data["LIVE_TRADE_ENABLE"] == "false"
    assert data["PAPER_DEFAULT_LEVERAGE"] == "7"
    assert data["PAPER_MAX_LEVERAGE"] == "75"
    assert data["RISK_ALLOWED_LEVERAGE_MIN"] == "7"
    assert data["RISK_ALLOWED_LEVERAGE_MAX"] == "7"
    assert data["LEVERAGE_FAMILY_MAX_CAP_SPOT"] == "5"
    assert data["LEVERAGE_FAMILY_MAX_CAP_MARGIN"] == "7"
    assert data["LEVERAGE_FAMILY_MAX_CAP_FUTURES"] == "7"
    assert data["RISK_DEFAULT_ACTION"] == "do_not_trade"
    assert data["RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE"] == "7"
    assert "@postgres:" in data["DATABASE_URL_DOCKER"]
    assert "localhost" not in data["DATABASE_URL"]
    assert data["REDIS_URL_DOCKER"].startswith("redis://redis:")
    assert "localhost" not in data["REDIS_URL"]
    assert data["HEALTH_URL_ALERT_ENGINE"].endswith("/ready")
    assert data["ORDER_IDEMPOTENCY_PREFIX"] == "bgai-prod"
    assert data["INSTRUMENT_CATALOG_REFRESH_INTERVAL_SEC"] == "300"
    assert data["INSTRUMENT_CATALOG_CACHE_TTL_SEC"] == "900"
    assert data["INSTRUMENT_CATALOG_MAX_STALE_SEC"] == "1800"
    assert data["LIVE_ALLOWED_MARKET_FAMILIES"] == "futures"
    assert data["LIVE_REQUIRE_EXECUTION_BINDING"] == "true"
    assert data["LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN"] == "true"
    assert data["REQUIRE_SHADOW_MATCH_BEFORE_LIVE"] == "true"
    assert data["BITGET_UNIVERSE_MARKET_FAMILIES"] == "spot,margin,futures"
    assert data["BITGET_UNIVERSE_SYMBOLS"] == "<SET_REAL_VISIBLE_UNIVERSE_SYMBOLS_FROM_DISCOVERY>"
    assert data["BITGET_MARKET_FAMILY"] == "futures"
    assert data["BITGET_FUTURES_DEFAULT_PRODUCT_TYPE"] == "USDT-FUTURES"
    assert data["BITGET_PRODUCT_TYPE"] == "USDT-FUTURES"
    assert data["BITGET_SYMBOL"] == "BTCUSDT"
    assert data["BITGET_DISCOVERY_SYMBOLS"] == "BTCUSDT,ETHUSDT"
    assert data["BITGET_MARGIN_ACCOUNT_MODE"] == "isolated"
    assert data["BITGET_MARGIN_LOAN_TYPE"] == "normal"
    assert data["BITGET_MARGIN_COIN"] == "USDT"
    assert data["BITGET_REST_LOCALE"] == "en-US"
    assert data["LIVE_ORDER_TIMEOUT_SEC"] == "300"
    assert data["LIVE_BROKER_SIGNAL_STREAM"] == "events:signal_created"
    assert "events:trade_closed" in data["LIVE_BROKER_REFERENCE_STREAMS"]
    assert "live-broker=http://live-broker:8120" in data["MONITOR_SERVICE_URLS"]
    assert "live-broker" in data["MONITOR_STREAM_GROUPS"]
    for key in (
        "APP_BASE_URL",
        "FRONTEND_URL",
        "DATABASE_URL",
        "REDIS_URL",
        "NEXT_PUBLIC_API_BASE_URL",
    ):
        assert "localhost" not in data[key], f"{key} darf im production-Profil nicht localhost sein"


def test_test_profile_stays_deterministic_and_test_scoped() -> None:
    data, _ = _parse_env_file(REPO_ROOT / ".env.test.example")
    assert data["PRODUCTION"] == "false"
    assert data["APP_ENV"] == "test"
    assert data["CI"] == "true"
    assert data["NODE_ENV"] == "test"
    assert data["EXECUTION_MODE"] == "paper"
    assert data["STRATEGY_EXEC_MODE"] == "manual"
    assert data["SHADOW_TRADE_ENABLE"] == "false"
    assert data["LIVE_TRADE_ENABLE"] == "false"
    assert data["LIVE_BROKER_ENABLED"] == "false"
    assert data["API_AUTH_MODE"] == "none"
    assert data["LIVE_BROKER_PORT"] == "8120"
    assert data["INTERNAL_API_KEY"] == "<SET_ME>"
    assert data["NEWS_FIXTURE_MODE"] == "true"
    assert data["LLM_USE_FAKE_PROVIDER"] == "true"
    assert data["BITGET_DEMO_ENABLED"] == "true"
    assert data["PAPER_SIM_MODE"] == "true"
    assert data["PAPER_CONTRACT_CONFIG_MODE"] == "fixture"
    assert data["PAPER_DEFAULT_LEVERAGE"] == "7"
    assert data["PAPER_MAX_LEVERAGE"] == "75"
    assert data["RISK_DEFAULT_ACTION"] == "do_not_trade"
    assert data["RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE"] == "7"
    assert data["TEST_DATABASE_URL"].endswith("/bitget_test")
    assert data["TEST_REDIS_URL"].endswith("/1")
    assert "@postgres:" in data["DATABASE_URL_DOCKER"]
    assert data["REDIS_URL_DOCKER"].startswith("redis://redis:")
    assert data["ORDER_IDEMPOTENCY_PREFIX"] == "bgai-test"
    assert data["INSTRUMENT_CATALOG_REFRESH_INTERVAL_SEC"] == "60"
    assert data["INSTRUMENT_CATALOG_CACHE_TTL_SEC"] == "120"
    assert data["INSTRUMENT_CATALOG_MAX_STALE_SEC"] == "300"
    assert data["LIVE_ALLOWED_MARKET_FAMILIES"] == ""
    assert data["LIVE_REQUIRE_EXECUTION_BINDING"] == "false"
    assert data["LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN"] == "false"
    assert data["REQUIRE_SHADOW_MATCH_BEFORE_LIVE"] == "false"
    assert data["BITGET_UNIVERSE_MARKET_FAMILIES"] == "spot,margin,futures"
    assert data["BITGET_UNIVERSE_SYMBOLS"] == "BTCUSDT,ETHUSDT"
    assert data["BITGET_MARKET_FAMILY"] == ""
    assert data["BITGET_MARGIN_ACCOUNT_MODE"] == "isolated"
    assert data["BITGET_MARGIN_LOAN_TYPE"] == "normal"
    assert data["BITGET_MARGIN_COIN"] == "USDT"
    assert data["BITGET_REST_LOCALE"] == "en-US"
    assert data["LIVE_BROKER_HTTP_MAX_RETRIES"] == "1"
    assert data["LIVE_ORDER_TIMEOUT_SEC"] == "60"
    assert data["LIVE_BROKER_SIGNAL_STREAM"] == "events:signal_created"
    assert "events:trade_updated" in data["LIVE_BROKER_REFERENCE_STREAMS"]


def test_demo_example_includes_compose_required_base_values() -> None:
    data, _ = _parse_env_file(REPO_ROOT / ".env.demo.example")
    expected = {
        "APP_BASE_URL": "http://127.0.0.1:8000",
        "FRONTEND_URL": "http://127.0.0.1:3000",
        "CORS_ALLOW_ORIGINS": "http://127.0.0.1:3000",
        "NEXT_PUBLIC_API_BASE_URL": "http://127.0.0.1:8000",
        "NEXT_PUBLIC_WS_BASE_URL": "ws://127.0.0.1:8000",
        "POSTGRES_PASSWORD": "postgres",
        "GRAFANA_ADMIN_PASSWORD": "admin",
    }
    for key, value in expected.items():
        assert data.get(key) == value, f"{key} fehlt oder ist unerwartet in .env.demo.example"


def test_demo_example_keeps_live_and_submit_flags_fail_closed() -> None:
    data, _ = _parse_env_file(REPO_ROOT / ".env.demo.example")
    assert data.get("LIVE_TRADE_ENABLE") == "false"
    assert data.get("DEMO_ORDER_SUBMIT_ENABLE") == "false"
    assert data.get("DEMO_CLOSE_POSITION_ENABLE") == "false"


def test_demo_example_does_not_expose_live_bitget_keys() -> None:
    data, _ = _parse_env_file(REPO_ROOT / ".env.demo.example")
    assert data.get("BITGET_API_KEY", "") == ""
    assert data.get("BITGET_API_SECRET", "") == ""
    assert data.get("BITGET_API_PASSPHRASE", "") == ""
