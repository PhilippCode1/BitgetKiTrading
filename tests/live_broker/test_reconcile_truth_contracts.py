from __future__ import annotations

from shared_py.reconcile_truth import ReconcileTruthContext, build_reconcile_audit_payload, evaluate_reconcile_truth


def _ctx() -> ReconcileTruthContext:
    return ReconcileTruthContext(
        global_status="ok",
        per_asset_status={"BTCUSDT": "ok", "ETHUSDT": "warning"},
        reconcile_fresh=True,
        exchange_reachable=True,
        auth_ok=True,
        unknown_order_state=False,
        position_mismatch=False,
        fill_mismatch=False,
        exchange_order_missing=False,
        local_order_missing=False,
        safety_latch_active=False,
    )


def test_warning_state_without_block_when_only_reconcile_required() -> None:
    ctx = ReconcileTruthContext(**{**_ctx().__dict__, "exchange_order_missing": True, "global_status": "exchange_order_missing"})
    d = evaluate_reconcile_truth(ctx)
    assert d.reconcile_required is True
    assert d.status == "warning"


def test_safety_latch_active_blocks() -> None:
    ctx = ReconcileTruthContext(**{**_ctx().__dict__, "safety_latch_active": True, "global_status": "safety_latch_required"})
    d = evaluate_reconcile_truth(ctx)
    assert d.status == "blocked"


def test_audit_payload_contains_per_asset_status() -> None:
    ctx = _ctx()
    d = evaluate_reconcile_truth(ctx)
    payload = build_reconcile_audit_payload(context=ctx, decision=d)
    assert "per_asset_status" in payload
