from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from inference_server.config import InferenceServerSettings
from inference_server.embedding_model import encode_with_optional_fallback

logger = logging.getLogger("inference_server.embed")


class EmbedRequest(BaseModel):
    texts: list[str] = Field(default_factory=list, max_length=64)
    normalize: bool = True


class EmbedResponse(BaseModel):
    vectors: list[list[float]]
    dim: int = 1024
    backend: str
    wall_ms: float


def build_embedding_router(settings: InferenceServerSettings) -> APIRouter:
    r = APIRouter(tags=["embeddings"])

    @r.post("/v1/embed", response_model=EmbedResponse)
    def embed(req: EmbedRequest) -> EmbedResponse:
        if not settings.embedding_enabled:
            raise HTTPException(status_code=503, detail="embeddings_disabled")
        if not req.texts:
            return EmbedResponse(vectors=[], dim=1024, backend="none", wall_ms=0.0)
        t0 = time.perf_counter()
        vecs, backend = encode_with_optional_fallback(
            req.texts,
            model_id=settings.embedding_model_id,
            prefer_cuda=settings.embedding_prefer_cuda,
            allow_fallback=settings.embedding_allow_hash_fallback,
        )
        ms = (time.perf_counter() - t0) * 1000.0
        logger.debug("embed count=%s backend=%s ms=%.2f", len(req.texts), backend, ms)
        return EmbedResponse(vectors=vecs, dim=1024, backend=backend, wall_ms=round(ms, 3))

    @r.get("/v1/embed/health")
    def embed_health() -> dict[str, Any]:
        try:
            import torch

            cuda = bool(torch.cuda.is_available())
        except Exception:
            cuda = False
        return {
            "embedding_enabled": settings.embedding_enabled,
            "model_id": settings.embedding_model_id,
            "cuda_available": cuda,
        }

    return r
