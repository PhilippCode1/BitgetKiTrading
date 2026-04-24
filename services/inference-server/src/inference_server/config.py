from __future__ import annotations

from typing import ClassVar

from config.settings import BaseServiceSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict


class InferenceServerSettings(BaseServiceSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        populate_by_name=True,
    )
    production_required_fields: ClassVar[tuple[str, ...]] = (
        BaseServiceSettings.production_required_fields + ("redis_url",)
    )
    production_required_non_local_fields: ClassVar[tuple[str, ...]] = (
        BaseServiceSettings.production_required_non_local_fields + ("redis_url",)
    )

    redis_url: str = Field(alias="REDIS_URL")

    inference_grpc_port: int = Field(default=50051, alias="INFERENCE_GRPC_PORT")
    inference_http_port: int = Field(default=8140, alias="INFERENCE_HTTP_PORT")

    timesfm_model_id: str = Field(
        default="google/timesfm-1.0-200m",
        alias="TIMESFM_MODEL_ID",
        description="HuggingFace-/Checkpoint-Name (Platzhalter bis Library installiert).",
    )
    timesfm_max_inflight_batches: int = Field(
        default=4,
        ge=1,
        le=64,
        alias="TIMESFM_MAX_INFLIGHT_BATCHES",
    )
    timesfm_batch_semaphore_wait_sec: float = Field(
        default=2.0,
        ge=0.1,
        le=60.0,
        alias="TIMESFM_BATCH_SEMAPHORE_WAIT_SEC",
    )
    timesfm_dynamic_batching_enabled: bool = Field(
        default=True,
        alias="TIMESFM_DYNAMIC_BATCHING_ENABLED",
    )
    timesfm_dynamic_batch_max_wait_ms: float = Field(
        default=2.0,
        ge=0.0,
        le=50.0,
        alias="TIMESFM_DYNAMIC_BATCH_MAX_WAIT_MS",
    )
    timesfm_dynamic_batch_max_size: int = Field(
        default=8,
        ge=1,
        le=32,
        alias="TIMESFM_DYNAMIC_BATCH_MAX_SIZE",
    )

    monitor_engine_base_url: str = Field(
        default="http://monitor-engine:8110",
        alias="MONITOR_ENGINE_BASE_URL",
        description="Basis-URL fuer Batch-Latenz-Metrik (POST /ops/inference-batch-metric).",
    )

    embedding_enabled: bool = Field(default=True, alias="INFERENCE_EMBEDDING_ENABLED")
    embedding_model_id: str = Field(default="BAAI/bge-m3", alias="INFERENCE_EMBEDDING_MODEL_ID")
    embedding_prefer_cuda: bool = Field(default=True, alias="INFERENCE_EMBEDDING_PREFER_CUDA")
    embedding_allow_hash_fallback: bool = Field(
        default=True,
        alias="INFERENCE_EMBEDDING_ALLOW_HASH_FALLBACK",
        description="Wenn HF/Torch fehlt: deterministischer Hash-Vektor (nur fuer Tests/Notstart).",
    )
