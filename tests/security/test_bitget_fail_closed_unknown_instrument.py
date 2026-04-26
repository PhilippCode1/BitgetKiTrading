from __future__ import annotations

from shared_py.bitget.instruments import BitgetAssetUniverseInstrument, evaluate_asset_universe_live_eligibility
from shared_py.live_preflight import LivePreflightContext, evaluate_live_preflight


def _base() -> BitgetAssetUniverseInstrument:
    return BitgetAssetUniverseInstrument.model_validate(
        {
            "symbol": "ETHUSDT",
            "base_coin": "ETH",
            "quote_coin": "USDT",
            "market_family": "futures",
            "product_type": "USDT-FUTURES",
            "margin_coin": "USDT",
            "tick_size": "0.1",
            "lot_size": "0.001",
            "min_qty": "0.001",
            "min_notional": "5",
            "price_precision": 1,
            "quantity_precision": 3,
            "status": "live_candidate",
            "asset_tier": 1,
            "data_quality_ok": True,
            "liquidity_ok": True,
            "risk_tier_assigned": True,
            "strategy_evidence_ready": True,
            "owner_approved": True,
        }
    )


def test_unknown_instrument_is_no_trade() -> None:
    evaluated = evaluate_asset_universe_live_eligibility(_base().model_copy(update={"status": "unknown"}))
    assert evaluated.is_live_allowed is False
    assert "status_unknown" in evaluated.block_reasons


def test_stale_metadata_blocks_live_context() -> None:
    decision = evaluate_live_preflight(
        LivePreflightContext(
            execution_mode_live=True,
            live_trade_enable=True,
            owner_approved=True,
            asset_in_catalog=True,
            asset_status_ok=True,
            asset_live_allowed=True,
            instrument_contract_complete=True,
            instrument_metadata_fresh=False,
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
            checked_at="test",
        )
    )
    assert decision.submit_allowed is False
    assert "instrument_metadata_stale" in decision.blocking_reasons
