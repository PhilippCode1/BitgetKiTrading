from __future__ import annotations

from decimal import Decimal
from typing import Any

from learning_engine.config import LearningEngineSettings


def apply_error_labels(
    *,
    settings: LearningEngineSettings,
    stop_distance_atr_mult: Decimal | None,
    false_breakout_events: list[dict[str, Any]],
    multi_tf_score: float | None,
    feature_4h_trend: int | None,
    side: str,
    news_shock: bool,
    stale_signal: bool,
) -> list[str]:
    labels: list[str] = []
    min_atr = Decimal(str(settings.learn_stop_min_atr_mult))
    if stop_distance_atr_mult is not None and stop_distance_atr_mult < min_atr:
        labels.append("STOP_TOO_TIGHT")
    if false_breakout_events:
        labels.append("FALSE_BREAKOUT")
    thr = settings.learn_multi_tf_threshold
    if multi_tf_score is not None and float(multi_tf_score) < thr:
        labels.append("HIGH_TF_CONFLICT")
    if feature_4h_trend is not None:
        s = side.lower()
        if s == "long" and feature_4h_trend < 0:
            labels.append("HIGH_TF_CONFLICT")
        if s == "short" and feature_4h_trend > 0:
            labels.append("HIGH_TF_CONFLICT")
    if news_shock:
        labels.append("NEWS_SHOCK")
    if stale_signal:
        labels.append("STALE_DATA")
    return sorted({x for x in labels})
