"""Deterministische Governance fuer KI-Strategie-Entwuerfe."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api_gateway.ai_strategy_proposal_governance import (
    normalize_proposal_payload,
    run_deterministic_validation,
)
from api_gateway.ai_strategy_proposal_governance import assert_promotion_allowed


def _valid_result() -> dict:
    return {
        "schema_version": "1.0",
        "execution_authority": "none",
        "strategy_explanation_de": "x",
        "scenario_variants_de": ["a"],
        "parameter_ideas_de": [],
        "validity_and_assumptions_de": "y",
        "risk_and_caveats_de": "z",
        "referenced_input_keys_de": [],
        "non_authoritative_note_de": "n",
        "promotion_disclaimer_de": "Kein Orderauftrag; nur Entwurf.",
        "suggested_execution_lane_hint": "paper_sandbox",
    }


def test_normalize_forces_execution_none() -> None:
    dirty = dict(_valid_result())
    dirty["execution_authority"] = "trade"
    out = normalize_proposal_payload(dirty)
    assert out["execution_authority"] == "none"


def test_validation_rejects_forbidden_keys() -> None:
    r = _valid_result()
    r["order_intent"] = {"side": "buy"}
    ok, rep = run_deterministic_validation(r)
    assert ok is False
    assert any(x.startswith("forbidden_key:") for x in rep["errors"])


def test_validation_passes_clean() -> None:
    ok, rep = run_deterministic_validation(_valid_result())
    assert ok is True
    assert rep["errors"] == []


def test_promotion_requires_human_ack() -> None:
    with pytest.raises(HTTPException) as ei:
        assert_promotion_allowed(
            lifecycle_status="validation_passed",
            human_acknowledged=False,
            promotion_target="paper_sandbox",
        )
    assert ei.value.status_code == 422


def test_promotion_requires_validation_status() -> None:
    with pytest.raises(HTTPException) as ei:
        assert_promotion_allowed(
            lifecycle_status="draft",
            human_acknowledged=True,
            promotion_target="paper_sandbox",
        )
    assert ei.value.status_code == 422


def test_promotion_ok_when_gates_met() -> None:
    assert_promotion_allowed(
        lifecycle_status="validation_passed",
        human_acknowledged=True,
        promotion_target="shadow_observe",
    )
