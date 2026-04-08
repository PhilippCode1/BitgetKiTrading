from __future__ import annotations

from decimal import Decimal

from paper_broker.strategy.news_shock import (
    evaluate_news_shock,
    sentiment_opposes_position,
)


def test_sentiment_opposes_long() -> None:
    assert sentiment_opposes_position("baerisch", "long")
    assert sentiment_opposes_position("bearish", "long")
    assert not sentiment_opposes_position("bullisch", "long")


def test_evaluate_news_shock_partial() -> None:
    hit, action, _ = evaluate_news_shock(
        relevance_score=85,
        sentiment="baerisch",
        impact_window="sofort",
        position_side="long",
        shock_threshold=80,
        partial_pct=Decimal("0.5"),
    )
    assert hit
    assert action == "partial"


def test_evaluate_news_shock_full_high_pct() -> None:
    hit, action, _ = evaluate_news_shock(
        relevance_score=90,
        sentiment="baerisch",
        impact_window="immediate",
        position_side="long",
        shock_threshold=80,
        partial_pct=Decimal("1.0"),
    )
    assert hit
    assert action == "full"
