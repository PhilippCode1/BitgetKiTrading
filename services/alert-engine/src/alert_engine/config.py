from __future__ import annotations

import logging
from functools import lru_cache
from typing import ClassVar

from pydantic import Field, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from config.settings import BaseServiceSettings, TelegramMode, _is_blank_or_placeholder

_log = logging.getLogger("alert_engine.config")


class Settings(BaseServiceSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        populate_by_name=True,
    )
    production_required_fields: ClassVar[tuple[str, ...]] = (
        BaseServiceSettings.production_required_fields
        + ("database_url", "redis_url", "telegram_bot_token")
    )
    production_required_non_local_fields: ClassVar[tuple[str, ...]] = (
        BaseServiceSettings.production_required_non_local_fields
        + ("database_url", "redis_url")
    )

    alert_engine_port: int = Field(default=8100, alias="ALERT_ENGINE_PORT")
    database_url: str = Field(default="", alias="DATABASE_URL")
    redis_url: str = Field(default="", alias="REDIS_URL")

    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_mode: TelegramMode = Field(default="getUpdates", alias="TELEGRAM_MODE")
    telegram_longpoll_timeout_sec: int = Field(default=30, alias="TELEGRAM_LONGPOLL_TIMEOUT_SEC")
    telegram_allowed_updates: str = Field(
        default="message,callback_query", alias="TELEGRAM_ALLOWED_UPDATES"
    )
    telegram_allowed_chat_ids: str = Field(default="", alias="TELEGRAM_ALLOWED_CHAT_IDS")
    telegram_send_max_per_sec: float = Field(default=1.0, alias="TELEGRAM_SEND_MAX_PER_SEC")
    telegram_send_max_per_min_per_chat: int = Field(
        default=20, alias="TELEGRAM_SEND_MAX_PER_MIN_PER_CHAT"
    )
    telegram_send_max_retries: int = Field(default=3, alias="TELEGRAM_SEND_MAX_RETRIES")
    telegram_dry_run: bool = Field(default=True, alias="TELEGRAM_DRY_RUN")
    telegram_parse_mode: str = Field(default="none", alias="TELEGRAM_PARSE_MODE")
    telegram_message_safe_len: int = Field(default=3500, alias="TELEGRAM_MESSAGE_SAFE_LEN")
    telegram_operator_thread_ttl_sec: int = Field(
        default=604800,
        alias="TELEGRAM_OPERATOR_THREAD_TTL_SEC",
        description="Redis-TTL fuer Telegram-Thread-Anker (correlation_id -> message_id)",
    )
    telegram_outbox_max_send_attempts: int = Field(
        default=8,
        alias="TELEGRAM_OUTBOX_MAX_SEND_ATTEMPTS",
        description="claim-Zaehler bevor Outbox-Eintrag endgueltig failed",
    )
    telegram_webhook_url: str = Field(default="", alias="TELEGRAM_WEBHOOK_URL")
    telegram_webhook_secret: str = Field(default="", alias="TELEGRAM_WEBHOOK_SECRET")

    alert_signal_gross_threshold: int = Field(default=80, alias="ALERT_SIGNAL_GROSS_THRESHOLD")
    alert_signal_core_threshold: int = Field(default=65, alias="ALERT_SIGNAL_CORE_THRESHOLD")
    alert_news_threshold: int = Field(default=80, alias="ALERT_NEWS_THRESHOLD")
    alert_dedupe_minutes_gross: int = Field(default=10, alias="ALERT_DEDUPE_MINUTES_GROSS")
    alert_dedupe_minutes_core: int = Field(default=10, alias="ALERT_DEDUPE_MINUTES_CORE")
    alert_dedupe_minutes_trend: int = Field(default=10, alias="ALERT_DEDUPE_MINUTES_TREND")
    alert_dedupe_minutes_news: int = Field(default=30, alias="ALERT_DEDUPE_MINUTES_NEWS")

    consumer_group: str = Field(default="alert-engine", alias="ALERT_CONSUMER_GROUP")
    consumer_name: str = Field(default="ae-1", alias="ALERT_CONSUMER_NAME")
    event_block_ms: int = Field(default=2000, alias="ALERT_EVENT_BLOCK_MS")
    event_batch: int = Field(default=50, alias="ALERT_EVENT_BATCH")

    telegram_operator_actions_enabled: bool = Field(
        default=False,
        alias="TELEGRAM_OPERATOR_ACTIONS_ENABLED",
        description=(
            "Erlaubt zweistufige Operator-Befehle gegen live-broker (release, Notfall) — "
            "keine Strategie-Mutation."
        ),
    )
    live_broker_ops_base_url: str = Field(
        default="",
        alias="ALERT_ENGINE_LIVE_BROKER_BASE_URL",
        description="Origin des live-broker, z. B. http://live-broker:8120 (ohne Pfad-Suffix).",
    )
    telegram_operator_confirm_ttl_sec: int = Field(
        default=300,
        ge=60,
        le=3600,
        alias="TELEGRAM_OPERATOR_CONFIRM_TTL_SEC",
        description="Gueltigkeit der Telegram-Bestaetigungsphase (Sekunden).",
    )
    telegram_operator_allowed_user_ids: str = Field(
        default="",
        alias="TELEGRAM_OPERATOR_ALLOWED_USER_IDS",
        description=(
            "Optional: CSV numerischer Telegram-user_id; nur diese Nutzer duerfen "
            "Operator-Befehle. Leer = keine zusaetzliche User-RBAC (nur Chat-Allowlist)."
        ),
    )
    telegram_operator_confirm_token: str = Field(
        default="",
        alias="TELEGRAM_OPERATOR_CONFIRM_TOKEN",
        description=(
            "Optional: gemeinsames Geheimnis; bei Setzen muss /release_confirm und "
            "/emerg_confirm ein drittes Argument <token> enthalten (zusammen mit Code)."
        ),
    )

    def parsed_allowed_chat_ids(self) -> set[int]:
        raw = self.telegram_allowed_chat_ids.strip()
        if not raw:
            return set()
        out: set[int] = set()
        for part in raw.split(","):
            p = part.strip()
            if not p:
                continue
            try:
                out.add(int(p))
            except ValueError:
                _log.warning(
                    "TELEGRAM_ALLOWED_CHAT_IDS: ueberspringe ungueltigen Eintrag %r",
                    p[:64],
                )
        return out

    def parsed_operator_user_ids(self) -> set[int]:
        raw = self.telegram_operator_allowed_user_ids.strip()
        if not raw:
            return set()
        out: set[int] = set()
        for part in raw.split(","):
            p = part.strip()
            if not p:
                continue
            try:
                out.add(int(p))
            except ValueError:
                _log.warning(
                    "TELEGRAM_OPERATOR_ALLOWED_USER_IDS: ueberspringe ungueltigen Eintrag %r",
                    p[:64],
                )
        return out

    @model_validator(mode="after")
    def _validate_telegram_runtime(self) -> "Settings":
        if self.telegram_mode == "webhook":
            if _is_blank_or_placeholder(self.telegram_webhook_url):
                raise ValueError(
                    "TELEGRAM_WEBHOOK_URL muss fuer TELEGRAM_MODE=webhook gesetzt sein"
                )
            if _is_blank_or_placeholder(self.telegram_webhook_secret):
                raise ValueError(
                    "TELEGRAM_WEBHOOK_SECRET muss fuer TELEGRAM_MODE=webhook gesetzt sein"
                )
        if self.production and _is_blank_or_placeholder(self.telegram_bot_token):
            raise ValueError("TELEGRAM_BOT_TOKEN fehlt fuer Produktionsstart")
        ttl = self.telegram_operator_thread_ttl_sec
        if ttl < 3600 or ttl > 2592000:
            raise ValueError("TELEGRAM_OPERATOR_THREAD_TTL_SEC muss 3600..2592000 sein")
        att = self.telegram_outbox_max_send_attempts
        if att < 2 or att > 50:
            raise ValueError("TELEGRAM_OUTBOX_MAX_SEND_ATTEMPTS muss 2..50 sein")
        return self

    @model_validator(mode="after")
    def _telegram_operator_requires_upstream(self) -> "Settings":
        if self.telegram_operator_actions_enabled:
            if _is_blank_or_placeholder(self.live_broker_ops_base_url):
                raise ValueError(
                    "ALERT_ENGINE_LIVE_BROKER_BASE_URL ist Pflicht wenn "
                    "TELEGRAM_OPERATOR_ACTIONS_ENABLED=true"
                )
            if self.production and _is_blank_or_placeholder(self.service_internal_api_key):
                raise ValueError(
                    "INTERNAL_API_KEY ist Pflicht fuer TELEGRAM_OPERATOR_ACTIONS in Production"
                )
        return self

    @field_validator("live_broker_ops_base_url", mode="after")
    @classmethod
    def _strip_live_broker_base(cls, v: str) -> str:
        return str(v or "").strip().rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
