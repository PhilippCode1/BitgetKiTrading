from __future__ import annotations

from shared_py.live_preflight import LivePreflightContext, evaluate_live_preflight


def test_live_preflight_blocks_submit_on_risk_fail() -> None:
    decision = evaluate_live_preflight(
        LivePreflightContext(
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
            risk_tier_live_allowed=False,
            order_sizing_ok=False,
            portfolio_risk_ok=False,
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
    )
    assert decision.submit_allowed is False
    assert "risk_tier_not_live_allowed" in decision.blocking_reasons
    assert "order_sizing_not_safe" in decision.blocking_reasons
    assert "portfolio_risk_not_safe" in decision.blocking_reasons
