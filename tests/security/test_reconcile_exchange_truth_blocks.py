from __future__ import annotations

from shared_py.reconcile_truth import (
    ReconcileTruthContext,
    build_reconcile_drift_reasons_de,
    evaluate_reconcile_truth,
    reconcile_requires_safety_latch,
    reconcile_truth_blocks_live,
)


def _ctx(**overrides: object) -> ReconcileTruthContext:
    base = {
        "global_status": "ok",
        "per_asset_status": {"BTCUSDT": "ok"},
        "reconcile_fresh": True,
        "exchange_reachable": True,
        "auth_ok": True,
        "unknown_order_state": False,
        "position_mismatch": False,
        "fill_mismatch": False,
        "exchange_order_missing": False,
        "local_order_missing": False,
        "safety_latch_active": False,
    }
    base.update(overrides)
    return ReconcileTruthContext(**base)  # type: ignore[arg-type]


def test_stale_blocks() -> None:
    d = evaluate_reconcile_truth(_ctx(reconcile_fresh=False, global_status="stale"))
    assert reconcile_truth_blocks_live(d) is True


def test_exchange_unreachable_blocks() -> None:
    d = evaluate_reconcile_truth(_ctx(exchange_reachable=False, global_status="exchange_unreachable"))
    assert "exchange_unreachable" in d.blocking_reasons


def test_auth_failed_blocks() -> None:
    d = evaluate_reconcile_truth(_ctx(auth_ok=False, global_status="auth_failed"))
    assert "auth_failed" in d.blocking_reasons


def test_unknown_order_state_blocks() -> None:
    d = evaluate_reconcile_truth(_ctx(unknown_order_state=True, global_status="unknown_order_state"))
    assert "unknown_order_state" in d.blocking_reasons


def test_position_mismatch_blocks() -> None:
    d = evaluate_reconcile_truth(_ctx(position_mismatch=True, global_status="position_mismatch"))
    assert "position_mismatch" in d.blocking_reasons


def test_fill_mismatch_requires_safety_latch_or_block() -> None:
    d = evaluate_reconcile_truth(_ctx(fill_mismatch=True, global_status="fill_mismatch"))
    assert reconcile_requires_safety_latch(d) is True


def test_exchange_order_missing_requires_reconcile() -> None:
    d = evaluate_reconcile_truth(_ctx(exchange_order_missing=True, global_status="exchange_order_missing"))
    assert d.reconcile_required is True


def test_local_order_missing_requires_reconcile() -> None:
    d = evaluate_reconcile_truth(_ctx(local_order_missing=True, global_status="local_order_missing"))
    assert d.reconcile_required is True


def test_ok_allows_next_gate_only() -> None:
    d = evaluate_reconcile_truth(_ctx())
    assert d.allows_next_gate_only is True
    assert d.status == "ok"


def test_german_drift_reasons() -> None:
    d = evaluate_reconcile_truth(_ctx(position_mismatch=True, global_status="position_mismatch"))
    reasons = build_reconcile_drift_reasons_de(d)
    assert any("Positionsabweichung" in r for r in reasons)
