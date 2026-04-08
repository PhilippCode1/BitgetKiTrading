"""
Trade-relevante Evaluierungsmetriken jenseits reiner Accuracy (Abstention, Tails, Stop-Modi).
"""

from __future__ import annotations

from collections import Counter
from typing import Any


def stop_failure_mode_rates(examples: list[dict[str, Any]]) -> dict[str, int]:
    c: Counter[str] = Counter()
    for ex in examples:
        for lab in ex.get("error_labels") or []:
            if lab:
                c[str(lab)] += 1
    return dict(sorted(c.items()))


def trade_relevance_binary_classification_report(
    y_true: list[int],
    probs: list[float],
    *,
    abstain_threshold: float = 0.42,
    high_confidence: float = 0.65,
    tail_quantile: float = 0.9,
) -> dict[str, Any]:
    """Für kalibrierte Take-Trade-Wahrscheinlichkeiten auf Holdout-Test."""
    n = len(y_true)
    if n != len(probs) or n == 0:
        return {"error": "length_mismatch_or_empty", "count": n}

    abstain = [p < abstain_threshold for p in probs]
    ab_count = sum(abstain)
    ab_correct = sum(1 for yt, a in zip(y_true, abstain, strict=True) if a and yt == 0)
    abstention_precision = float(ab_correct / ab_count) if ab_count else None

    high_mask = [p >= high_confidence for p in probs]
    hi_n = sum(high_mask)
    hi_fp = sum(1 for yt, h in zip(y_true, high_mask, strict=True) if h and yt == 0)
    high_conf_false_positive_rate = float(hi_fp / hi_n) if hi_n else None

    sorted_p = sorted(probs)
    q_idx = min(len(sorted_p) - 1, int((len(sorted_p) - 1) * tail_quantile))
    thresh = sorted_p[q_idx]
    tail_mask = [p >= thresh for p in probs]
    tn = sum(tail_mask)
    tail_fp = sum(1 for yt, t in zip(y_true, tail_mask, strict=True) if t and yt == 0)
    top_decile_tail_fp_rate = float(tail_fp / tn) if tn else None

    route_stability_proxy = {
        "prob_std": _safe_std(probs),
        "prob_mean": sum(probs) / n,
        "n": n,
        "note_de": "Grobe Streuung der Modellwahrscheinlichkeiten auf dem Testausschnitt (kein Router-Argmax).",
    }

    return {
        "count": n,
        "abstention_threshold": abstain_threshold,
        "abstention_count": ab_count,
        "abstention_precision_on_negative_class": abstention_precision,
        "high_confidence_threshold": high_confidence,
        "high_confidence_count": hi_n,
        "high_confidence_false_positive_rate": high_conf_false_positive_rate,
        "tail_quantile": tail_quantile,
        "tail_probability_threshold_used": thresh,
        "top_decile_tail_false_positive_rate": top_decile_tail_fp_rate,
        "route_stability_proxy": route_stability_proxy,
    }


def _safe_std(vals: list[float]) -> float | None:
    if len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    var = sum((x - m) ** 2 for x in vals) / (len(vals) - 1)
    return float(var**0.5)


def execution_sensitivity_proxy(
    examples: list[dict[str, Any]],
    probs: list[float],
    *,
    feature_key: str = "execution_cost_bps",
) -> dict[str, Any]:
    """Korrelation P(take) vs. Execution-Cost aus Feature-Vektor (falls vorhanden)."""
    xs: list[float] = []
    ps: list[float] = []
    for ex, p in zip(examples, probs, strict=True):
        feats = ex.get("features")
        if not isinstance(feats, dict):
            continue
        v = feats.get(feature_key)
        if v is None:
            continue
        try:
            xs.append(float(v))
            ps.append(float(p))
        except (TypeError, ValueError):
            continue
    if len(xs) < 8:
        return {"available": False, "n": len(xs)}
    mx = sum(xs) / len(xs)
    mp = sum(ps) / len(ps)
    num = sum((x - mx) * (p - mp) for x, p in zip(xs, ps, strict=True))
    denx = sum((x - mx) ** 2 for x in xs) ** 0.5
    denp = sum((p - mp) ** 2 for p in ps) ** 0.5
    corr = float(num / (denx * denp)) if denx > 0 and denp > 0 else None
    return {"available": True, "n": len(xs), "pearson_prob_vs_execution_cost_bps": corr}
