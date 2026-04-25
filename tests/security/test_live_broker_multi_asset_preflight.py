from __future__ import annotations

from shared_py.live_preflight import LivePreflightContext, build_live_preflight_reasons_de, evaluate_live_preflight


def _ctx(**overrides: object) -> LivePreflightContext:
    payload = {
        "execution_mode_live": True,
        "live_trade_enable": True,
        "owner_approved": True,
        "asset_in_catalog": True,
        "asset_status_ok": True,
        "asset_live_allowed": True,
        "instrument_contract_complete": True,
        "instrument_metadata_fresh": True,
        "data_quality_status": "pass",
        "liquidity_status": "pass",
        "slippage_ok": True,
        "risk_tier_live_allowed": True,
        "order_sizing_ok": True,
        "portfolio_risk_ok": True,
        "strategy_evidence_ok": True,
        "bitget_readiness_ok": True,
        "reconcile_ok": True,
        "kill_switch_active": False,
        "safety_latch_active": False,
        "unknown_order_state": False,
        "account_snapshot_fresh": True,
        "idempotency_key": "idem-123",
        "audit_context_present": True,
        "warning_policy_allows_live": {},
    }
    payload.update(overrides)
    return LivePreflightContext(**payload)  # type: ignore[arg-type]


def test_asset_missing_blocks() -> None:
    d = evaluate_live_preflight(_ctx(asset_in_catalog=False))
    assert "asset_not_in_catalog" in d.blocking_reasons


def test_asset_not_live_allowed_blocks() -> None:
    d = evaluate_live_preflight(_ctx(asset_live_allowed=False))
    assert "asset_not_live_allowed" in d.blocking_reasons


def test_instrument_contract_missing_blocks() -> None:
    d = evaluate_live_preflight(_ctx(instrument_contract_complete=False))
    assert "instrument_contract_missing" in d.blocking_reasons


def test_data_quality_fail_blocks() -> None:
    d = evaluate_live_preflight(_ctx(data_quality_status="fail"))
    assert "data_quality_not_pass" in d.blocking_reasons


def test_liquidity_fail_blocks() -> None:
    d = evaluate_live_preflight(_ctx(liquidity_status="fail"))
    assert "liquidity_not_pass" in d.blocking_reasons


def test_risk_tier_blocks() -> None:
    d = evaluate_live_preflight(_ctx(risk_tier_live_allowed=False))
    assert "risk_tier_not_live_allowed" in d.blocking_reasons


def test_strategy_evidence_missing_blocks() -> None:
    d = evaluate_live_preflight(_ctx(strategy_evidence_ok=False))
    assert "strategy_evidence_missing_or_invalid" in d.blocking_reasons


def test_portfolio_risk_fail_blocks() -> None:
    d = evaluate_live_preflight(_ctx(portfolio_risk_ok=False))
    assert "portfolio_risk_not_safe" in d.blocking_reasons


def test_reconcile_fail_blocks() -> None:
    d = evaluate_live_preflight(_ctx(reconcile_ok=False))
    assert "reconcile_not_ok" in d.blocking_reasons


def test_kill_switch_active_blocks() -> None:
    d = evaluate_live_preflight(_ctx(kill_switch_active=True))
    assert "kill_switch_active" in d.blocking_reasons


def test_safety_latch_active_blocks() -> None:
    d = evaluate_live_preflight(_ctx(safety_latch_active=True))
    assert "safety_latch_active" in d.blocking_reasons


def test_unknown_order_state_blocks() -> None:
    d = evaluate_live_preflight(_ctx(unknown_order_state=True))
    assert "unknown_order_state_active" in d.blocking_reasons


def test_missing_idempotency_blocks() -> None:
    d = evaluate_live_preflight(_ctx(idempotency_key=None))
    assert "idempotency_key_missing" in d.blocking_reasons


def test_all_green_passes_without_real_submit() -> None:
    d = evaluate_live_preflight(_ctx())
    assert d.passed is True
    assert d.submit_allowed is True
    assert len(d.blocking_reasons) == 0


def test_german_reasons_generated() -> None:
    d = evaluate_live_preflight(_ctx(asset_in_catalog=False))
    reasons = build_live_preflight_reasons_de(d)
    assert any("Asset ist nicht im Katalog" in item for item in reasons)
