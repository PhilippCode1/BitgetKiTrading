from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("httpx")

from llm_orchestrator.agents import (
    AgentRegistry,
    MacroAnalystAgent,
    QuantAnalystAgent,
    RiskGovernorAgent,
    validate_agent_message,
)
from llm_orchestrator.config import LLMOrchestratorSettings


def test_three_agents_instantiate_independently(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_USE_FAKE_PROVIDER", "true")
    settings = LLMOrchestratorSettings()
    macro = MacroAnalystAgent(settings=settings)
    quant = QuantAnalystAgent(feature_engine_base_url="http://127.0.0.1:9")
    risk = RiskGovernorAgent()
    assert macro.agent_id == "macro_analyst"
    assert quant.agent_id == "quant_analyst"
    assert risk.agent_id == "risk_governor"


def test_macro_fake_provider_validates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_USE_FAKE_PROVIDER", "true")
    macro = MacroAnalystAgent(settings=LLMOrchestratorSettings())
    out = asyncio.run(macro.analyze({"news_context": {"headline": "Test"}}))
    validate_agent_message(out)
    assert asyncio.run(macro.get_confidence_score()) == out["confidence_0_1"]


def test_quant_agent_mock_http(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    class FakeResp:
        status_code = 200
        text = ""

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "status": "ok",
                "feature": {
                    "rsi_14": 28.0,
                    "momentum_score": 0.05,
                    "trend_dir": 1,
                },
            }

    class FakeClient:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *a: object) -> None:
            return None

        async def get(self, *a: object, **k: object) -> FakeResp:
            return FakeResp()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    quant = QuantAnalystAgent(feature_engine_base_url="http://mock")
    out = asyncio.run(quant.analyze({"symbol": "BTCUSDT", "timeframe": "1m"}))
    validate_agent_message(out)
    assert out["signal_proposal"]["action"] == "buy_bias"


def test_risk_governor_agent_allow(monkeypatch: pytest.MonkeyPatch) -> None:
    risk = RiskGovernorAgent()
    out = asyncio.run(
        risk.analyze(
            {
                "signal_row": {"source_snapshot_json": {}},
                "direction": "long",
            }
        )
    )
    validate_agent_message(out)
    assert out["signal_proposal"]["action"] in {"allow", "veto"}


def test_risk_governor_vpin_hard_veto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RISK_GOVERNOR_AMS_MODE", "off")

    def _fake_assess_risk_governor(**_kwargs: object) -> dict:
        return {
            "version": "test",
            "trade_action_recommendation": "allow_trade",
            "universal_hard_block_reasons_json": None,
            "hard_block_reasons_json": [],
            "quality_tier": "A",
        }

    monkeypatch.setattr(
        "signal_engine.risk_governor.assess_risk_governor",
        _fake_assess_risk_governor,
    )
    risk = RiskGovernorAgent(llm_settings=LLMOrchestratorSettings())
    out = asyncio.run(
        risk.analyze(
            {
                "signal_row": {"source_snapshot_json": {}},
                "direction": "long",
                "vpin_toxicity_0_1": 0.95,
            }
        )
    )
    validate_agent_message(out)
    assert out["signal_proposal"]["action"] == "veto"
    assert out["signal_proposal"]["payload"].get("vpin_override_applied") is True


def test_agent_registry_build_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_USE_FAKE_PROVIDER", "true")
    import httpx

    class FakeResp:
        status_code = 404
        text = "nf"

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {}

    class FakeClient:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *a: object) -> None:
            return None

        async def get(self, *a: object, **k: object) -> FakeResp:
            return FakeResp()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    reg = AgentRegistry.build_default(
        settings=LLMOrchestratorSettings(),
        feature_engine_base_url="http://mock",
    )
    assert set(reg.list_ids()) == {"macro_analyst", "quant_analyst", "risk_governor"}
    q = reg.get("quant_analyst")
    assert isinstance(q, QuantAnalystAgent)
    out = asyncio.run(q.analyze({"symbol": "ETHUSDT", "timeframe": "5m"}))
    validate_agent_message(out)
