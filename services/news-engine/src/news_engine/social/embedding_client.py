from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger("news_engine.social.embedding_client")


def _text_key(text: str) -> str:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"social:emb:{h}"


async def _http_embed(base_url: str, texts: list[str]) -> tuple[list[list[float]], str]:
    url = base_url.rstrip("/") + "/v1/embed"
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, json={"texts": texts, "normalize": True})
        r.raise_for_status()
        data = r.json()
    vecs = data.get("vectors") or []
    backend = str(data.get("backend") or "unknown")
    if not isinstance(vecs, list):
        return [], backend
    out = [[float(x) for x in row] for row in vecs if isinstance(row, list)]
    return out, backend


async def embed_texts(
    *,
    base_url: str,
    texts: list[str],
    redis: Any | None,
    cache_ttl_sec: int,
) -> tuple[list[list[float] | None], str, float]:
    """Liefert pro Eingabetext einen Vektor oder None (Reihenfolge erhalten). backend, wall_ms."""
    t0 = time.perf_counter()
    if not texts:
        return [], "none", 0.0
    results: list[list[float] | None] = [None] * len(texts)
    to_fetch: list[tuple[int, str]] = []
    for i, tx in enumerate(texts):
        if redis is not None:
            try:
                raw = redis.get(_text_key(tx))
                if raw:
                    results[i] = json.loads(raw)
            except Exception as exc:
                logger.debug("redis emb get: %s", exc)
        if results[i] is None:
            to_fetch.append((i, tx))
    backend = "redis_hit"
    if to_fetch:
        texts_only = [t for _, t in to_fetch]
        vecs, backend = await _http_embed(base_url, texts_only)
        if len(vecs) != len(to_fetch):
            logger.warning("embed batch size mismatch want=%s got=%s", len(to_fetch), len(vecs))
        for k, (i, tx) in enumerate(to_fetch):
            if k >= len(vecs):
                break
            vec = vecs[k]
            results[i] = vec
            if redis is not None:
                try:
                    redis.setex(_text_key(tx), cache_ttl_sec, json.dumps(vec))
                except Exception as exc:
                    logger.debug("redis emb set: %s", exc)
    ms = (time.perf_counter() - t0) * 1000.0
    return results, backend, ms
