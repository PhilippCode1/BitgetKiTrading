"""BGE-m3 Embeddings (1024-d) via sentence-transformers + PyTorch; CPU/GPU auto."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import numpy as np

logger = logging.getLogger("inference_server.embedding_model")

_DIM = 1024


def _hash_embedding_fallback(texts: list[str]) -> list[list[float]]:
    """Deterministischer Fallback ohne vollstaendiges HF-Modell (CI / Notstart)."""
    out: list[list[float]] = []
    for t in texts:
        seed = int.from_bytes(hashlib.sha256(t.encode("utf-8")).digest()[:8], "big", signed=False)
        x = seed % (2**31 - 1) or 1
        vec = np.empty(_DIM, dtype=np.float64)
        for i in range(_DIM):
            x = (1103515245 * x + 12345) % (2**31)
            vec[i] = (x / (2**31)) * 2.0 - 1.0
        vec /= np.linalg.norm(vec) + 1e-9
        out.append(vec.tolist())
    return out


_cached_eng: EmbeddingEngine | None = None
_cached_mid: str | None = None


def get_embedding_engine(*, model_id: str, prefer_cuda: bool) -> EmbeddingEngine:
    global _cached_eng, _cached_mid
    if _cached_eng is None or _cached_mid != model_id:
        _cached_eng = EmbeddingEngine(model_id=model_id, prefer_cuda=prefer_cuda)
        _cached_mid = model_id
    return _cached_eng


class EmbeddingEngine:
    def __init__(self, *, model_id: str, prefer_cuda: bool = True) -> None:
        self._model_id = model_id
        self._prefer_cuda = prefer_cuda
        self._model: Any = None
        self._device: str | None = None

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers/torch nicht installiert — Embedding-Pfad nicht verfuegbar"
            ) from exc
        device = "cuda" if self._prefer_cuda and torch.cuda.is_available() else "cpu"
        if device == "cpu" and self._prefer_cuda:
            logger.warning("CUDA nicht verfuegbar — Embeddings laufen auf CPU")
        self._device = device
        self._model = SentenceTransformer(self._model_id, device=device)
        logger.info("EmbeddingEngine geladen model=%s device=%s", self._model_id, device)

    def encode(self, texts: list[str], *, normalize: bool = True) -> list[list[float]]:
        if not texts:
            return []
        self._ensure_model()
        assert self._model is not None
        embs = self._model.encode(
            texts,
            normalize_embeddings=normalize,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        out: list[list[float]] = []
        for row in embs:
            v = np.asarray(row, dtype=np.float64).ravel()
            if v.size != _DIM:
                raise ValueError(f"unexpected embedding dim {v.size}, expected {_DIM}")
            out.append(v.tolist())
        return out


def encode_with_optional_fallback(
    texts: list[str],
    *,
    model_id: str,
    prefer_cuda: bool,
    allow_fallback: bool,
) -> tuple[list[list[float]], str]:
    try:
        eng = get_embedding_engine(model_id=model_id, prefer_cuda=prefer_cuda)
        return eng.encode(texts), "bge-m3"
    except Exception as exc:
        if not allow_fallback:
            raise
        logger.warning("BGE-Embed fehlgeschlagen, Fallback aktiv: %s", exc)
        return _hash_embedding_fallback(texts), "hash_fallback"
