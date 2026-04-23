from __future__ import annotations

from functools import cached_property

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OnchainSnifferSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ONCHAIN_",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = Field(default="onchain-sniffer", validation_alias="SERVICE_NAME")
    bind_host: str = Field(default="0.0.0.0")
    bind_port: int = Field(default=8096)

    redis_url: str = Field(
        default="redis://127.0.0.1:6379/0",
        validation_alias=AliasChoices("REDIS_URL", "ONCHAIN_REDIS_URL"),
    )

    eth_ws_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ETH_WS_URL", "ONCHAIN_ETH_WS_URL"),
    )
    eth_http_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ETH_HTTP_URL", "ONCHAIN_ETH_HTTP_URL"),
    )

    solana_ws_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SOLANA_WS_URL", "ONCHAIN_SOLANA_WS_URL"),
    )

    min_notional_usd: float = Field(default=500_000.0, ge=1.0)
    eth_usd_mark: float = Field(default=3500.0, ge=0.01)
    pool_tvl_usd_hint: float = Field(
        default=50_000_000.0,
        ge=1.0,
        description="Heuristik fuer Impact, wenn keine On-Chain-Reserves gelesen werden",
    )

    reserve_in_hint: float | None = Field(default=None, ge=0.0)
    reserve_out_hint: float | None = Field(default=None, ge=0.0)

    max_pending_fetch_concurrency: int = Field(default=48, ge=1, le=256)
    dedupe_cache_size: int = Field(default=20_000, ge=1000)

    onchain_impact_lib_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ONCHAIN_IMPACT_LIB_PATH"),
    )

    eth_listener_enabled: bool = Field(default=True)
    solana_listener_enabled: bool = Field(default=False)

    @cached_property
    def has_eth_stack(self) -> bool:
        return bool(self.eth_ws_url and self.eth_http_url)
