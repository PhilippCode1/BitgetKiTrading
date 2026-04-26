from __future__ import annotations

from shared_py.bitget.asset_governance import AssetGovernanceRecord, evaluate_trade_decision
from shared_py.bitget.instruments import BitgetAssetUniverseInstrument, evaluate_asset_universe_live_eligibility


def _instrument(**overrides: object) -> BitgetAssetUniverseInstrument:
    payload: dict[str, object] = {
        "symbol": "BTCUSDT",
        "base_coin": "BTC",
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
    payload.update(overrides)
    return BitgetAssetUniverseInstrument.model_validate(payload)


def test_missing_tick_size_blocks_trade() -> None:
    evaluated = evaluate_asset_universe_live_eligibility(_instrument(tick_size=None))
    assert evaluated.is_live_allowed is False


def test_missing_lot_size_blocks_trade() -> None:
    evaluated = evaluate_asset_universe_live_eligibility(_instrument(lot_size=None))
    assert evaluated.is_live_allowed is False


def test_missing_price_and_quantity_precision_block_trade() -> None:
    evaluated = evaluate_asset_universe_live_eligibility(
        _instrument(price_precision=None, quantity_precision=None)
    )
    assert evaluated.is_live_allowed is False
    assert "missing_precision" in evaluated.block_reasons


def test_delisted_and_quarantined_block_trade() -> None:
    delisted = evaluate_asset_universe_live_eligibility(_instrument(status="delisted"))
    quarantined = evaluate_asset_universe_live_eligibility(_instrument(status="quarantined"))
    assert delisted.is_live_allowed is False
    assert quarantined.is_live_allowed is False


def test_machine_readable_governance_decision_is_no_trade_on_missing_evidence() -> None:
    record = AssetGovernanceRecord.model_validate(
        {
            "asset_id": "ASSET-BTCUSDT",
            "symbol": "BTCUSDT",
            "market_family": "futures",
            "product_type": "USDT-FUTURES",
            "state": "live_candidate",
            "actor": "system",
            "reason_de": "",
            "evidence_refs": [],
            "created_at": "2026-04-26T10:00:00Z",
            "data_quality_status": "data_unknown",
            "liquidity_ok": False,
            "strategy_evidence_ready": False,
            "bitget_status_clear": False,
        }
    )
    decision = evaluate_trade_decision(record)
    assert decision.allowed is False
    assert decision.decision == "no_trade"
    assert decision.severity == "P0"
