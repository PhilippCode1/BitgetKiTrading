from __future__ import annotations

import asyncio

from llm_orchestrator.agents.macro import MacroAnalystAgent, _merge_social_sentiment_context


def test_merge_social_adjusts_payload() -> None:
    raw = {
        "confidence_0_1": 0.5,
        "signal_proposal": {"action": "hold_research", "symbol": None, "timeframe": None, "payload": {}},
    }
    ctx = {
        "social_context": {
            "rolling_sentiment_score": 0.6,
            "sentiment_score": 0.55,
            "panic_cosine": 0.1,
            "euphoria_cosine": 0.8,
            "text_excerpt": "ETF approved narrative",
        }
    }
    _merge_social_sentiment_context(raw, ctx)
    pl = raw["signal_proposal"]["payload"]
    assert pl.get("social_rolling_sentiment_neg1_1") == 0.6
    assert "social_text_excerpt_de" in pl
    assert float(raw["confidence_0_1"]) > 0.5


def test_macro_analyze_offline_sees_social_block() -> None:
    agent = MacroAnalystAgent()
    context = {
        "news_context": {},
        "social_context": {"rolling_sentiment_score": 0.4, "sentiment_score": 0.5},
    }
    out = asyncio.run(agent.analyze(context))
    pl = (out.get("signal_proposal") or {}).get("payload") or {}
    assert pl.get("social_rolling_sentiment_neg1_1") == 0.4
