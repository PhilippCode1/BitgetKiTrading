from __future__ import annotations

import pytest
from pydantic import ValidationError

from signal_engine.config import SignalEngineSettings
from signal_engine.models import LayerScore, ScoringContext
from signal_engine.scoring.news_score import NEWS_LAYER_SENTIMENT_SCORE_CAP, score_news


def test_signal_weight_news_cannot_exceed_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@127.0.0.1:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("SIGNAL_WEIGHT_NEWS", "0.16")
    with pytest.raises(ValidationError, match="SIGNAL_WEIGHT_NEWS"):
        SignalEngineSettings()


def test_weight_tuple_redistributes_when_news_composite_disabled(signal_settings) -> None:
    s = signal_settings.model_copy(update={"signal_news_in_composite_enabled": False})
    t = s.weight_tuple()
    assert t[3] == 0.0
    assert abs(sum(t) - 1.0) < 1e-6
    assert t[0] == pytest.approx(signal_settings.signal_weight_structure + signal_settings.signal_weight_news)


def test_score_news_ignores_db_when_layer_disabled(signal_settings) -> None:
    s = signal_settings.model_copy(update={"signal_news_in_composite_enabled": False})
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1_700_000_000_000,
        structure_state={"trend_dir": "UP"},
        structure_events=[],
        primary_feature={"computed_ts_ms": 1_700_000_000_000},
        features_by_tf={},
        drawings=[],
        news_row={"relevance_score": 99, "sentiment": "baerisch"},
        last_close=100_000.0,
    )
    out = score_news(ctx, s)
    assert isinstance(out, LayerScore)
    assert out.score == float(s.signal_default_news_neutral_score)
    assert any("news_layer_disabled" in n for n in out.notes)


def test_score_news_sentiment_clamped_to_cap(signal_settings) -> None:
    """Extrem-Sentiment darf den Layer-Score nur um NEWS_LAYER_SENTIMENT_SCORE_CAP verschieben."""
    s = signal_settings.model_copy(update={"signal_news_in_composite_enabled": True})
    neutral = float(s.signal_default_news_neutral_score)
    ctx_extreme = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1_700_000_000_000,
        structure_state={"trend_dir": "UP"},
        structure_events=[],
        primary_feature={"computed_ts_ms": 1_700_000_000_000},
        features_by_tf={},
        drawings=[],
        news_row={"relevance_score": None, "sentiment": 999.0},
        last_close=100_000.0,
    )
    out_hi = score_news(ctx_extreme, s)
    ctx_neg = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1_700_000_000_000,
        structure_state={"trend_dir": "UP"},
        structure_events=[],
        primary_feature={"computed_ts_ms": 1_700_000_000_000},
        features_by_tf={},
        drawings=[],
        news_row={"relevance_score": None, "sentiment": -999.0},
        last_close=100_000.0,
    )
    out_lo = score_news(ctx_neg, s)
    assert out_hi.score == pytest.approx(
        max(0.0, min(100.0, neutral + NEWS_LAYER_SENTIMENT_SCORE_CAP))
    )
    assert out_lo.score == pytest.approx(
        max(0.0, min(100.0, neutral - NEWS_LAYER_SENTIMENT_SCORE_CAP))
    )
