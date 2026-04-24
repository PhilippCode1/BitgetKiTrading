from __future__ import annotations

from shared_py.observability.risk_rejection_inquiry import (
    REJECTED_BY_RISK,
    build_ops_risk_assist_context,
    build_risk_rejection_inquiry,
    is_rejected_by_risk,
)
from shared_py.observability.vpin_redis import VPIN_HARD_HALT_THRESHOLD_0_1


def _minimal_timeline(*, vpin: float) -> dict:
    return {
        "execution_id": "00000000-0000-4000-8000-000000000001",
        "decision": {
            "decision_action": "blocked",
            "decision_reason": "shared_risk_blocked",
        },
        "signal_context": {},
        "correlation": {"execution_id": "00000000-0000-4000-8000-000000000001"},
        "risk_snapshot": {
            "trade_action": "do_not_trade",
            "decision_state": "rejected",
            "primary_reason": "RISK_VPIN_HALT",
            "reasons_json": ["vpin_toxicity"],
            "detail_json": {
                "decision_reason": "RISK_VPIN_HALT",
                "limits": {
                    "max_account_margin_usage": 0.35,
                },
            },
            "metrics_json": {
                "vpin_toxicity_0_1": vpin,
                "projected_margin_usage_pct": 0.2,
            },
        },
    }


def test_rejected_by_risk_and_vpin_policy_hit() -> None:
    tl = _minimal_timeline(vpin=0.9)
    assert is_rejected_by_risk(tl) is True
    inq = build_risk_rejection_inquiry(tl)
    assert inq["rejection_code"] == REJECTED_BY_RISK
    hits = inq.get("policy_hits_de") or []
    joined = " ".join(hits)
    assert "0.90" in joined
    assert str(VPIN_HARD_HALT_THRESHOLD_0_1) in joined or "0.85" in joined


def test_ops_risk_assist_has_golden_and_inquiry_keys() -> None:
    ctx = build_ops_risk_assist_context(_minimal_timeline(vpin=0.88))
    assert "trade_lifecycle_golden" in ctx
    assert "risk_rejection_inquiry" in ctx
    assert ctx["risk_rejection_inquiry"].get("rejection_code") == REJECTED_BY_RISK
