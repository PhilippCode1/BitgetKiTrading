from __future__ import annotations

from shared_py.reconcile_truth import ReconcileTruthContext, evaluate_reconcile_truth


def test_position_drift_blocks_opening_orders() -> None:
    decision = evaluate_reconcile_truth(
        ReconcileTruthContext(
            global_status="position_mismatch",
            per_asset_status={"BTCUSDT": "position_mismatch"},
            reconcile_fresh=True,
            exchange_reachable=True,
            auth_ok=True,
            unknown_order_state=False,
            position_mismatch=True,
            fill_mismatch=False,
            exchange_order_missing=False,
            local_order_missing=False,
            safety_latch_active=False,
        )
    )
    assert decision.status == "blocked"
    assert "position_mismatch" in decision.blocking_reasons
