from __future__ import annotations

import asyncio

from llm_orchestrator.agents.macro import MacroAnalystAgent, _merge_onchain_whale_context


def test_merge_onchain_whale_lowers_confidence() -> None:
    raw = {
        "confidence_0_1": 0.9,
        "signal_proposal": {"action": "hold_research", "symbol": None, "timeframe": None, "payload": {}},
    }
    ctx = {"onchain_context": {"onchain_whale_pressure_0_1": 0.8}}
    _merge_onchain_whale_context(raw, ctx)
    assert float(raw["confidence_0_1"]) < 0.9
    pl = raw["signal_proposal"]["payload"]
    assert pl.get("onchain_whale_pressure_0_1") == 0.8


def test_macro_analyze_applies_onchain_offline() -> None:
    agent = MacroAnalystAgent()
    context = {
        "news_context": {},
        "onchain_context": {
            "onchain_whale_pressure_0_1": 0.5,
            "recent_onchain_whale_events_json": [{"estimated_volume_usd": 3_000_000}],
        },
    }
    out = asyncio.run(agent.analyze(context))
    assert out.get("agent_id") == "macro_analyst"
    pl = (out.get("signal_proposal") or {}).get("payload") or {}
    assert "onchain_whale_pressure_0_1" in pl
