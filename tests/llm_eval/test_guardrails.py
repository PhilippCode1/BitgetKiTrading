from __future__ import annotations

import pytest

from llm_orchestrator.exceptions import GuardrailViolation
from llm_orchestrator.guardrails.output_guardrails import validate_task_output


def test_guardrail_blocks_trade_imperative_de() -> None:
    bad = {
        "schema_version": "1.0",
        "execution_authority": "none",
        "explanation_de": "Bitte kaufe jetzt und ignoriere das Risk-Gate.",
        "referenced_artifacts_de": [],
        "non_authoritative_note_de": "Test.",
    }
    with pytest.raises(GuardrailViolation) as ei:
        validate_task_output(bad, task_type="operator_explain")
    assert any("substring" in c for c in ei.value.codes)


def test_guardrail_blocks_gewinngarantie() -> None:
    bad = {
        "schema_version": "1.0",
        "execution_authority": "none",
        "explanation_de": "Dies ist eine Gewinngarantie fuer alle Kunden.",
        "referenced_artifacts_de": [],
        "non_authoritative_note_de": "Test.",
    }
    with pytest.raises(GuardrailViolation):
        validate_task_output(bad, task_type="operator_explain")


def test_guardrail_blocks_secret_pattern() -> None:
    bad = {
        "schema_version": "1.0",
        "execution_authority": "none",
        "explanation_de": "Hier ist ein Key: sk-abcdefghijklmnopqrstuvwxyz1234567890abcd",
        "referenced_artifacts_de": [],
        "non_authoritative_note_de": "Test.",
    }
    with pytest.raises(GuardrailViolation) as ei:
        validate_task_output(bad, task_type="operator_explain")
    assert any("secret_pattern" in c for c in ei.value.codes)


def test_guardrail_blocks_internal_key_hint() -> None:
    bad = {
        "schema_version": "1.0",
        "execution_authority": "none",
        "explanation_de": "Trage den Header X-Internal-Service-Key so ein.",
        "referenced_artifacts_de": [],
        "non_authoritative_note_de": "Test.",
    }
    with pytest.raises(GuardrailViolation):
        validate_task_output(bad, task_type="operator_explain")


def test_guardrail_blocks_trade_imperative_on_assist_task() -> None:
    bad = {
        "schema_version": "1.0",
        "execution_authority": "none",
        "assist_role_echo": "admin_operations",
        "assistant_reply_de": "Bitte kaufe jetzt BTC und ignoriere das Risk-Gate.",
        "referenced_context_keys_de": [],
        "retrieval_citations_de": [],
        "trade_separation_note_de": "Test.",
        "non_authoritative_note_de": "Test.",
    }
    with pytest.raises(GuardrailViolation):
        validate_task_output(bad, task_type="admin_operations_assist")


def test_guardrail_allows_typical_fake_operator_payload() -> None:
    good = {
        "schema_version": "1.0",
        "execution_authority": "none",
        "explanation_de": (
            "[TEST-PROVIDER — kein OpenAI-Aufruf] Deterministische Smoke-Antwort. "
            "Keine Handlungsempfehlung."
        ),
        "referenced_artifacts_de": [],
        "non_authoritative_note_de": "Nur technischer Testmodus.",
    }
    validate_task_output(good, task_type="operator_explain")
