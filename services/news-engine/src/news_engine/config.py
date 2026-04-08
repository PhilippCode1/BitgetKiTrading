from __future__ import annotations

from typing import ClassVar

from pydantic import Field, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from config.settings import BaseServiceSettings, _is_blank_or_placeholder

_DEFAULT_ALLOWED = (
    "cryptopanic.com",
    "newsapi.org",
    "www.coindesk.com",
    "coindesk.com",
    "api.gdeltproject.org",
    "api.gdeltproject.org.",
)


class NewsEngineSettings(BaseServiceSettings):
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

    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")
    news_engine_port: int = Field(default=8060, alias="NEWS_ENGINE_PORT")
    news_poll_interval_sec: int = Field(default=30, alias="NEWS_POLL_INTERVAL_SEC")
    cryptopanic_api_key: str | None = Field(default=None, alias="CRYPTOPANIC_API_KEY")
    cryptopanic_api_url: str = Field(
        default="https://cryptopanic.com/api/v1/posts/",
        alias="CRYPTOPANIC_API_URL",
    )
    newsapi_api_key: str | None = Field(default=None, alias="NEWSAPI_API_KEY")
    newsapi_top_country: str = Field(
        default="us",
        alias="NEWSAPI_TOP_COUNTRY",
    )
    coindesk_rss_url: str = Field(
        default="https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml",
        alias="COINDESK_RSS_URL",
    )
    gdelt_doc_api_base: str = Field(
        default="https://api.gdeltproject.org/api/v2/doc/doc",
        alias="GDELT_DOC_API_BASE",
    )

    news_keywords: str = Field(
        default="bitcoin,btc,etf,fed,sec,regulation",
        alias="NEWS_KEYWORDS",
    )
    news_http_allowed_hosts: str = Field(
        default=",".join(_DEFAULT_ALLOWED),
        alias="NEWS_HTTP_ALLOWED_HOSTS",
    )

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    eventbus_dedupe_ttl_sec: int = Field(default=86400, alias="EVENTBUS_DEDUPE_TTL_SEC")

    news_scoring_version: str = Field(default="1.0", alias="NEWS_SCORING_VERSION")
    news_pipeline_enabled: bool = Field(
        default=True,
        alias="NEWS_PIPELINE_ENABLED",
        description="false: Ingest-Worker läuft, holt aber keine externen Feeds (Kern bleibt erreichbar).",
    )
    news_stale_warn_after_ms: int = Field(
        default=900_000,
        alias="NEWS_STALE_WARN_AFTER_MS",
        description="Mindestalter letzter Ingestion (ms) bis core_pipeline als stale gilt; zusätzlich 3× Poll-Intervall.",
    )
    news_llm_enabled: bool = Field(default=False, alias="NEWS_LLM_ENABLED")
    news_llm_provider_pref: str | None = Field(default=None, alias="NEWS_LLM_PROVIDER_PREF")
    llm_orch_base_url: str = Field(default="http://localhost:8070", alias="LLM_ORCH_BASE_URL")
    news_llm_probe_timeout_sec: float = Field(
        default=2.5,
        alias="NEWS_LLM_PROBE_TIMEOUT_SEC",
        description="Kurzer HTTP-Check Orchestrator /health — unabhängig vom langen news_summary-Timeout.",
    )
    news_score_max_llm_delta: int = Field(default=15, alias="NEWS_SCORE_MAX_LLM_DELTA")
    news_score_publish_events: bool = Field(default=True, alias="NEWS_SCORE_PUBLISH_EVENTS")
    news_max_ingest_item_age_ms: int = Field(
        default=604_800_000,
        alias="NEWS_MAX_INGEST_ITEM_AGE_MS",
        description="Items aelter als dieses Fenster (ms) werden nicht ingestiert.",
    )
    news_max_future_skew_ms: int = Field(
        default=300_000,
        alias="NEWS_MAX_FUTURE_SKEW_MS",
        description="Published-Timestamp > now+skew gilt als ungueltig (Feed-Fehler).",
    )

    @field_validator("news_poll_interval_sec")
    @classmethod
    def _poll_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("NEWS_POLL_INTERVAL_SEC muss >= 1 sein")
        return v

    @field_validator("news_engine_port")
    @classmethod
    def _port(cls, v: int) -> int:
        if not 1 <= v <= 65535:
            raise ValueError("NEWS_ENGINE_PORT ungueltig")
        return v

    @field_validator("news_score_max_llm_delta")
    @classmethod
    def _llm_delta(cls, v: int) -> int:
        if v < 0 or v > 50:
            raise ValueError("NEWS_SCORE_MAX_LLM_DELTA ausserhalb 0..50")
        return v

    @field_validator("news_max_ingest_item_age_ms", "news_max_future_skew_ms", "news_stale_warn_after_ms")
    @classmethod
    def _positive_news_windows(cls, v: int) -> int:
        if v < 1:
            raise ValueError("NEWS_MAX_*_MS muss >= 1 sein")
        return v

    @field_validator("news_llm_probe_timeout_sec")
    @classmethod
    def _probe_timeout(cls, v: float) -> float:
        if v < 0.5 or v > 30.0:
            raise ValueError("NEWS_LLM_PROBE_TIMEOUT_SEC ausserhalb 0.5..30")
        return v

    def keyword_list(self) -> list[str]:
        from news_engine.filters import parse_keyword_list

        return parse_keyword_list(self.news_keywords)

    def allowed_hosts_set(self) -> set[str]:
        hosts = {h.strip().lower() for h in self.news_http_allowed_hosts.split(",") if h.strip()}
        return hosts

    @model_validator(mode="after")
    def _validate_llm_requirements(self) -> "NewsEngineSettings":
        if self.news_llm_enabled and _is_blank_or_placeholder(self.llm_orch_base_url):
            raise ValueError(
                "LLM_ORCH_BASE_URL muss gesetzt sein, wenn NEWS_LLM_ENABLED=true"
            )
        return self
