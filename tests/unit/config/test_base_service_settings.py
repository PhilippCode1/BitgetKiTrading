from __future__ import annotations

import pytest
from config.gateway_settings import GatewaySettings, get_gateway_settings
from config.settings import BaseServiceSettings


def _set_production_env(
    monkeypatch: pytest.MonkeyPatch,
    **overrides: str,
) -> None:
    defaults = {
        "PRODUCTION": "true",
        "APP_ENV": "production",
        "DEBUG": "false",
        "LOG_LEVEL": "INFO",
        "LOG_FORMAT": "json",
        "VAULT_MODE": "hashicorp",
        "VAULT_ADDR": "https://vault.prod.company",
        "VAULT_TOKEN": "vault-token",
        "SHADOW_TRADE_ENABLE": "true",
        "EXECUTION_MODE": "shadow",
        "STRATEGY_EXEC_MODE": "manual",
        "API_AUTH_MODE": "api_key",
        "SECURITY_REQUIRE_INTERNAL_NETWORK": "true",
        "SECURITY_ALLOW_EVENT_DEBUG_ROUTES": "false",
        "SECURITY_ALLOW_DB_DEBUG_ROUTES": "false",
        "SECURITY_ALLOW_ALERT_REPLAY_ROUTES": "false",
        "APP_BASE_URL": "https://api.prod.company",
        "FRONTEND_URL": "https://dashboard.prod.company",
        "CORS_ALLOW_ORIGINS": "https://dashboard.prod.company",
        "LIVE_BROKER_BASE_URL": "https://live-broker.prod.company",
        "LIVE_BROKER_WS_PRIVATE_URL": "wss://live-broker.prod.company/ws/private",
        "INTERNAL_API_KEY": "internal-service-key-12345",
        "ADMIN_TOKEN": "admin-token-123456789012",
        "SECRET_KEY": "secret-key-1234567890ab",
        "JWT_SECRET": "jwt-secret-1234567890ab",
        "ENCRYPTION_KEY": "encryption-key-12345678",
        "GATEWAY_JWT_SECRET": "unit-test-gateway-jwt-secret-32b!",
        "GATEWAY_SEND_HSTS": "true",
        "GATEWAY_ALLOW_LEGACY_ADMIN_TOKEN": "false",
        "GATEWAY_ENFORCE_SENSITIVE_AUTH": "true",
        "DATABASE_URL": "postgresql://postgres:secret@postgres.prod.company:5432/bitget_ai",
        "REDIS_URL": "redis://redis.prod.company:6379/0",
        "BITGET_DEMO_ENABLED": "false",
        "NEWS_FIXTURE_MODE": "false",
        "LLM_USE_FAKE_PROVIDER": "false",
        "PAPER_SIM_MODE": "false",
        "PAPER_CONTRACT_CONFIG_MODE": "live",
        "TELEGRAM_DRY_RUN": "false",
        "RISK_HARD_GATING_ENABLED": "true",
        "RISK_ALLOWED_LEVERAGE_MIN": "7",
        "RISK_ALLOWED_LEVERAGE_MAX": "75",
        "RISK_REQUIRE_7X_APPROVAL": "true",
        "RISK_DEFAULT_ACTION": "do_not_trade",
        "LIVE_KILL_SWITCH_ENABLED": "true",
        "LIVE_TRADE_ENABLE": "false",
        # .env.local kann MODEL_OPS aktivieren; sonst schlaegt Pflichtfeld model_ops_registry_uri fehl.
        "MODEL_OPS_ENABLED": "false",
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        monkeypatch.setenv(key, value)


def test_production_forbids_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_production_env(monkeypatch, DEBUG="true")
    with pytest.raises(ValueError, match="DEBUG"):
        BaseServiceSettings()


def test_production_caps_debug_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_production_env(monkeypatch, LOG_LEVEL="DEBUG")
    s = BaseServiceSettings()
    assert s.log_level == "INFO"


def test_production_requires_api_auth_and_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_production_env(monkeypatch, API_AUTH_MODE="none")
    with pytest.raises(ValueError, match="API_AUTH_MODE"):
        BaseServiceSettings()

    _set_production_env(monkeypatch, ADMIN_TOKEN="")
    with pytest.raises(ValueError, match="admin_token"):
        BaseServiceSettings()


def test_production_forbids_fake_demo_fixture_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_production_env(monkeypatch, LLM_USE_FAKE_PROVIDER="true")
    with pytest.raises(ValueError, match="LLM_USE_FAKE_PROVIDER"):
        BaseServiceSettings()

    _set_production_env(monkeypatch, BITGET_DEMO_ENABLED="true")
    with pytest.raises(ValueError, match="BITGET_DEMO_ENABLED"):
        BaseServiceSettings()


def test_execution_mode_accepts_canonical_and_legacy_env_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EXECUTION_MODE", "shadow")
    monkeypatch.setenv("SHADOW_TRADE_ENABLE", "true")
    assert BaseServiceSettings().execution_mode == "shadow"

    monkeypatch.delenv("EXECUTION_MODE", raising=False)
    monkeypatch.setenv("TRADING_RUNTIME_MODE", "shadow")
    assert BaseServiceSettings().execution_mode == "shadow"


def test_strategy_execution_mode_reads_strategy_exec_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STRATEGY_EXEC_MODE", "auto")
    assert BaseServiceSettings().strategy_execution_mode == "auto"


def test_trade_gates_require_matching_execution_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EXECUTION_MODE", "paper")
    monkeypatch.setenv("SHADOW_TRADE_ENABLE", "true")
    with pytest.raises(ValueError, match="SHADOW_TRADE_ENABLE"):
        BaseServiceSettings()

    monkeypatch.setenv("EXECUTION_MODE", "shadow")
    monkeypatch.setenv("SHADOW_TRADE_ENABLE", "true")
    monkeypatch.setenv("LIVE_TRADE_ENABLE", "true")
    with pytest.raises(ValueError, match="LIVE_TRADE_ENABLE"):
        BaseServiceSettings()


def test_live_mode_forbids_bitget_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PRODUCTION", "false")
    monkeypatch.setenv("EXECUTION_MODE", "live")
    monkeypatch.setenv("LIVE_BROKER_ENABLED", "true")
    monkeypatch.setenv("SHADOW_TRADE_ENABLE", "false")
    monkeypatch.setenv("LIVE_TRADE_ENABLE", "true")
    monkeypatch.setenv("BITGET_DEMO_ENABLED", "true")
    monkeypatch.setenv("STRATEGY_EXEC_MODE", "manual")
    monkeypatch.setenv("RISK_HARD_GATING_ENABLED", "true")
    monkeypatch.setenv("RISK_REQUIRE_7X_APPROVAL", "true")
    monkeypatch.setenv("RISK_ALLOWED_LEVERAGE_MIN", "7")
    monkeypatch.setenv("RISK_ALLOWED_LEVERAGE_MAX", "75")
    monkeypatch.setenv("LIVE_KILL_SWITCH_ENABLED", "true")
    with pytest.raises(ValueError, match="BITGET_DEMO_ENABLED"):
        BaseServiceSettings()


def test_api_auth_mode_accepts_canonical_and_legacy_env_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("API_AUTH_MODE", "oauth2")
    assert BaseServiceSettings().api_auth_mode == "oauth2"

    monkeypatch.delenv("API_AUTH_MODE", raising=False)
    monkeypatch.setenv("SECURITY_EDGE_AUTH_MODE", "mtls")
    assert BaseServiceSettings().api_auth_mode == "mtls"


def test_production_requires_https_public_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_production_env(monkeypatch, APP_BASE_URL="http://api.prod.company")
    with pytest.raises(ValueError, match="APP_BASE_URL"):
        BaseServiceSettings()


def test_production_requires_minimum_core_secret_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_production_env(monkeypatch, JWT_SECRET="zu_kurz")
    with pytest.raises(ValueError, match="JWT_SECRET"):
        BaseServiceSettings()


def test_drawdown_limit_chain_rejects_inverted_hierarchy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PRODUCTION", "false")
    monkeypatch.setenv("EXECUTION_MODE", "paper")
    monkeypatch.setenv("SHADOW_TRADE_ENABLE", "false")
    monkeypatch.setenv("LIVE_TRADE_ENABLE", "false")
    monkeypatch.setenv("LIVE_BROKER_ENABLED", "false")
    monkeypatch.setenv("STRATEGY_EXEC_MODE", "manual")
    monkeypatch.setenv("RISK_HARD_GATING_ENABLED", "true")
    monkeypatch.setenv("RISK_REQUIRE_7X_APPROVAL", "true")
    monkeypatch.setenv("RISK_ALLOWED_LEVERAGE_MIN", "7")
    monkeypatch.setenv("RISK_ALLOWED_LEVERAGE_MAX", "75")
    monkeypatch.setenv("LIVE_KILL_SWITCH_ENABLED", "true")
    monkeypatch.setenv("RISK_MAX_DAILY_DRAWDOWN_PCT", "0.10")
    monkeypatch.setenv("RISK_MAX_WEEKLY_DRAWDOWN_PCT", "0.08")
    with pytest.raises(ValueError, match="RISK_MAX_DAILY_DRAWDOWN_PCT"):
        BaseServiceSettings()


def test_leverage_policy_is_hard_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RISK_ALLOWED_LEVERAGE_MIN", "8")
    with pytest.raises(ValueError, match="RISK_ALLOWED_LEVERAGE_MIN"):
        BaseServiceSettings()

    monkeypatch.delenv("RISK_ALLOWED_LEVERAGE_MIN", raising=False)
    monkeypatch.setenv("RISK_ALLOWED_LEVERAGE_MAX", "7")
    # Unified-Leverage-Validator: Family-/Cold-Start-/Shadow-Caps duerfen RISK_MAX nicht uebersteigen.
    monkeypatch.setenv("LEVERAGE_FAMILY_MAX_CAP_SPOT", "5")
    monkeypatch.setenv("LEVERAGE_FAMILY_MAX_CAP_MARGIN", "7")
    monkeypatch.setenv("LEVERAGE_FAMILY_MAX_CAP_FUTURES", "7")
    monkeypatch.setenv("LEVERAGE_COLD_START_MAX_CAP", "7")
    monkeypatch.setenv("LEVERAGE_SHADOW_DIVERGENCE_SOFT_MAX_LEVERAGE", "7")
    assert BaseServiceSettings().risk_allowed_leverage_max == 7

    monkeypatch.delenv("RISK_ALLOWED_LEVERAGE_MAX", raising=False)
    monkeypatch.setenv("RISK_ALLOWED_LEVERAGE_MAX", "80")
    with pytest.raises(ValueError, match="RISK_ALLOWED_LEVERAGE_MAX"):
        BaseServiceSettings()


def test_universe_scope_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PRODUCTION", "false")
    monkeypatch.setenv("EXECUTION_MODE", "paper")
    monkeypatch.setenv("SHADOW_TRADE_ENABLE", "false")
    monkeypatch.setenv("LIVE_TRADE_ENABLE", "false")
    monkeypatch.setenv("LIVE_BROKER_ENABLED", "false")
    monkeypatch.setenv("STRATEGY_EXEC_MODE", "manual")
    monkeypatch.setenv("RISK_HARD_GATING_ENABLED", "true")
    monkeypatch.setenv("RISK_REQUIRE_7X_APPROVAL", "true")
    monkeypatch.setenv("RISK_ALLOWED_LEVERAGE_MIN", "7")
    monkeypatch.setenv("RISK_ALLOWED_LEVERAGE_MAX", "75")
    monkeypatch.setenv("LIVE_KILL_SWITCH_ENABLED", "true")
    monkeypatch.setenv("BITGET_UNIVERSE_MARKET_FAMILIES", "spot,futures")
    monkeypatch.setenv("LIVE_ALLOWED_MARKET_FAMILIES", "spot,margin")
    with pytest.raises(ValueError, match="LIVE_ALLOWED_MARKET_FAMILIES"):
        BaseServiceSettings()


def test_gateway_settings_cache_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    get_gateway_settings.cache_clear()
    try:
        monkeypatch.setenv("DASHBOARD_PAGE_SIZE", "77")
        g = get_gateway_settings()
        assert g.dashboard_page_size == 77
    finally:
        get_gateway_settings.cache_clear()


def test_gateway_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    get_gateway_settings.cache_clear()
    try:
        monkeypatch.setenv("APP_PORT", "8000")
        # Leere Strings ueberschreiben .env.local (env schlaegt dotenv); delenv laesst dotenv gewinnen.
        monkeypatch.setenv("DASHBOARD_WATCHLIST_SYMBOLS", "")
        monkeypatch.setenv("NEXT_PUBLIC_WATCHLIST_SYMBOLS", "")
        monkeypatch.setenv("DASHBOARD_DEFAULT_SYMBOL", "")
        monkeypatch.setenv("NEXT_PUBLIC_DEFAULT_SYMBOL", "")
        monkeypatch.setenv("BITGET_WATCHLIST_SYMBOLS", "ETHUSDT,BTCUSDT")
        g = GatewaySettings()
        assert g.app_port == 8000
        assert g.dashboard_default_symbol == "ETHUSDT"
        assert g.next_public_default_symbol == "ETHUSDT"
        assert g.dashboard_default_market_family == "spot"
    finally:
        get_gateway_settings.cache_clear()


def test_gateway_sse_cookie_secure_empty_string_is_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_gateway_settings.cache_clear()
    try:
        monkeypatch.setenv("APP_PORT", "8000")
        monkeypatch.setenv("MODEL_OPS_ENABLED", "false")
        monkeypatch.setenv("DASHBOARD_WATCHLIST_SYMBOLS", "")
        monkeypatch.setenv("NEXT_PUBLIC_WATCHLIST_SYMBOLS", "")
        monkeypatch.setenv("DASHBOARD_DEFAULT_SYMBOL", "")
        monkeypatch.setenv("NEXT_PUBLIC_DEFAULT_SYMBOL", "")
        monkeypatch.setenv("BITGET_WATCHLIST_SYMBOLS", "ETHUSDT,BTCUSDT")
        monkeypatch.setenv("GATEWAY_SSE_COOKIE_SECURE", "")
        monkeypatch.setenv("GATEWAY_SEND_HSTS", "")
        g = GatewaySettings()
        assert g.gateway_sse_cookie_secure is None
        assert g.gateway_send_hsts is False
    finally:
        get_gateway_settings.cache_clear()


def test_gateway_sse_cookie_samesite_none_requires_secure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_gateway_settings.cache_clear()
    try:
        monkeypatch.setenv("GATEWAY_SSE_COOKIE_SAMESITE", "none")
        monkeypatch.setenv("PRODUCTION", "false")
        monkeypatch.delenv("GATEWAY_SSE_COOKIE_SECURE", raising=False)
        with pytest.raises(ValueError, match="none"):
            GatewaySettings()
    finally:
        get_gateway_settings.cache_clear()


def test_gateway_sse_cookie_samesite_none_ok_with_secure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_gateway_settings.cache_clear()
    try:
        monkeypatch.setenv("GATEWAY_SSE_COOKIE_SAMESITE", "none")
        monkeypatch.setenv("PRODUCTION", "false")
        monkeypatch.setenv("GATEWAY_SSE_COOKIE_SECURE", "true")
        g = GatewaySettings()
        assert g.gateway_sse_cookie_samesite == "none"
        assert g.sse_cookie_secure_flag() is True
    finally:
        get_gateway_settings.cache_clear()


def test_gateway_production_requires_hsts_with_https_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_gateway_settings.cache_clear()
    try:
        _set_production_env(monkeypatch, GATEWAY_SEND_HSTS="false")
        with pytest.raises(ValueError, match="GATEWAY_SEND_HSTS"):
            GatewaySettings()
    finally:
        get_gateway_settings.cache_clear()


def test_gateway_production_rejects_localhost_backends(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_gateway_settings.cache_clear()
    try:
        _set_production_env(
            monkeypatch,
            DATABASE_URL="postgresql://postgres:secret@localhost:5432/bitget_ai",
            REDIS_URL="redis://localhost:6379/0",
        )
        with pytest.raises(ValueError, match="localhost"):
            GatewaySettings()
    finally:
        get_gateway_settings.cache_clear()


def test_gateway_live_strict_prerequisites_enforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_gateway_settings.cache_clear()
    try:
        _set_production_env(
            monkeypatch,
            EXECUTION_MODE="live",
            SHADOW_TRADE_ENABLE="false",
            LIVE_TRADE_ENABLE="true",
            LIVE_BROKER_ENABLED="true",
            EXECUTION_LIVE_STRICT_PREREQUISITES="true",
            COMMERCIAL_ENABLED="false",
            RISK_ELEVATED_LEVERAGE_LIVE_ACK="true",
        )
        with pytest.raises(ValueError, match="EXECUTION_LIVE_STRICT_PREREQUISITES"):
            GatewaySettings()
    finally:
        get_gateway_settings.cache_clear()


def test_gateway_live_strict_prerequisites_ok_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_gateway_settings.cache_clear()
    try:
        meter = "commercial-meter-secret-32chars-minimum!!"
        _set_production_env(
            monkeypatch,
            EXECUTION_MODE="live",
            SHADOW_TRADE_ENABLE="false",
            LIVE_TRADE_ENABLE="true",
            LIVE_BROKER_ENABLED="true",
            EXECUTION_LIVE_STRICT_PREREQUISITES="true",
            COMMERCIAL_ENABLED="true",
            COMMERCIAL_TELEGRAM_REQUIRED_FOR_CONSOLE="true",
            TELEGRAM_BOT_USERNAME="example_ops_bot",
            COMMERCIAL_METER_SECRET=meter,
            LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN="true",
            RISK_ELEVATED_LEVERAGE_LIVE_ACK="true",
        )
        g = GatewaySettings()
        assert g.execution_live_strict_prerequisites is True
        assert g.live_require_operator_release_for_live_open is True
    finally:
        get_gateway_settings.cache_clear()


def test_production_live_elevated_leverage_requires_ack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_production_env(
        monkeypatch,
        EXECUTION_MODE="live",
        SHADOW_TRADE_ENABLE="false",
        LIVE_TRADE_ENABLE="true",
        LIVE_BROKER_ENABLED="true",
        RISK_ALLOWED_LEVERAGE_MAX="75",
        RISK_ELEVATED_LEVERAGE_LIVE_ACK="false",
    )
    with pytest.raises(ValueError, match="RISK_ELEVATED_LEVERAGE_LIVE_ACK"):
        BaseServiceSettings()


def test_production_live_elevated_leverage_ok_with_ack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_production_env(
        monkeypatch,
        EXECUTION_MODE="live",
        SHADOW_TRADE_ENABLE="false",
        LIVE_TRADE_ENABLE="true",
        LIVE_BROKER_ENABLED="true",
        RISK_ALLOWED_LEVERAGE_MAX="75",
        RISK_ELEVATED_LEVERAGE_LIVE_ACK="true",
    )
    s = BaseServiceSettings()
    assert s.risk_allowed_leverage_max == 75
    assert s.risk_elevated_leverage_live_ack is True


def test_production_live_max_seven_no_ack_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_production_env(
        monkeypatch,
        EXECUTION_MODE="live",
        SHADOW_TRADE_ENABLE="false",
        LIVE_TRADE_ENABLE="true",
        LIVE_BROKER_ENABLED="true",
        RISK_ALLOWED_LEVERAGE_MAX="7",
        RISK_ELEVATED_LEVERAGE_LIVE_ACK="false",
    )
    s = BaseServiceSettings()
    assert s.risk_allowed_leverage_max == 7


def test_production_shadow_high_max_without_live_no_ack_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Schema-Obergrenze 75 ist erlaubt im Shadow-Betrieb ohne Live-Orders."""
    _set_production_env(
        monkeypatch,
        RISK_ALLOWED_LEVERAGE_MAX="75",
        LIVE_TRADE_ENABLE="false",
        RISK_ELEVATED_LEVERAGE_LIVE_ACK="false",
    )
    s = BaseServiceSettings()
    assert s.execution_mode == "shadow"
    assert s.risk_allowed_leverage_max == 75


def test_service_internal_api_key_reads_service_internal_api_key_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INTERNAL_API_KEY", raising=False)
    monkeypatch.setenv("SERVICE_INTERNAL_API_KEY", "alias-only-internal-key-32b!")
    s = BaseServiceSettings()
    assert s.service_internal_api_key == "alias-only-internal-key-32b!"
