from __future__ import annotations

from typing import ClassVar

from pydantic import Field, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from config.settings import BaseServiceSettings
from shared_py.eventbus import STREAM_CANDLE_CLOSE

KNOWN_TIMEFRAMES = ("1m", "5m", "15m", "1H", "4H")


class StructureEngineSettings(BaseServiceSettings):
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
    structure_engine_port: int = Field(default=8030, alias="STRUCTURE_ENGINE_PORT")
    structure_stream: str = Field(default=STREAM_CANDLE_CLOSE, alias="STRUCTURE_STREAM")
    structure_group: str = Field(default="structure-engine", alias="STRUCTURE_GROUP")
    structure_consumer: str = Field(default="st-1", alias="STRUCTURE_CONSUMER")
    structure_lookback_candles: int = Field(default=400, alias="STRUCTURE_LOOKBACK_CANDLES")
    structure_max_allowed_gap_bars: int = Field(default=3, alias="STRUCTURE_MAX_ALLOWED_GAP_BARS")
    structure_bos_choch_max_gap_bars: int = Field(default=2, alias="STRUCTURE_BOS_CHOCH_MAX_GAP_BARS")

    pivot_left_n_1m: int = Field(default=3, alias="PIVOT_LEFT_N_1M")
    pivot_right_n_1m: int = Field(default=3, alias="PIVOT_RIGHT_N_1M")
    pivot_left_n_5m: int = Field(default=2, alias="PIVOT_LEFT_N_5M")
    pivot_right_n_5m: int = Field(default=2, alias="PIVOT_RIGHT_N_5M")
    pivot_left_n_15m: int = Field(default=2, alias="PIVOT_LEFT_N_15M")
    pivot_right_n_15m: int = Field(default=2, alias="PIVOT_RIGHT_N_15M")
    pivot_left_n_1h: int = Field(default=1, alias="PIVOT_LEFT_N_1H")
    pivot_right_n_1h: int = Field(default=1, alias="PIVOT_RIGHT_N_1H")
    pivot_left_n_4h: int = Field(default=1, alias="PIVOT_LEFT_N_4H")
    pivot_right_n_4h: int = Field(default=1, alias="PIVOT_RIGHT_N_4H")

    compression_atrp_thresh: float = Field(default=0.0012, alias="COMPRESSION_ATRP_THRESH")
    compression_atrp_thresh_off: float = Field(
        default=0.0018, alias="COMPRESSION_ATRP_THRESH_OFF"
    )
    compression_range_thresh: float = Field(default=0.0025, alias="COMPRESSION_RANGE_THRESH")
    compression_range_thresh_off: float = Field(
        default=0.0035, alias="COMPRESSION_RANGE_THRESH_OFF"
    )

    box_window_1m: int = Field(default=20, alias="BOX_WINDOW_1M")
    box_window_5m: int = Field(default=30, alias="BOX_WINDOW_5M")
    box_window_15m: int = Field(default=30, alias="BOX_WINDOW_15M")
    box_window_1h: int = Field(default=40, alias="BOX_WINDOW_1H")
    box_window_4h: int = Field(default=40, alias="BOX_WINDOW_4H")

    box_prebreak_dist_bps: float = Field(default=8.0, alias="BOX_PREBREAK_DIST_BPS")
    box_breakout_buffer_bps: float = Field(default=3.0, alias="BOX_BREAKOUT_BUFFER_BPS")
    false_breakout_window_bars: int = Field(default=5, alias="FALSE_BREAKOUT_WINDOW_BARS")

    eventbus_default_block_ms: int = Field(default=2000, alias="EVENTBUS_DEFAULT_BLOCK_MS")
    eventbus_default_count: int = Field(default=50, alias="EVENTBUS_DEFAULT_COUNT")
    eventbus_dedupe_ttl_sec: int = Field(default=86400, alias="EVENTBUS_DEDUPE_TTL_SEC")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("structure_engine_port")
    @classmethod
    def _validate_port(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("STRUCTURE_ENGINE_PORT muss zwischen 1 und 65535 liegen")
        return value

    @field_validator(
        "structure_lookback_candles",
        "eventbus_default_block_ms",
        "eventbus_default_count",
        "false_breakout_window_bars",
    )
    @classmethod
    def _validate_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Struktur- und Eventbus-Werte muessen > 0 sein")
        return value

    @field_validator("structure_max_allowed_gap_bars", "structure_bos_choch_max_gap_bars")
    @classmethod
    def _validate_gap_bars_non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("Gap-Bar-Grenzen duerfen nicht negativ sein")
        return value

    @field_validator(
        "pivot_left_n_1m",
        "pivot_right_n_1m",
        "pivot_left_n_5m",
        "pivot_right_n_5m",
        "pivot_left_n_15m",
        "pivot_right_n_15m",
        "pivot_left_n_1h",
        "pivot_right_n_1h",
        "pivot_left_n_4h",
        "pivot_right_n_4h",
        "box_window_1m",
        "box_window_5m",
        "box_window_15m",
        "box_window_1h",
        "box_window_4h",
    )
    @classmethod
    def _validate_pivot_box_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Pivot- und Box-Fenster muessen > 0 sein")
        return value

    @field_validator("eventbus_dedupe_ttl_sec")
    @classmethod
    def _validate_non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("EVENTBUS_DEDUPE_TTL_SEC darf nicht negativ sein")
        return value

    @field_validator("structure_stream")
    @classmethod
    def _validate_stream(cls, value: str) -> str:
        normalized = value.strip()
        if normalized != STREAM_CANDLE_CLOSE:
            raise ValueError(
                "STRUCTURE_STREAM muss fuer Prompt 11 exakt events:candle_close sein"
            )
        return normalized

    @field_validator("structure_group", "structure_consumer", mode="before")
    @classmethod
    def _validate_names(cls, value: object) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("Structure Worker Namen duerfen nicht leer sein")
        return normalized

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> str:
        if value is None:
            return "INFO"
        return str(value).strip().upper() or "INFO"

    @model_validator(mode="after")
    def _validate_lookback(self) -> "StructureEngineSettings":
        max_pivot = max(
            self.pivot_left_n_1m + self.pivot_right_n_1m,
            self.pivot_left_n_5m + self.pivot_right_n_5m,
            self.pivot_left_n_15m + self.pivot_right_n_15m,
            self.pivot_left_n_1h + self.pivot_right_n_1h,
            self.pivot_left_n_4h + self.pivot_right_n_4h,
        )
        max_box = max(
            self.box_window_1m,
            self.box_window_5m,
            self.box_window_15m,
            self.box_window_1h,
            self.box_window_4h,
        )
        minimum = max(max_pivot + 5, max_box + 5, 50)
        if self.structure_lookback_candles < minimum:
            raise ValueError(
                f"STRUCTURE_LOOKBACK_CANDLES muss mindestens {minimum} sein "
                f"(Pivot/Box-Fenster)"
            )
        return self

    def pivot_for_timeframe(self, timeframe: str) -> tuple[int, int]:
        tf = normalize_timeframe(timeframe)
        match tf:
            case "1m":
                return self.pivot_left_n_1m, self.pivot_right_n_1m
            case "5m":
                return self.pivot_left_n_5m, self.pivot_right_n_5m
            case "15m":
                return self.pivot_left_n_15m, self.pivot_right_n_15m
            case "1H":
                return self.pivot_left_n_1h, self.pivot_right_n_1h
            case "4H":
                return self.pivot_left_n_4h, self.pivot_right_n_4h
            case _:
                raise ValueError(f"unsupported timeframe for pivot: {timeframe}")

    def box_window_for_timeframe(self, timeframe: str) -> int:
        tf = normalize_timeframe(timeframe)
        match tf:
            case "1m":
                return self.box_window_1m
            case "5m":
                return self.box_window_5m
            case "15m":
                return self.box_window_15m
            case "1H":
                return self.box_window_1h
            case "4H":
                return self.box_window_4h
            case _:
                raise ValueError(f"unsupported timeframe for box: {timeframe}")


def normalize_timeframe(timeframe: str) -> str:
    raw = timeframe.strip()
    aliases = {"1h": "1H", "4h": "4H"}
    return aliases.get(raw, raw)


def is_supported_timeframe(timeframe: str) -> bool:
    return normalize_timeframe(timeframe) in KNOWN_TIMEFRAMES
