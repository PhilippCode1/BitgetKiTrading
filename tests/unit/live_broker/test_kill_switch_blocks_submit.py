from __future__ import annotations

from dataclasses import replace

from shared_py.live_preflight import LivePreflightContext, evaluate_live_preflight


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
        idempotency_key="idem",
        audit_context_present=True,
    )


def test_kill_switch_blocks_submit() -> None:
    decision = evaluate_live_preflight(replace(_ctx(), kill_switch_active=True))
    assert decision.submit_allowed is False
    assert "kill_switch_active" in decision.blocking_reasons
