from __future__ import annotations

import pytest
from learning_engine.config import LearningEngineSettings
from learning_engine.labeling.rules_v1 import apply_error_labels


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> LearningEngineSettings:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    return LearningEngineSettings()


def test_stop_too_tight(settings: LearningEngineSettings) -> None:
    from decimal import Decimal

    labels = apply_error_labels(
        settings=settings,
        stop_distance_atr_mult=Decimal("0.3"),
        false_breakout_events=[],
        multi_tf_score=None,
        feature_4h_trend=None,
        side="long",
        news_shock=False,
        stale_signal=False,
    )
    assert "STOP_TOO_TIGHT" in labels


def test_news_shock_label(settings: LearningEngineSettings) -> None:
    labels = apply_error_labels(
        settings=settings,
        stop_distance_atr_mult=None,
        false_breakout_events=[],
        multi_tf_score=None,
        feature_4h_trend=None,
        side="long",
        news_shock=True,
        stale_signal=False,
    )
    assert "NEWS_SHOCK" in labels
