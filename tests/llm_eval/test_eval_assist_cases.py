from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def test_admin_operations_assist_eval(client: TestClient) -> None:
    conv = str(uuid.uuid4())
    r = client.post(
        "/llm/assist/turn",
        json={
            "assist_role": "admin_operations",
            "conversation_id": conv,
            "tenant_partition_id": "eval-tenant-admin",
            "user_message_de": "Was prüft das Live-Gate in einem Satz?",
            "context_json": {},
        },
    )
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["ok"] is True
    assert p["provenance"]["task_type"] == "admin_operations_assist"
    assert p["provenance"].get("global_system_prompt_version")
    res = p["result"]
    assert res.get("execution_authority") == "none"
    assert res.get("assist_role_echo") == "admin_operations"
    reply = str(res.get("assistant_reply_de") or "")
    assert len(reply.strip()) >= 20
    assert "TEST-PROVIDER" in reply


def test_customer_onboarding_assist_eval(client: TestClient) -> None:
    conv = str(uuid.uuid4())
    r = client.post(
        "/llm/assist/turn",
        json={
            "assist_role": "customer_onboarding",
            "conversation_id": conv,
            "tenant_partition_id": "eval-tenant",
            "user_message_de": "Wie starte ich mit dem Onboarding?",
            "context_json": {"tenant_profile": {"display_name": "Eval"}},
        },
    )
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["provenance"]["task_type"] == "customer_onboarding_assist"
    assert p["provenance"].get("global_system_prompt_version")
    res = p["result"]
    assert res.get("execution_authority") == "none"
    assert res.get("assist_role_echo") == "customer_onboarding"
    assert "TEST-PROVIDER" in str(res.get("assistant_reply_de") or "")


def test_support_billing_assist_eval(client: TestClient) -> None:
    conv = str(uuid.uuid4())
    r = client.post(
        "/llm/assist/turn",
        json={
            "assist_role": "support_billing",
            "conversation_id": conv,
            "tenant_partition_id": "eval-tenant-b",
            "user_message_de": "Was bedeutet mein aktueller Plan?",
            "context_json": {
                "plan_snapshot": {"name": "trial"},
                "usage_month": {"ledger_total_list_usd": "0"},
            },
        },
    )
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["provenance"]["task_type"] == "support_billing_assist"
    res = p["result"]
    assert res.get("execution_authority") == "none"
    assert res.get("trade_separation_note_de")
    assert "TEST-PROVIDER" in str(res.get("assistant_reply_de") or "")


def test_trial_contract_context_eval(client: TestClient) -> None:
    conv = str(uuid.uuid4())
    r = client.post(
        "/llm/assist/turn",
        json={
            "assist_role": "customer_onboarding",
            "conversation_id": conv,
            "tenant_partition_id": "eval-trial",
            "user_message_de": "Wie lange laeuft mein Testzeitraum laut System?",
            "context_json": {
                "trial_status": {"phase": "trial", "days_remaining_hint": 14},
            },
        },
    )
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["ok"] is True
    res = p["result"]
    assert isinstance(res, dict)
    reply = str(res.get("assistant_reply_de") or "")
    assert len(reply) >= 20
    assert res.get("execution_authority") == "none"
    assert "TEST-PROVIDER" in reply
