from __future__ import annotations

from typing import ClassVar

from pydantic import Field, field_validator
from pydantic_settings import SettingsConfigDict

from config.settings import BaseServiceSettings
from shared_py.eventbus import STREAM_STRUCTURE_UPDATED


class DrawingEngineSettings(BaseServiceSettings):
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
    drawing_engine_port: int = Field(default=8040, alias="DRAWING_ENGINE_PORT")
    drawing_stream: str = Field(default=STREAM_STRUCTURE_UPDATED, alias="DRAWING_STREAM")
    drawing_group: str = Field(default="drawing-engine", alias="DRAWING_GROUP")
    drawing_consumer: str = Field(default="de-1", alias="DRAWING_CONSUMER")

    zone_cluster_bps: float = Field(default=25.0, alias="ZONE_CLUSTER_BPS")
    zone_pad_bps: float = Field(default=10.0, alias="ZONE_PAD_BPS")
    stop_pad_bps: float = Field(default=15.0, alias="STOP_PAD_BPS")
    liquidity_topk: int = Field(default=5, alias="LIQUIDITY_TOPK")
    liquidity_cluster_bps: float = Field(default=12.0, alias="LIQUIDITY_CLUSTER_BPS")
    drawing_max_orderbook_age_ms: int = Field(
        default=300_000,
        alias="DRAWING_MAX_ORDERBOOK_AGE_MS",
    )

    eventbus_default_block_ms: int = Field(default=2000, alias="EVENTBUS_DEFAULT_BLOCK_MS")
    eventbus_default_count: int = Field(default=50, alias="EVENTBUS_DEFAULT_COUNT")
    eventbus_dedupe_ttl_sec: int = Field(default=86400, alias="EVENTBUS_DEDUPE_TTL_SEC")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("drawing_engine_port")
    @classmethod
    def _validate_port(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("DRAWING_ENGINE_PORT muss zwischen 1 und 65535 liegen")
        return value

    @field_validator("drawing_max_orderbook_age_ms")
    @classmethod
    def _validate_ob_age_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("DRAWING_MAX_ORDERBOOK_AGE_MS muss > 0 sein")
        return value

    @field_validator(
        "eventbus_default_block_ms",
        "eventbus_default_count",
        "liquidity_topk",
    )
    @classmethod
    def _validate_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Werte muessen > 0 sein")
        return value

    @field_validator(
        "zone_cluster_bps",
        "zone_pad_bps",
        "stop_pad_bps",
        "liquidity_cluster_bps",
    )
    @classmethod
    def _validate_bps_non_negative(cls, value: float) -> float:
        if value < 0:
            raise ValueError("BPS-Werte duerfen nicht negativ sein")
        return value

    @field_validator("drawing_stream")
    @classmethod
    def _validate_stream(cls, value: str) -> str:
        normalized = value.strip()
        if normalized != STREAM_STRUCTURE_UPDATED:
            raise ValueError(
                "DRAWING_STREAM muss fuer Prompt 12 exakt events:structure_updated sein"
            )
        return normalized

    @field_validator("drawing_group", "drawing_consumer", mode="before")
    @classmethod
    def _validate_names(cls, value: object) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("Drawing Worker Namen duerfen nicht leer sein")
        return normalized

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> str:
        if value is None:
            return "INFO"
        return str(value).strip().upper() or "INFO"


def normalize_timeframe(timeframe: str) -> str:
    raw = timeframe.strip()
    aliases = {"1h": "1H", "4h": "4H"}
    return aliases.get(raw, raw)
