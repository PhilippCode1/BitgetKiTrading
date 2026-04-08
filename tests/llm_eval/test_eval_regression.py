from __future__ import annotations

from fastapi.testclient import TestClient


def test_operator_explain_fake_passes_guardrails(client: TestClient) -> None:
    r = client.post(
        "/llm/analyst/operator_explain",
        json={"question_de": "Was bedeutet Live-Gate?", "readonly_context_json": {}},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["ok"] is True
    prov = payload["provenance"]
    assert prov.get("prompt_manifest_version")
    assert prov.get("guardrails_version")
    assert prov.get("prompt_task_version")
    assert prov.get("global_system_prompt_version")


def test_strategy_signal_explain_fake_passes_guardrails(client: TestClient) -> None:
    r = client.post(
        "/llm/analyst/strategy_signal_explain",
        json={"signal_context_json": {"signal_id": "eval-1", "symbol": "BTCUSDT"}},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["ok"] is True
    assert payload["provenance"].get("prompt_manifest_version")


def test_governance_summary_endpoint(client: TestClient) -> None:
    r = client.get("/llm/governance/summary")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True
    assert data.get("tasks")
    assert any(t.get("task_id") == "operator_explain" for t in data["tasks"])
    assert data.get("system_prompt", {}).get("global_version")
    er = data.get("eval_regression") or {}
    assert er.get("release_gate") is True
    assert er.get("case_count", 0) >= 9
