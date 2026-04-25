from __future__ import annotations

from shared_py.live_preflight import (
    LivePreflightContext,
    build_live_preflight_audit_payload,
    evaluate_live_preflight,
    live_preflight_blocks_submit,
)


def _ctx() -> LivePreflightContext:
    return LivePreflightContext(
        execution_mode_live=True,
        live_trade_enable=True,
        owner_approved=True,
        asset_in_catalog=True,
        asset_status_ok=True,
        asset_live_allowed=True,
        instrument_contract_complete=True,
        instrument_metadata_fresh=True,
        data_quality_status="pass",
        liquidity_status="pass",
        slippage_ok=True,
        risk_tier_live_allowed=True,
        order_sizing_ok=True,
        portfolio_risk_ok=True,
        strategy_evidence_ok=True,
        bitget_readiness_ok=True,
        reconcile_ok=True,
        kill_switch_active=False,
        safety_latch_active=False,
        unknown_order_state=False,
        account_snapshot_fresh=True,
        idempotency_key="idem-1",
        audit_context_present=True,
        warning_policy_allows_live={},
    )


def test_warning_blocks_by_default() -> None:
    ctx = _ctx()
    ctx = LivePreflightContext(**{**ctx.__dict__, "data_quality_status": "warn"})
    d = evaluate_live_preflight(ctx)
    assert live_preflight_blocks_submit(d) is True


def test_warning_can_be_explicitly_allowed() -> None:
    ctx = _ctx()
    ctx = LivePreflightContext(
        **{
            **ctx.__dict__,
            "data_quality_status": "warn",
            "warning_policy_allows_live": {"data_quality": True},
        }
    )
    d = evaluate_live_preflight(ctx)
    assert "data_quality" in d.warning_reasons
    assert "data_quality_not_pass" not in d.blocking_reasons


def test_audit_payload_contains_gate_snapshot() -> None:
    ctx = _ctx()
    d = evaluate_live_preflight(ctx)
    payload = build_live_preflight_audit_payload(context=ctx, decision=d)
    assert payload["passed"] is True
    assert "context_flags" in payload
