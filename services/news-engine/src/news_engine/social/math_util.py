from __future__ import annotations

import math


def l2_normalize(v: list[float]) -> list[float]:
    s = math.sqrt(sum(x * x for x in v)) + 1e-12
    return [x / s for x in v]


def cosine_sim(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb + 1e-12)


def mean_vector(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    d = len(vectors[0])
    acc = [0.0] * d
    for v in vectors:
        for i, x in enumerate(v):
            acc[i] += x
    n = float(len(vectors))
    return [x / n for x in acc]
