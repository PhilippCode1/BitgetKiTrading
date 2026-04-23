from __future__ import annotations

import logging
import re
from typing import Any

from news_engine.social.math_util import cosine_sim, l2_normalize, mean_vector

logger = logging.getLogger("news_engine.social.aggregator")

_SYM_RE = re.compile(r"\b(BTC|ETH|BITCOIN|ETHEREUM)\b", re.I)


def infer_symbols(text: str) -> list[str]:
    low = text.lower()
    hits = {m.group(1).upper() for m in _SYM_RE.finditer(text)}
    out: list[str] = []
    for h in hits:
        if h in ("BTC", "BITCOIN"):
            out.append("BTCUSDT")
        elif h in ("ETH", "ETHEREUM"):
            out.append("ETHUSDT")
    if "etf" in low and ("approv" in low or "approval" in low or "genehm" in low):
        out.append("BTCUSDT")
    return sorted(set(out)) or ["GLOBAL"]


class SentimentAggregator:
    """Kosinus zu Panik-/Euphorie-Zentroiden + rollierender EMA-Score pro Symbol."""

    def __init__(
        self,
        *,
        panic_centroid: list[float],
        euphoria_centroid: list[float],
        roll_alpha: float,
    ) -> None:
        self._panic = l2_normalize(panic_centroid)
        self._euphoria = l2_normalize(euphoria_centroid)
        self._roll_alpha = max(0.01, min(0.99, roll_alpha))

    @staticmethod
    def from_reference_vectors(
        panic_vecs: list[list[float]],
        euphoria_vecs: list[list[float]],
        roll_alpha: float,
    ) -> "SentimentAggregator":
        pc = mean_vector([l2_normalize(v) for v in panic_vecs])
        ec = mean_vector([l2_normalize(v) for v in euphoria_vecs])
        return SentimentAggregator(panic_centroid=pc, euphoria_centroid=ec, roll_alpha=roll_alpha)

    def instantaneous_score(self, embedding: list[float]) -> tuple[float, float, float]:
        e = l2_normalize(embedding)
        cp = cosine_sim(e, self._panic)
        ce = cosine_sim(e, self._euphoria)
        raw = (ce - cp) * 1.85
        inst = max(-1.0, min(1.0, raw))
        return inst, cp, ce

    def update_rolling(self, redis: Any | None, symbol: str, inst: float) -> float:
        if redis is None:
            return inst
        key = f"social:roll:{symbol}"
        try:
            prev_raw = redis.get(key)
            prev = float(prev_raw) if prev_raw is not None else 0.0
        except (TypeError, ValueError):
            prev = 0.0
        nxt = self._roll_alpha * inst + (1.0 - self._roll_alpha) * prev
        try:
            redis.setex(key, 7200, f"{nxt:.8f}")
        except Exception as exc:
            logger.debug("roll redis set %s: %s", key, exc)
        return nxt
