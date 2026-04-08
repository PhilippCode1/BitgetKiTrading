from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_reports_fake_mode_for_eval_regression_client(
    client: TestClient,
) -> None:
    """Reproduzierbare Baseline: Eval-Client erzwingt LLM_USE_FAKE_PROVIDER=true."""
    r = client.get("/health")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("fake_mode") is True
