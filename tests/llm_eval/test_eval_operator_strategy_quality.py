from __future__ import annotations

from fastapi.testclient import TestClient


def test_operator_explain_fake_marked_and_non_empty(client: TestClient) -> None:
    r = client.post(
        "/llm/analyst/operator_explain",
        json={
            "question_de": "Was bedeutet Live-Gate?",
            "readonly_context_json": {},
        },
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["ok"] is True
    res = payload["result"]
    exp = str(res.get("explanation_de") or "")
    note = str(res.get("non_authoritative_note_de") or "")
    assert len(exp.strip()) >= 40
    assert len(note.strip()) >= 10
    assert "TEST-PROVIDER" in exp
    assert res.get("execution_authority") == "none"
    assert isinstance(res.get("referenced_artifacts_de"), list)


def test_strategy_signal_explain_risk_section_non_empty(client: TestClient) -> None:
    r = client.post(
        "/llm/analyst/strategy_signal_explain",
        json={"signal_context_json": {"signal_id": "eval-q", "symbol": "ETHUSDT"}},
    )
    assert r.status_code == 200, r.text
    res = r.json()["result"]
    risk = str(res.get("risk_and_caveats_de") or "")
    assert len(risk.strip()) >= 15
    keys = res.get("referenced_input_keys_de")
    assert isinstance(keys, list)
