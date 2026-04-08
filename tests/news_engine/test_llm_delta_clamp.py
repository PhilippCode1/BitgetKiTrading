from __future__ import annotations

from news_engine.scoring.llm_enricher import clamp_llm_relevance, merge_llm_with_rules
from news_engine.scoring.rules_v1 import Scored


def test_clamp_llm_relevance_bounds() -> None:
    assert clamp_llm_relevance(50, 100, 15) == 65
    assert clamp_llm_relevance(50, 20, 15) == 35
    assert clamp_llm_relevance(50, 52, 15) == 52


def test_merge_respects_delta() -> None:
    rule = Scored(relevance=40, sentiment="neutral", impact_window="mittel")
    llm = {
        "schema_version": "1.0",
        "headline_de": "t",
        "summary_de": "s",
        "relevance_score_0_100": 99,
        "sentiment_neg1_to_1": -0.9,
        "impact_keywords": [],
        "entities_mentioned": [],
        "confidence_0_1": 0.9,
        "impact_window": "sofort",
    }
    merged, _blob = merge_llm_with_rules(rule, llm, max_delta=15)
    assert merged.relevance == 55
    assert merged.sentiment == "baerisch"
    assert merged.impact_window == "sofort"


def test_merge_low_confidence_keeps_rule_sentiment() -> None:
    rule = Scored(relevance=30, sentiment="bullisch", impact_window="mittel")
    llm = {
        "schema_version": "1.0",
        "headline_de": "t",
        "summary_de": "s",
        "relevance_score_0_100": 30,
        "sentiment_neg1_to_1": -1.0,
        "impact_keywords": [],
        "entities_mentioned": [],
        "confidence_0_1": 0.1,
        "impact_window": "langsam",
    }
    merged, _ = merge_llm_with_rules(rule, llm, max_delta=15)
    assert merged.sentiment == "bullisch"
    assert merged.impact_window == "mittel"
