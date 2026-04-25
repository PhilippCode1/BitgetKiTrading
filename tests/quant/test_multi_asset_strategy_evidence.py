from __future__ import annotations

from shared_py.multi_asset_strategy_evidence import (
    MultiAssetStrategyEvidence,
    evaluate_multi_asset_strategy_evidence,
)


def _base(**overrides: object) -> MultiAssetStrategyEvidence:
    data: dict[str, object] = {
        "strategy_id": "strat-x",
        "strategy_version": "1.0.0",
        "asset_symbol": "BTCUSDT",
        "asset_class": "major_high_liquidity",
        "market_family": "futures",
        "regime": "trend",
        "backtest_ok": True,
        "walk_forward_ok": True,
        "out_of_sample_ok": True,
        "paper_ok": True,
        "shadow_ok": True,
        "slippage_fees_funding_ok": True,
        "drawdown_ok": True,
        "regime_breakdown_ok": True,
        "asset_class_breakdown_ok": True,
        "trade_count": 120,
        "no_trade_quality_ok": True,
        "data_quality_ok": True,
        "liquidity_execution_evidence_ok": True,
        "expectancy_after_costs": 0.11,
        "max_drawdown_pct": 0.12,
        "live_requested": True,
    }
    data.update(overrides)
    return MultiAssetStrategyEvidence(**data)


def test_major_high_liquidity_with_full_evidence_pass() -> None:
    verdict, reasons, _ = evaluate_multi_asset_strategy_evidence(_base())
    assert verdict == "PASS"
    assert reasons == []


def test_without_walk_forward_fail() -> None:
    verdict, reasons, _ = evaluate_multi_asset_strategy_evidence(_base(walk_forward_ok=False))
    assert verdict == "FAIL"
    assert any("Walk-forward" in r for r in reasons)


def test_without_slippage_fees_fail() -> None:
    verdict, reasons, _ = evaluate_multi_asset_strategy_evidence(_base(slippage_fees_funding_ok=False))
    assert verdict == "FAIL"
    assert any("Slippage/Fees/Funding" in r for r in reasons)


def test_low_liquidity_without_execution_evidence_fail() -> None:
    verdict, reasons, _ = evaluate_multi_asset_strategy_evidence(
        _base(asset_class="low_liquidity", liquidity_execution_evidence_ok=False)
    )
    assert verdict == "FAIL"
    assert any("Low-liquidity" in r for r in reasons)


def test_new_listing_is_quarantine_fail() -> None:
    verdict, reasons, _ = evaluate_multi_asset_strategy_evidence(_base(asset_class="new_listing"))
    assert verdict == "FAIL"
    assert any("gesperrt" in r for r in reasons)


def test_negative_expectancy_fail() -> None:
    verdict, reasons, _ = evaluate_multi_asset_strategy_evidence(_base(expectancy_after_costs=-0.01))
    assert verdict == "FAIL"
    assert any("Expectancy" in r for r in reasons)


def test_high_drawdown_fail() -> None:
    verdict, reasons, _ = evaluate_multi_asset_strategy_evidence(_base(drawdown_ok=False, max_drawdown_pct=0.31))
    assert verdict == "FAIL"
    assert any("Drawdown" in r for r in reasons)


def test_low_trade_count_warn_or_fail() -> None:
    verdict, reasons, _ = evaluate_multi_asset_strategy_evidence(_base(trade_count=40))
    assert verdict in {"PASS_WITH_WARNINGS", "FAIL"}
    assert any("Trades" in r for r in reasons)


def test_backtest_only_not_live() -> None:
    verdict, reasons, _ = evaluate_multi_asset_strategy_evidence(
        _base(
            backtest_ok=True,
            walk_forward_ok=False,
            out_of_sample_ok=False,
            paper_ok=False,
            shadow_ok=False,
            trade_count=15,
        )
    )
    assert verdict == "FAIL"
    assert any("reicht nicht für Live" in r for r in reasons)


def test_report_text_contains_german_reason() -> None:
    verdict, reasons, text = evaluate_multi_asset_strategy_evidence(_base(walk_forward_ok=False))
    assert verdict == "FAIL"
    assert "Strategie" in text and ("fuer" in text or "f\u00fcr" in text)
    assert len(reasons) > 0
