from __future__ import annotations

from fastapi.testclient import TestClient


def test_safety_incident_diagnosis_fake_schema(client: TestClient) -> None:
    r = client.post(
        "/llm/analyst/safety_incident_diagnosis",
        json={
            "question_de": "Was ist der wahrscheinlichste Engpass laut Health-Snapshot?",
            "diagnostic_context_json": {
                "context_kind": "test",
                "system_health": {"database": "error"},
                "monitor_open_alerts": [],
            },
        },
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["ok"] is True
    assert payload["provenance"].get("task_type") == "safety_incident_diagnosis"
    res = payload["result"]
    assert res.get("execution_authority") == "none"
    assert "TEST-PROVIDER" in str(res.get("incident_summary_de") or "")
    assert isinstance(res.get("root_causes_de"), list)
    assert isinstance(res.get("proposed_commands_de"), list)
