from __future__ import annotations

from fastapi.testclient import TestClient


def test_strategy_signal_explain_chart_annotations_fake_schema(
    client: TestClient,
) -> None:
    """Orchestrator liefert chart_annotations mit schema_version 1.0 (Fake-Provider)."""
    r = client.post(
        "/llm/analyst/strategy_signal_explain",
        json={
            "signal_context_json": {
                "signal_id": "eval-chart-1",
                "symbol": "BTCUSDT",
            },
        },
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["ok"] is True
    res = payload["result"]
    assert isinstance(res, dict)
    assert res.get("execution_authority") == "none"
    strat = str(res.get("strategy_explanation_de") or "")
    assert len(strat.strip()) >= 40
    assert "TEST-PROVIDER" in strat

    ca = res.get("chart_annotations")
    assert isinstance(ca, dict)
    assert ca.get("schema_version") == "1.0"
    notes = ca.get("chart_notes_de")
    assert isinstance(notes, list) and len(notes) >= 1
    first = notes[0]
    assert isinstance(first, dict)
    tx = str(first.get("text") or "")
    assert len(tx.strip()) >= 10
    assert "TEST-PROVIDER" in tx
