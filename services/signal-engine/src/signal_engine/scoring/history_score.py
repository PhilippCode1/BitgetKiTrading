"""
Schicht 6: Historik — konservativ, ohne Fantasiewerte.
"""

from __future__ import annotations

from signal_engine.config import SignalEngineSettings
from signal_engine.models import LayerScore, ScoringContext


def score_history(
    ctx: ScoringContext,
    settings: SignalEngineSettings,
    *,
    prior_avg_strength: float | None,
    prior_count: int,
) -> LayerScore:
    if prior_count < 5 or prior_avg_strength is None:
        return LayerScore(
            settings.signal_default_history_neutral_score,
            [
                f"insufficient_history_count={prior_count}",
                f"neutral_default={settings.signal_default_history_neutral_score}",
            ],
            ["history_sparse"],
        )

    mapped = 40.0 + min(60.0, prior_avg_strength * 0.55)
    score = max(0.0, min(100.0, mapped))
    return LayerScore(
        score,
        [
            f"prior_signals={prior_count}",
            f"prior_avg_strength={prior_avg_strength:.2f}",
        ],
        [],
    )
