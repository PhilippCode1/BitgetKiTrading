from __future__ import annotations

from typing import ClassVar

from config.settings import BaseServiceSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict


class AdversarialEngineSettings(BaseServiceSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        populate_by_name=True,
    )
    production_required_fields: ClassVar[tuple[str, ...]] = (
        BaseServiceSettings.production_required_fields
    )
    production_required_non_local_fields: ClassVar[tuple[str, ...]] = (
        BaseServiceSettings.production_required_non_local_fields
    )

    adversarial_engine_port: int = Field(default=8145, alias="ADVERSARIAL_ENGINE_PORT")

    ams_latent_dim: int = Field(default=48, ge=8, le=512, alias="AMS_LATENT_DIM")
    ams_default_seq_len: int = Field(default=128, ge=32, le=2048, alias="AMS_DEFAULT_SEQ_LEN")
    ams_price_depth_rho: float = Field(
        default=0.72,
        ge=-0.95,
        le=0.95,
        alias="AMS_PRICE_DEPTH_RHO",
        description="Ziel-Korrelation log-Return vs. Orderbuch-Tiefen-Imbalance (L3-Proxy).",
    )
    ams_checkpoint_path: str | None = Field(
        default=None,
        alias="AMS_CHECKPOINT_PATH",
        description="Optional: PyTorch state_dict fuer Generator/Critic.",
    )
