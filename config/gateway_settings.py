"""
API-Gateway-spezifische Settings (lesen ausschliesslich aus ENV).
"""

from __future__ import annotations

from functools import lru_cache
from typing import ClassVar, Self
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from config.internal_service_discovery import http_base_from_health_or_ready_url
from config.settings import MIN_PRODUCTION_SECRET_LEN, BaseServiceSettings

# Peer-Readiness: bei Docker-DSN muss jede URL einen anderen Container erreichen (kein Loopback).
_GATEWAY_HEALTH_PEER_FIELDS: tuple[tuple[str, str], ...] = (
    ("health_url_market_stream", "HEALTH_URL_MARKET_STREAM"),
    ("health_url_feature_engine", "HEALTH_URL_FEATURE_ENGINE"),
    ("health_url_structure_engine", "HEALTH_URL_STRUCTURE_ENGINE"),
    ("health_url_signal_engine", "HEALTH_URL_SIGNAL_ENGINE"),
    ("health_url_drawing_engine", "HEALTH_URL_DRAWING_ENGINE"),
    ("health_url_news_engine", "HEALTH_URL_NEWS_ENGINE"),
    ("health_url_llm_orchestrator", "HEALTH_URL_LLM_ORCHESTRATOR"),
    ("health_url_paper_broker", "HEALTH_URL_PAPER_BROKER"),
    ("health_url_learning_engine", "HEALTH_URL_LEARNING_ENGINE"),
    ("health_url_alert_engine", "HEALTH_URL_ALERT_ENGINE"),
    ("health_url_monitor_engine", "HEALTH_URL_MONITOR_ENGINE"),
    ("health_url_live_broker", "HEALTH_URL_LIVE_BROKER"),
)


def _hostname_is_loopback(hostname: str) -> bool:
    h = hostname.strip().lower()
    return h in ("localhost", "127.0.0.1", "::1", "[::1]")


class GatewaySettings(BaseServiceSettings):
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
    gateway_readiness_redis_probe_budget_ms: int = Field(
        default=500,
        ge=50,
        le=5_000,
        alias="GATEWAY_READINESS_REDIS_PROBE_BUDGET_MS",
        description="Zeitfenster (ms) fuer schnelle Redis-PING-Retries im GET /ready (Kern-Check).",
    )
    gateway_readiness_redis_probe_max_attempts: int = Field(
        default=3,
        ge=1,
        le=5,
        alias="GATEWAY_READINESS_REDIS_PROBE_MAX_ATTEMPTS",
        description="Max. Redis-PING-Versuche innerhalb des Probe-Budgets.",
    )
    gateway_readiness_redis_probe_socket_sec: float = Field(
        default=0.15,
        ge=0.05,
        le=2.0,
        alias="GATEWAY_READINESS_REDIS_PROBE_SOCKET_SEC",
        description="Socket-Timeout (s) pro schnellem PING in /ready (niedrig, damit 3x in <500ms).",
    )
    app_port: int = Field(default=8000, alias="APP_PORT")
    cors_allow_origins: str = Field(
        default="http://localhost:3000", alias="CORS_ALLOW_ORIGINS"
    )

    health_url_market_stream: str = Field(default="", alias="HEALTH_URL_MARKET_STREAM")
    health_url_feature_engine: str = Field(
        default="", alias="HEALTH_URL_FEATURE_ENGINE"
    )
    health_url_structure_engine: str = Field(
        default="", alias="HEALTH_URL_STRUCTURE_ENGINE"
    )
    health_url_signal_engine: str = Field(default="", alias="HEALTH_URL_SIGNAL_ENGINE")
    health_url_drawing_engine: str = Field(
        default="", alias="HEALTH_URL_DRAWING_ENGINE"
    )
    health_url_news_engine: str = Field(default="", alias="HEALTH_URL_NEWS_ENGINE")
    health_url_llm_orchestrator: str = Field(
        default="", alias="HEALTH_URL_LLM_ORCHESTRATOR"
    )
    llm_orchestrator_base_url: str = Field(
        default="",
        alias="LLM_ORCH_BASE_URL",
        description=(
            "HTTP-Basis-URL des LLM-Orchestators (ohne Pfad) fuer Gateway-Forward. "
            "Leer = aus HEALTH_URL_LLM_ORCHESTRATOR (Scheme/Host/Port) ableiten."
        ),
    )
    health_url_paper_broker: str = Field(
        default="http://localhost:8085/health", alias="HEALTH_URL_PAPER_BROKER"
    )
    health_url_learning_engine: str = Field(
        default="http://localhost:8090/health", alias="HEALTH_URL_LEARNING_ENGINE"
    )
    health_url_alert_engine: str = Field(default="", alias="HEALTH_URL_ALERT_ENGINE")
    health_url_monitor_engine: str = Field(
        default="", alias="HEALTH_URL_MONITOR_ENGINE"
    )
    health_url_live_broker: str = Field(default="", alias="HEALTH_URL_LIVE_BROKER")

    dashboard_default_symbol: str = Field(default="", alias="DASHBOARD_DEFAULT_SYMBOL")
    next_public_default_symbol: str = Field(default="", alias="NEXT_PUBLIC_DEFAULT_SYMBOL")
    dashboard_default_market_family: str = Field(
        default="",
        alias="DASHBOARD_DEFAULT_MARKET_FAMILY",
    )
    next_public_default_market_family: str = Field(
        default="",
        alias="NEXT_PUBLIC_DEFAULT_MARKET_FAMILY",
    )
    next_public_default_product: str = Field(
        default="",
        alias="NEXT_PUBLIC_DEFAULT_PRODUCT",
    )
    dashboard_watchlist_symbols: str = Field(
        default="",
        alias="DASHBOARD_WATCHLIST_SYMBOLS",
    )
    next_public_watchlist_symbols: str = Field(
        default="",
        alias="NEXT_PUBLIC_WATCHLIST_SYMBOLS",
    )
    data_stale_warn_ms: int = Field(default=900000, alias="DATA_STALE_WARN_MS")
    dashboard_page_size: int = Field(default=50, alias="DASHBOARD_PAGE_SIZE")
    admin_token: str = Field(default="", alias="ADMIN_TOKEN")
    dashboard_default_tf: str = Field(default="1m", alias="DASHBOARD_DEFAULT_TF")
    live_state_default_candles: int = Field(
        default=500, alias="LIVE_STATE_DEFAULT_CANDLES"
    )
    live_state_max_candles: int = Field(default=2000, alias="LIVE_STATE_MAX_CANDLES")
    live_sse_enabled: bool = Field(default=True, alias="LIVE_SSE_ENABLED")
    live_sse_ping_sec: int = Field(default=15, alias="LIVE_SSE_PING_SEC")

    gateway_sse_cookie_name: str = Field(default="gateway_sse_v1", alias="GATEWAY_SSE_COOKIE_NAME")
    gateway_sse_cookie_ttl_sec: int = Field(default=900, alias="GATEWAY_SSE_COOKIE_TTL_SEC")
    gateway_sse_signing_secret: str = Field(default="", alias="GATEWAY_SSE_SIGNING_SECRET")

    gateway_jwt_secret: str = Field(default="", alias="GATEWAY_JWT_SECRET")
    gateway_jwt_audience: str = Field(default="api-gateway", alias="GATEWAY_JWT_AUDIENCE")
    gateway_jwt_issuer: str = Field(
        default="bitget-btc-ai-gateway", alias="GATEWAY_JWT_ISSUER"
    )
    gateway_super_admin_subject: str = Field(
        default="",
        alias="GATEWAY_SUPER_ADMIN_SUBJECT",
        description=(
            "Exakter JWT-Claim `sub` des alleinigen Super-Admins (Philipp Crljic). "
            "Wenn gesetzt: `portal_roles`/`platform_role` mit super_admin nur fuer dieses sub "
            "wirksam; andere Subjects verlieren das Portal-Flag (kein UI-Leak). "
            "Leer = super_admin-Portal-Claim wird fuer keine JWT-Subject akzeptiert."
        ),
    )
    gateway_internal_api_key: str = Field(default="", alias="GATEWAY_INTERNAL_API_KEY")
    gateway_enforce_sensitive_auth: bool | None = Field(
        default=None,
        alias="GATEWAY_ENFORCE_SENSITIVE_AUTH",
    )
    gateway_allow_legacy_admin_token: bool = Field(
        default=False,
        alias="GATEWAY_ALLOW_LEGACY_ADMIN_TOKEN",
        description="Explizit true nur lokal/Dev; Shadow/Prod mit sensiblem Auth: immer aus.",
    )
    gateway_rl_public_per_minute: int = Field(
        default=240,
        alias="GATEWAY_RL_PUBLIC_PER_MINUTE",
    )
    gateway_rl_sensitive_per_minute: int = Field(
        default=90,
        alias="GATEWAY_RL_SENSITIVE_PER_MINUTE",
    )
    gateway_rl_admin_mutate_per_minute: int = Field(
        default=24,
        alias="GATEWAY_RL_ADMIN_MUTATE_PER_MINUTE",
    )
    gateway_rl_safety_mutate_per_minute: int = Field(
        default=12,
        alias="GATEWAY_RL_SAFETY_MUTATE_PER_MINUTE",
        description="Strikteres Limit fuer POST /v1/live-broker/safety/* und operator-release.",
    )
    gateway_rl_safety_burst_per_10s: int = Field(
        default=4,
        alias="GATEWAY_RL_SAFETY_BURST_PER_10S",
        description="Zusaetzliche Burst-Kappe (Mutationen / 10s pro Client-Bucket).",
    )
    gateway_internal_key_roles: str = Field(
        default="",
        alias="GATEWAY_INTERNAL_KEY_ROLES",
        description=(
            "Leer = volles Rollenset fuer X-Gateway-Internal-Key (inkl. operator:mutate, emergency:mutate). "
            "Sonst komma-separierte Rollen."
        ),
    )
    gateway_manual_action_secret: str = Field(
        default="",
        alias="GATEWAY_MANUAL_ACTION_SECRET",
        description="Optional: separates HMAC-Secret; sonst Fallback GATEWAY_JWT_SECRET.",
    )
    gateway_manual_action_ttl_sec: int = Field(
        default=120,
        ge=30,
        le=900,
        alias="GATEWAY_MANUAL_ACTION_TTL_SEC",
    )
    gateway_manual_action_required: bool | None = Field(
        default=None,
        alias="GATEWAY_MANUAL_ACTION_REQUIRED",
        description="None = bei erzwungenem sensiblen Auth true, sonst false.",
    )
    gateway_manual_action_redis_replay_guard: bool = Field(
        default=True,
        alias="GATEWAY_MANUAL_ACTION_REDIS_REPLAY_GUARD",
    )
    gateway_allow_anonymous_safety_mutations: bool = Field(
        default=False,
        alias="GATEWAY_ALLOW_ANONYMOUS_SAFETY_MUTATIONS",
        description="Nur non-production: Mutation ohne JWT/Key (nicht empfohlen).",
    )
    # TLS wird am Gateway terminiert (oder Proxy davor): HSTS-Header setzen
    gateway_send_hsts: bool = Field(default=False, alias="GATEWAY_SEND_HSTS")
    # SSE-Cookie: secure-Flag unabhaengig von PRODUCTION (z. B. TLS nur am Edge)
    gateway_sse_cookie_secure: bool | None = Field(
        default=None,
        alias="GATEWAY_SSE_COOKIE_SECURE",
    )
    gateway_sse_cookie_samesite: str = Field(
        default="lax",
        alias="GATEWAY_SSE_COOKIE_SAMESITE",
    )
    # JSON-API: restriktiv; leer = kein CSP-Header
    gateway_content_security_policy: str = Field(
        default="default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
        alias="GATEWAY_CONTENT_SECURITY_POLICY",
    )

    commercial_enabled: bool = Field(default=False, alias="COMMERCIAL_ENABLED")
    commercial_default_tenant_id: str = Field(
        default="default",
        alias="COMMERCIAL_DEFAULT_TENANT_ID",
    )
    commercial_entitlement_enforce: bool = Field(
        default=True,
        alias="COMMERCIAL_ENTITLEMENT_ENFORCE",
        description=(
            "402 Payment Required wenn Plan-Entitlement (623) / Prepaid-Kriterium "
            "fuer Premium-KI (z. B. AI_DEEP_ANALYSIS) nicht erfuellt."
        ),
    )
    live_broker_gateway_live_policy_enforce: bool = Field(
        default=True,
        alias="LIVE_BROKER_GATEWAY_LIVE_POLICY_ENFORCE",
        description=(
            "Vor live-broker Mutationen (Gateway): Tenant benoetigt abgeschlossenen "
            "commercial_contract_workflow + Live-Gates in DB (Fail-Fast 403)."
        ),
    )
    live_broker_gateway_live_policy_cache_ttl_sec: int = Field(
        default=60,
        ge=0,
        le=3600,
        alias="LIVE_BROKER_GATEWAY_LIVE_POLICY_CACHE_TTL_SEC",
        description=(
            "Redis-Cache fuer gueltigen Live-Status (0 = kein Cache, nur DB)."
        ),
    )
    commercial_meter_secret: str = Field(
        default="",
        alias="COMMERCIAL_METER_SECRET",
        description="POST /v1/commerce/internal/usage: Header X-Commercial-Meter-Secret (Dienst-zu-Dienst).",
    )

    billing_daily_api_fee_usd: str = Field(
        default="50",
        alias="BILLING_DAILY_API_FEE_USD",
        description="Taegliche API-Flatrate vom Prepaid (List-USD).",
    )
    billing_min_balance_new_trade_usd: str = Field(
        default="50",
        alias="BILLING_MIN_BALANCE_NEW_TRADE_USD",
        description="Mindest-Prepaid fuer neue Trades (Aktivierung).",
    )
    billing_warning_balance_usd: str = Field(
        default="100",
        alias="BILLING_WARNING_BALANCE_USD",
        description="Prepaid <= dieser Betrag: Vorwarnstufe (nach Abzug).",
    )
    billing_critical_balance_usd: str = Field(
        default="50",
        alias="BILLING_CRITICAL_BALANCE_USD",
        description="Prepaid <= dieser Betrag: kritisch niedrig.",
    )
    subscription_billing_eur_usd_rate: str = Field(
        default="1.0",
        alias="SUBSCRIPTION_BILLING_EUR_USD_RATE",
        description=(
            "Abo-Tagesabzuege: Umrechnung 1 EUR -> List-USD fuer app.customer_wallet "
            "(Vereinfachung/Referenz, PSP-FX getrennt)."
        ),
    )

    profit_fee_module_enabled: bool = Field(
        default=True,
        alias="PROFIT_FEE_MODULE_ENABLED",
        description="Gewinnbeteiligung / High-Water-Mark (Prompt 15, Migration 611).",
    )
    profit_fee_default_rate_basis_points: int = Field(
        default=1000,
        alias="PROFIT_FEE_RATE_BASIS_POINTS",
        ge=0,
        le=10000,
        description="1000 = 10 % auf inkrementelle Gewinnbasis (siehe shared_py.profit_fee_engine).",
    )
    profit_fee_settlement_enabled: bool = Field(
        default=True,
        alias="PROFIT_FEE_SETTLEMENT_ENABLED",
        description="Treasury/Settlement-Workflow (Prompt 16, Migration 612).",
    )
    profit_fee_settlement_treasury_secondary_approval: bool = Field(
        default=False,
        alias="PROFIT_FEE_SETTLEMENT_TREASURY_SECONDARY_APPROVAL",
        description="Zweite Admin-Freigabe vor manueller Auszahlung.",
    )

    telegram_bot_username: str = Field(
        default="",
        alias="TELEGRAM_BOT_USERNAME",
        description="Bot-Handle ohne @ fuer Kunden-Deep-Link t.me/<username>.",
    )
    commercial_telegram_required_for_console: bool = Field(
        default=False,
        alias="COMMERCIAL_TELEGRAM_REQUIRED_FOR_CONSOLE",
        description="Dashboard-Console: ohne Verknuepfung nur eingeschraenkte Bereiche.",
    )
    execution_live_strict_prerequisites: bool = Field(
        default=False,
        alias="EXECUTION_LIVE_STRICT_PREREQUISITES",
        description=(
            "Private Prod + Live-Handel: Owner-/Operator-Release, Exchange-Health, "
            "Risk-Hard-Gates und Kill-Switch erzwingen. Keine Billing-/Customer-Pflicht."
        ),
    )

    payment_checkout_enabled: bool = Field(
        default=False,
        alias="PAYMENT_CHECKOUT_ENABLED",
        description="Einzahlungs-Checkout (siehe docs/payment_architecture.md).",
    )
    payment_mode: str = Field(
        default="sandbox",
        alias="PAYMENT_MODE",
        description="sandbox oder live (Stripe-Keys, Webhook-Pflicht).",
    )
    payment_stripe_enabled: bool = Field(default=False, alias="PAYMENT_STRIPE_ENABLED")
    payment_stripe_secret_key: str = Field(default="", alias="PAYMENT_STRIPE_SECRET_KEY")
    payment_stripe_webhook_secret: str = Field(
        default="",
        alias="PAYMENT_STRIPE_WEBHOOK_SECRET",
    )
    payment_stripe_success_url: str = Field(
        default="",
        alias="PAYMENT_STRIPE_SUCCESS_URL",
        description="Redirect nach erfolgreicher Stripe Checkout Session.",
    )
    payment_stripe_cancel_url: str = Field(
        default="",
        alias="PAYMENT_STRIPE_CANCEL_URL",
    )
    payment_stripe_method_types: str = Field(
        default="card",
        alias="PAYMENT_STRIPE_METHOD_TYPES",
        description="Komma-separiert: card, link (PayPal ueber Stripe wo verfuegbar), alipay, wechat_pay, …",
    )
    payment_mock_enabled: bool = Field(
        default=True,
        alias="PAYMENT_MOCK_ENABLED",
        description="Sandbox-Provider ohne externes PSP (lokal testbar).",
    )
    payment_mock_webhook_secret: str = Field(
        default="",
        alias="PAYMENT_MOCK_WEBHOOK_SECRET",
        description="Header X-Payment-Mock-Secret fuer POST .../webhooks/mock.",
    )

    payment_wise_webhook_enabled: bool = Field(
        default=False,
        alias="PAYMENT_WISE_WEBHOOK_ENABLED",
        description="POST /v1/commerce/payments/webhooks/wise (HMAC siehe docs).",
    )
    payment_wise_webhook_secret: str = Field(
        default="",
        alias="PAYMENT_WISE_WEBHOOK_SECRET",
        description="Shared secret fuer HMAC-SHA256(hex) ueber Rohbody (Wise: mit Live-Doku abgleichen).",
    )
    payment_paypal_stub_webhook_enabled: bool = Field(
        default=False,
        alias="PAYMENT_PAYPAL_STUB_WEBHOOK_ENABLED",
        description="Stub-Webhook bis PayPal Commerce/Subscriptions produktiv angebunden sind.",
    )
    payment_paypal_stub_webhook_secret: str = Field(
        default="",
        alias="PAYMENT_PAYPAL_STUB_WEBHOOK_SECRET",
        description="Header X-Paypal-Stub-Secret (konstant), nur non-production oder explizit aktiviert.",
    )

    commercial_contract_webhook_secret: str = Field(
        default="",
        alias="COMMERCIAL_CONTRACT_WEBHOOK_SECRET",
        description=(
            "HMAC-SHA256 (hex) ueber sortiertes JSON-Webhook-Body; "
            "Header X-Commercial-Contract-Signature. Leer = nur fuer Dev ohne Webhook."
        ),
    )
    commercial_contract_esign_provider: str = Field(
        default="mock",
        alias="COMMERCIAL_CONTRACT_ESIGN_PROVIDER",
        description="Adapter-Name (aktuell nur mock).",
    )
    commercial_contract_allow_mock_customer_complete: bool = Field(
        default=False,
        alias="COMMERCIAL_CONTRACT_ALLOW_MOCK_CUSTOMER_COMPLETE",
        description="Nur non-production: POST .../contracts/{id}/mock-complete-sign ohne Webhook.",
    )
    commercial_contract_enforce_signing_workflow: bool = Field(
        default=False,
        alias="COMMERCIAL_CONTRACT_ENFORCE_SIGNING_WORKFLOW",
        description="Wenn true: POST .../lifecycle/ack-contract-signed ist gesperrt (nutze E-Sign-Flow).",
    )

    @field_validator(
        "gateway_enforce_sensitive_auth",
        "gateway_manual_action_required",
        "gateway_sse_cookie_secure",
        mode="before",
    )
    @classmethod
    def _optional_bool_empty_env_to_none(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("gateway_send_hsts", mode="before")
    @classmethod
    def _bool_empty_env_to_false(cls, value: object) -> object:
        if value is None:
            return False
        if isinstance(value, str) and not value.strip():
            return False
        return value

    @field_validator("gateway_content_security_policy", mode="before")
    @classmethod
    def _strip_gateway_csp(cls, value: object) -> object:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator(
        "dashboard_default_symbol",
        "next_public_default_symbol",
        "dashboard_default_market_family",
        "next_public_default_market_family",
        "next_public_default_product",
        "dashboard_watchlist_symbols",
        "next_public_watchlist_symbols",
        mode="before",
    )
    @classmethod
    def _normalize_dashboard_fields(cls, value: object) -> object:
        if value is None:
            return ""
        return str(value).strip()

    def sensitive_auth_enforced(self) -> bool:
        if self.gateway_enforce_sensitive_auth is not None:
            return bool(self.gateway_enforce_sensitive_auth)
        return bool(self.production)

    def legacy_admin_token_allowed(self) -> bool:
        if self.sensitive_auth_enforced():
            return False
        return bool(self.gateway_allow_legacy_admin_token)

    def gateway_auth_credentials_configured(self) -> bool:
        return bool(self.gateway_jwt_secret.strip()) or bool(
            self.gateway_internal_api_key.strip()
        )

    def dashboard_watchlist_symbols_list(self) -> list[str]:
        explicit = [item.strip().upper() for item in self.dashboard_watchlist_symbols.split(",") if item.strip()]
        if explicit:
            return explicit
        fallback = [item.strip().upper() for item in self.next_public_watchlist_symbols.split(",") if item.strip()]
        if fallback:
            return fallback
        return self.bitget_watchlist_symbols_list()

    @model_validator(mode="after")
    def _validate_gateway_security(self) -> Self:
        if self.sensitive_auth_enforced() and not (
            self.gateway_auth_credentials_configured()
        ):
            raise ValueError(
                "Bei aktivem sensiblen Gateway-Auth (PRODUCTION oder "
                "GATEWAY_ENFORCE_SENSITIVE_AUTH=true) muessen "
                "GATEWAY_JWT_SECRET und/oder GATEWAY_INTERNAL_API_KEY gesetzt sein."
            )
        if self.sensitive_auth_enforced():
            jwt_s = self.gateway_jwt_secret.strip()
            if jwt_s and len(jwt_s) < MIN_PRODUCTION_SECRET_LEN:
                raise ValueError(
                    "GATEWAY_JWT_SECRET muss mindestens "
                    f"{MIN_PRODUCTION_SECRET_LEN} Zeichen haben"
                )
            ik = self.gateway_internal_api_key.strip()
            if ik and len(ik) < MIN_PRODUCTION_SECRET_LEN:
                raise ValueError(
                    "GATEWAY_INTERNAL_API_KEY muss mindestens "
                    f"{MIN_PRODUCTION_SECRET_LEN} Zeichen haben"
                )
            if self.manual_action_required():
                ma = self.gateway_manual_action_secret.strip()
                if not ma and not jwt_s:
                    raise ValueError(
                        "GATEWAY_MANUAL_ACTION_SECRET oder GATEWAY_JWT_SECRET erforderlich, "
                        "wenn manuelle Aktions-Tokens aktiv sind (Production/sensibles Auth)."
                    )
                if ma and len(ma) < MIN_PRODUCTION_SECRET_LEN:
                    raise ValueError(
                        "GATEWAY_MANUAL_ACTION_SECRET muss mindestens "
                        f"{MIN_PRODUCTION_SECRET_LEN} Zeichen haben"
                    )
        pub = self.gateway_rl_public_per_minute
        if pub < 1 or pub > 10_000:
            raise ValueError("GATEWAY_RL_PUBLIC_PER_MINUTE muss 1..10000 sein")
        sens = self.gateway_rl_sensitive_per_minute
        if sens < 1 or sens > 5000:
            raise ValueError("GATEWAY_RL_SENSITIVE_PER_MINUTE muss 1..5000 sein")
        adm = self.gateway_rl_admin_mutate_per_minute
        if adm < 1 or adm > 500:
            raise ValueError("GATEWAY_RL_ADMIN_MUTATE_PER_MINUTE muss 1..500 sein")
        sm = self.gateway_rl_safety_mutate_per_minute
        if sm < 1 or sm > 500:
            raise ValueError("GATEWAY_RL_SAFETY_MUTATE_PER_MINUTE muss 1..500 sein")
        sb = self.gateway_rl_safety_burst_per_10s
        if sb < 1 or sb > 100:
            raise ValueError("GATEWAY_RL_SAFETY_BURST_PER_10S muss 1..100 sein")
        ttl = self.gateway_sse_cookie_ttl_sec
        if ttl < 60 or ttl > 86_400:
            raise ValueError("GATEWAY_SSE_COOKIE_TTL_SEC muss 60..86400 sein")
        ss = self.gateway_sse_cookie_samesite.strip().lower()
        if ss not in ("lax", "strict", "none"):
            raise ValueError(
                "GATEWAY_SSE_COOKIE_SAMESITE muss lax, strict oder none sein"
            )
        object.__setattr__(self, "gateway_sse_cookie_samesite", ss)
        if ss == "none" and not self._sse_cookie_secure_resolved():
            raise ValueError(
                "GATEWAY_SSE_COOKIE_SAMESITE=none erfordert "
                "GATEWAY_SSE_COOKIE_SECURE=true oder PRODUCTION=true"
            )
        watchlist = self.dashboard_watchlist_symbols_list()
        if not self.dashboard_default_symbol:
            object.__setattr__(
                self,
                "dashboard_default_symbol",
                watchlist[0] if watchlist else "",
            )
        if not self.next_public_default_symbol:
            object.__setattr__(
                self,
                "next_public_default_symbol",
                self.dashboard_default_symbol,
            )
        default_family = self.dashboard_default_market_family.strip().lower()
        if not default_family:
            families = self.bitget_universe_market_families_list()
            object.__setattr__(
                self,
                "dashboard_default_market_family",
                families[0] if families else "",
            )
        else:
            object.__setattr__(self, "dashboard_default_market_family", default_family)
        if not self.next_public_default_market_family:
            object.__setattr__(
                self,
                "next_public_default_market_family",
                self.dashboard_default_market_family,
            )
        else:
            object.__setattr__(
                self,
                "next_public_default_market_family",
                self.next_public_default_market_family.strip().lower(),
            )
        families = self.bitget_universe_market_families_list()
        if self.dashboard_default_market_family and self.dashboard_default_market_family not in families:
            raise ValueError(
                "DASHBOARD_DEFAULT_MARKET_FAMILY muss Teil von BITGET_UNIVERSE_MARKET_FAMILIES sein"
            )
        if (
            self.next_public_default_market_family
            and self.next_public_default_market_family not in families
        ):
            raise ValueError(
                "NEXT_PUBLIC_DEFAULT_MARKET_FAMILY muss Teil von BITGET_UNIVERSE_MARKET_FAMILIES sein"
            )
        if not self.next_public_default_product:
            object.__setattr__(
                self,
                "next_public_default_product",
                (
                    self.bitget_futures_default_product_type
                    if self.dashboard_default_market_family == "futures"
                    else ""
                ),
            )
        if self.commercial_enabled and self.production:
            cms = self.commercial_meter_secret.strip()
            if cms and len(cms) < MIN_PRODUCTION_SECRET_LEN:
                raise ValueError(
                    "COMMERCIAL_METER_SECRET muss mindestens "
                    f"{MIN_PRODUCTION_SECRET_LEN} Zeichen haben, wenn gesetzt (Production)."
                )

        if self.commercial_contract_allow_mock_customer_complete and self.production:
            raise ValueError(
                "COMMERCIAL_CONTRACT_ALLOW_MOCK_CUSTOMER_COMPLETE ist in Production unzulaessig"
            )
        if self.commercial_contract_enforce_signing_workflow and self.production:
            w = self.commercial_contract_webhook_secret.strip()
            if not w or len(w) < MIN_PRODUCTION_SECRET_LEN:
                raise ValueError(
                    "COMMERCIAL_CONTRACT_ENFORCE_SIGNING_WORKFLOW in Production erfordert "
                    f"COMMERCIAL_CONTRACT_WEBHOOK_SECRET (min {MIN_PRODUCTION_SECRET_LEN} Zeichen)"
                )

        if self.payment_wise_webhook_enabled and self.production:
            ws = self.payment_wise_webhook_secret.strip()
            if not ws or len(ws) < MIN_PRODUCTION_SECRET_LEN:
                raise ValueError(
                    "PAYMENT_WISE_WEBHOOK_ENABLED in Production erfordert "
                    f"PAYMENT_WISE_WEBHOOK_SECRET (min {MIN_PRODUCTION_SECRET_LEN} Zeichen)"
                )
        if self.payment_paypal_stub_webhook_enabled and self.production:
            ps = self.payment_paypal_stub_webhook_secret.strip()
            if not ps or len(ps) < MIN_PRODUCTION_SECRET_LEN:
                raise ValueError(
                    "PAYMENT_PAYPAL_STUB_WEBHOOK_ENABLED in Production erfordert "
                    f"PAYMENT_PAYPAL_STUB_WEBHOOK_SECRET (min {MIN_PRODUCTION_SECRET_LEN} Zeichen)"
                )

        if self.payment_checkout_enabled and self.production:
            if self.payment_mode.strip().lower() == "live" and self.payment_stripe_enabled:
                sk = self.payment_stripe_secret_key.strip()
                wh = self.payment_stripe_webhook_secret.strip()
                if not sk or len(sk) < MIN_PRODUCTION_SECRET_LEN:
                    raise ValueError(
                        "PAYMENT_STRIPE_SECRET_KEY erforderlich (Production, live, Stripe)."
                    )
                if not wh or len(wh) < MIN_PRODUCTION_SECRET_LEN:
                    raise ValueError(
                        "PAYMENT_STRIPE_WEBHOOK_SECRET erforderlich (Production, live, Stripe)."
                    )
            if self.payment_mock_enabled:
                ms = self.payment_mock_webhook_secret.strip()
                if not ms or len(ms) < MIN_PRODUCTION_SECRET_LEN:
                    raise ValueError(
                        "PAYMENT_MOCK_WEBHOOK_SECRET erforderlich wenn PAYMENT_MOCK_ENABLED "
                        f"(Production, min {MIN_PRODUCTION_SECRET_LEN} Zeichen)."
                    )

        if self.production:
            ab = self.app_base_url.strip().lower()
            if ab.startswith("https://") and not self.gateway_send_hsts:
                raise ValueError(
                    "PRODUCTION=true mit APP_BASE_URL=https:// erfordert "
                    "GATEWAY_SEND_HSTS=true (HSTS am API-Edge nach TLS-Terminierung)."
                )
            if ab.startswith("https://") and self.gateway_sse_cookie_secure is False:
                raise ValueError(
                    "Bei APP_BASE_URL=https:// ist GATEWAY_SSE_COOKIE_SECURE=false "
                    "unzulaessig"
                )

        live_handoff = (
            self.production
            and self.execution_live_strict_prerequisites
            and self.execution_mode == "live"
            and self.live_trade_enable
            and self.live_broker_enabled
        )
        if live_handoff:
            if not self.live_require_operator_release_for_live_open:
                raise ValueError(
                    "EXECUTION_LIVE_STRICT_PREREQUISITES: Production-Live-Handel "
                    "verlangt LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN=true "
                    "(Owner-/Operator-Freigabe durch Philipp fuer Live-Opens)"
                )
            if not self.live_require_exchange_health:
                raise ValueError(
                    "EXECUTION_LIVE_STRICT_PREREQUISITES: Production-Live-Handel "
                    "verlangt LIVE_REQUIRE_EXCHANGE_HEALTH=true"
                )
            if not self.risk_hard_gating_enabled:
                raise ValueError(
                    "EXECUTION_LIVE_STRICT_PREREQUISITES: Production-Live-Handel "
                    "verlangt RISK_HARD_GATING_ENABLED=true"
                )
            if not self.live_kill_switch_enabled:
                raise ValueError(
                    "EXECUTION_LIVE_STRICT_PREREQUISITES: Production-Live-Handel "
                    "verlangt LIVE_KILL_SWITCH_ENABLED=true"
                )

        if self.use_docker_datastore_dsn:
            for field, env_name in _GATEWAY_HEALTH_PEER_FIELDS:
                val = str(getattr(self, field, "") or "").strip()
                if not val:
                    continue
                host = urlparse(val).hostname or ""
                if _hostname_is_loopback(host):
                    raise ValueError(
                        "BITGET_USE_DOCKER_DATASTORE_DSN=true: "
                        f"{env_name} zeigt auf Loopback ({host!r}). "
                        "Im Container bezeichnet das den eigenen Container, nicht den Worker. "
                        "Nutze Docker-Dienstnamen wie in docker-compose.yml, z. B. "
                        "http://market-stream:8010/ready."
                    )
            llm_direct = str(self.llm_orchestrator_base_url or "").strip()
            if llm_direct:
                host = urlparse(llm_direct).hostname or ""
                if _hostname_is_loopback(host):
                    raise ValueError(
                        "BITGET_USE_DOCKER_DATASTORE_DSN=true: LLM_ORCH_BASE_URL zeigt auf Loopback "
                        f"({host!r}). Setze z. B. http://llm-orchestrator:8070."
                    )
            lb_direct = str(self.live_broker_base_url or "").strip()
            if lb_direct:
                host = urlparse(lb_direct).hostname or ""
                if _hostname_is_loopback(host):
                    raise ValueError(
                        "BITGET_USE_DOCKER_DATASTORE_DSN=true: LIVE_BROKER_BASE_URL zeigt auf Loopback "
                        f"({host!r}). Setze z. B. http://live-broker:8120."
                    )
        return self

    def manual_action_required(self) -> bool:
        if self.gateway_manual_action_required is not None:
            return bool(self.gateway_manual_action_required)
        return self.sensitive_auth_enforced()

    def allow_anonymous_safety_mutations_effective(self) -> bool:
        if self.production:
            return False
        if self.sensitive_auth_enforced():
            return False
        return bool(self.gateway_allow_anonymous_safety_mutations)

    def _sse_cookie_secure_resolved(self) -> bool:
        if self.gateway_sse_cookie_secure is not None:
            return bool(self.gateway_sse_cookie_secure)
        return bool(self.production)

    def sse_cookie_secure_flag(self) -> bool:
        """HttpOnly-SSE-Cookie: Secure-Flag (TLS am Client oder explizit gesetzt)."""
        return self._sse_cookie_secure_resolved()

    def payment_environment(self) -> str:
        return "live" if self.payment_mode.strip().lower() == "live" else "sandbox"

    def commercial_contract_stub_ack_disabled(self) -> bool:
        """True: Kunden-Stub ack-contract-signed soll nicht genutzt werden (E-Sign/Webhook)."""
        if self.commercial_contract_enforce_signing_workflow:
            return True
        w = self.commercial_contract_webhook_secret.strip()
        if self.production and w and len(w) >= MIN_PRODUCTION_SECRET_LEN:
            return True
        return False

    def llm_orchestrator_http_base(self) -> str:
        """
        Basis-URL fuer Gateway->Orchestrator (ohne trailing slash).

        Prioritaet: `LLM_ORCH_BASE_URL`, sonst `scheme://netloc` aus `HEALTH_URL_LLM_ORCHESTRATOR`
        (typisch `http://llm-orchestrator:8070/ready` im Compose).
        Auth: `INTERNAL_API_KEY` als Header `X-Internal-Service-Key` — identisch zum Wert im Orchestrator.
        """
        direct = str(self.llm_orchestrator_base_url or "").strip().rstrip("/")
        if direct:
            return direct
        return http_base_from_health_or_ready_url(str(self.health_url_llm_orchestrator or ""))

    def live_broker_http_base(self) -> str:
        """
        Basis-URL fuer Gateway->live-broker Forward (ohne trailing slash).

        Prioritaet: `LIVE_BROKER_BASE_URL`, sonst aus `HEALTH_URL_LIVE_BROKER` abgeleitet
        (typisch `http://live-broker:8120/ready` im Compose).
        """
        direct = str(self.live_broker_base_url or "").strip().rstrip("/")
        if direct:
            return direct
        return http_base_from_health_or_ready_url(str(self.health_url_live_broker or ""))


@lru_cache
def get_gateway_settings() -> GatewaySettings:
    return GatewaySettings()
