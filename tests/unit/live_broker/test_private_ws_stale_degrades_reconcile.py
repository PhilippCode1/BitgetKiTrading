from __future__ import annotations

from shared_py.reconcile_truth import ReconcileTruthContext, evaluate_reconcile_truth


def test_private_ws_stale_degrades_reconcile() -> None:
    decision = evaluate_reconcile_truth(
        ReconcileTruthContext(
            global_status="stale",
            per_asset_status={"BTCUSDT": "stale"},
            reconcile_fresh=False,
            exchange_reachable=True,
            auth_ok=True,
            unknown_order_state=False,
            position_mismatch=False,
            fill_mismatch=False,
            exchange_order_missing=False,
            local_order_missing=False,
            safety_latch_active=False,
        )
    )
    assert decision.status == "blocked"
    assert "reconcile_stale" in decision.blocking_reasons
