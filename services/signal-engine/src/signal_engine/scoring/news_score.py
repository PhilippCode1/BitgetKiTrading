"""
Schicht 4: News-Score (DB) oder explizit markierter Neutral-Default.
"""

from __future__ import annotations

from signal_engine.config import SignalEngineSettings
from signal_engine.models import LayerScore, ScoringContext
from signal_engine.news_compat import news_sentiment_as_float

# Sentiment darf den News-Layer nur begrenzt verschieben (randstaendig; kein LLM in der Kernpipeline).
NEWS_LAYER_SENTIMENT_SCORE_CAP = 15.0


def score_news(ctx: ScoringContext, settings: SignalEngineSettings) -> LayerScore:
    if not settings.signal_news_in_composite_enabled:
        nd = float(settings.signal_default_news_neutral_score)
        return LayerScore(
            nd,
            [
                "news_layer_disabled_env",
                f"neutral_fixed={nd}",
            ],
            ["news_optional_bypass"],
        )

    if ctx.news_row is None:
        return LayerScore(
            settings.signal_default_news_neutral_score,
            [
                "no_news_row",
                f"neutral_default={settings.signal_default_news_neutral_score}",
            ],
            ["news_unavailable"],
        )

    rel = ctx.news_row.get("relevance_score")
    sent = news_sentiment_as_float(ctx.news_row.get("sentiment"))
    notes = []
    base = float(settings.signal_default_news_neutral_score)
    if rel is not None:
        r = float(rel)
        base = 40.0 + min(60.0, max(0.0, r) * 0.6)
        notes.append(f"relevance={r}")
    if sent is not None:
        s = float(sent)
        cap = NEWS_LAYER_SENTIMENT_SCORE_CAP
        base += max(-cap, min(cap, s * 10.0))
        notes.append(f"sentiment_adjust={s}")

    score = max(0.0, min(100.0, base))
    notes.append("news_from_db")
    return LayerScore(score, notes, [])
