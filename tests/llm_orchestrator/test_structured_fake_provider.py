from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(mock_redis_bus, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("LLM_USE_FAKE_PROVIDER", "true")
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")
    monkeypatch.setenv("API_GATEWAY_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("NEXT_PUBLIC_API_BASE_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("NEXT_PUBLIC_WS_BASE_URL", "ws://127.0.0.1:8000")
    from llm_orchestrator.app import create_app

    ikey = os.environ.get("INTERNAL_API_KEY", "").strip()
    hdrs = {"X-Internal-Service-Key": ikey} if ikey else {}
    return TestClient(create_app(), headers=hdrs)


def test_post_structured_fake_valid_json(client: TestClient) -> None:
    body = {
        "schema_json": {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
        },
        "prompt": "test",
        "temperature": 0.1,
    }
    r = client.post("/llm/structured", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data["provider"] == "fake"
    assert data["result"]["a"] == "fake"
    assert data["result"]["b"] == 0
    prov = data["provenance"]
    assert prov["llm_derived"] is True
    assert prov["task_type"] == "structured_adhoc"
    assert len(prov["prompt_fingerprint_sha256"]) == 64


def test_news_summary_matches_contract(client: TestClient) -> None:
    body = {
        "title": "Bitcoin futures funding update",
        "description": "SEC and regulation",
        "content": "btc market",
        "url": "https://example.com/n1",
        "source": "coindesk",
        "published_ts_ms": 1_700_000_000_000,
    }
    r = client.post("/llm/news_summary", json=body)
    assert r.status_code == 200, r.text
    payload = r.json()
    out = payload["result"]
    assert out["schema_version"] == "1.0"
    assert 0 <= out["relevance_score_0_100"] <= 100
    assert -1 <= out["sentiment_neg1_to_1"] <= 1
    assert isinstance(out["impact_keywords"], list)
    assert payload["provenance"]["task_type"] == "news_summary"
    ret = payload["provenance"].get("retrieval")
    assert ret is None or (isinstance(ret, dict) and "chunks" in ret)


def test_analyst_hypotheses_and_operator_explain(client: TestClient) -> None:
    r = client.post("/llm/analyst/hypotheses", json={"context_json": {"symbol": "BTCUSDT"}})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["provenance"]["task_type"] == "analyst_hypotheses"
    assert d["result"]["schema_version"] == "1.0"
    assert len(d["result"]["hypotheses"]) >= 1

    r2 = client.post(
        "/llm/analyst/operator_explain",
        json={"question_de": "Was bedeutet Live-Gate?", "readonly_context_json": {}},
    )
    assert r2.status_code == 200, r2.text
    payload2 = r2.json()
    assert payload2["provider"] == "fake"
    ex = payload2["result"]
    assert ex["execution_authority"] == "none"
    assert "[TEST-PROVIDER" in (ex.get("explanation_de") or "")

    r3 = client.post(
        "/llm/analyst/strategy_signal_explain",
        json={"signal_context_json": {"signal_id": "sig-1", "symbol": "BTCUSDT"}},
    )
    assert r3.status_code == 200, r3.text
    payload3 = r3.json()
    assert payload3["provider"] == "fake"
    assert payload3["provenance"]["task_type"] == "strategy_signal_explain"
    rs = payload3["result"]
    assert rs["execution_authority"] == "none"
    assert "[TEST-PROVIDER" in (rs.get("strategy_explanation_de") or "")
    ca = rs.get("chart_annotations")
    assert isinstance(ca, dict)
    assert ca.get("schema_version") == "1.0"
    assert isinstance(ca.get("chart_notes_de"), list)
    assert len(ca["chart_notes_de"]) >= 1
