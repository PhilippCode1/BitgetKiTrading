from __future__ import annotations

from shared_py.bitget.instruments import (
    BitgetAssetUniverseInstrument,
    evaluate_asset_universe_live_eligibility,
)


def _base_instrument(**overrides: object) -> BitgetAssetUniverseInstrument:
    payload: dict[str, object] = {
        "symbol": "ETHUSDT",
        "base_coin": "ETH",
        "quote_coin": "USDT",
        "market_family": "futures",
        "product_type": "USDT-FUTURES",
        "margin_coin": "USDT",
        "margin_mode": "isolated",
        "tick_size": "0.1",
        "lot_size": "0.001",
        "min_qty": "0.001",
        "min_notional": "5",
        "price_precision": 1,
        "quantity_precision": 3,
        "status": "live_candidate",
        "asset_tier": 1,
        "is_tradable": True,
        "is_chart_visible": True,
        "data_quality_ok": True,
        "liquidity_ok": True,
        "risk_tier_assigned": True,
        "strategy_evidence_ready": True,
        "owner_approved": True,
        "source": "catalog",
    }
    payload.update(overrides)
    return BitgetAssetUniverseInstrument.model_validate(payload)


def _evaluate(**overrides: object) -> BitgetAssetUniverseInstrument:
    return evaluate_asset_universe_live_eligibility(_base_instrument(**overrides))


def test_unknown_asset_blocks_live() -> None:
    out = _evaluate(status="unknown")
    assert out.is_live_allowed is False
    assert "status_unknown" in out.block_reasons


def test_delisted_asset_blocks_live() -> None:
    out = _evaluate(status="delisted")
    assert out.is_live_allowed is False
    assert "status_delisted" in out.block_reasons


def test_suspended_asset_blocks_live() -> None:
    out = _evaluate(status="suspended")
    assert out.is_live_allowed is False
    assert "status_suspended" in out.block_reasons


def test_futures_without_product_type_blocks() -> None:
    out = _evaluate(product_type=None)
    assert out.is_live_allowed is False
    assert "missing_product_type_for_futures" in out.block_reasons


def test_futures_without_margin_coin_blocks() -> None:
    out = _evaluate(margin_coin=None)
    assert out.is_live_allowed is False
    assert "missing_margin_coin_for_futures" in out.block_reasons


def test_missing_precision_blocks() -> None:
    out = _evaluate(price_precision=None)
    assert out.is_live_allowed is False
    assert "missing_precision" in out.block_reasons


def test_missing_min_qty_blocks_live() -> None:
    out = _evaluate(min_qty=None)
    assert out.is_live_allowed is False
    assert "missing_min_qty" in out.block_reasons


def test_tier_0_blocks_live() -> None:
    out = _evaluate(asset_tier=0)
    assert out.is_live_allowed is False
    assert "tier_0_blocked" in out.block_reasons


def test_tier_4_not_automatically_live_eligible() -> None:
    out = _evaluate(asset_tier=4, status="live_candidate")
    assert out.is_live_allowed is False
    assert "tier_4_shadow_only" in out.block_reasons


def test_tier_4_shadow_allowed_still_blocks_live() -> None:
    out = _evaluate(asset_tier=4, status="shadow_allowed")
    assert out.is_live_allowed is False
    assert "tier_4_shadow_only" in out.block_reasons


def test_tier_1_requires_live_candidate_status_and_other_gates() -> None:
    out = _evaluate(asset_tier=1, status="active")
    assert out.is_live_allowed is False
    assert "tier_1_requires_live_candidate_status" in out.block_reasons


def test_live_allowed_requires_empty_block_reasons() -> None:
    out = _evaluate(block_reasons=["manual_block"])
    assert out.is_live_allowed is False
    assert "manual_block" in out.block_reasons


def test_no_silent_btcusdt_default_release() -> None:
    out = _evaluate(symbol="BTCUSDT", status="unknown")
    assert out.is_live_allowed is False
    assert "status_unknown" in out.block_reasons
