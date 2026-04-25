from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AssetClass = Literal[
    "major_high_liquidity",
    "large_liquidity",
    "mid_liquidity",
    "high_volatility",
    "low_liquidity",
    "new_listing",
    "delisting_risk",
    "blocked_unknown",
]

Verdict = Literal["PASS", "PASS_WITH_WARNINGS", "FAIL"]

ASSET_CLASSES: tuple[AssetClass, ...] = (
    "major_high_liquidity",
    "large_liquidity",
    "mid_liquidity",
    "high_volatility",
    "low_liquidity",
    "new_listing",
    "delisting_risk",
    "blocked_unknown",
)


@dataclass(frozen=True)
class MultiAssetStrategyEvidence:
    strategy_id: str
    strategy_version: str
    asset_symbol: str
    asset_class: AssetClass
    market_family: str
    regime: str
    backtest_ok: bool
    walk_forward_ok: bool
    out_of_sample_ok: bool
    paper_ok: bool
    shadow_ok: bool
    slippage_fees_funding_ok: bool
    drawdown_ok: bool
    regime_breakdown_ok: bool
    asset_class_breakdown_ok: bool
    trade_count: int
    no_trade_quality_ok: bool
    data_quality_ok: bool
    liquidity_execution_evidence_ok: bool
    expectancy_after_costs: float
    max_drawdown_pct: float
    live_requested: bool = False


def evaluate_multi_asset_strategy_evidence(item: MultiAssetStrategyEvidence) -> tuple[Verdict, list[str], str]:
    reasons: list[str] = []
    warnings: list[str] = []

    if item.asset_class in {"new_listing", "delisting_risk", "blocked_unknown"}:
        reasons.append("Asset-Klasse ist für Live gesperrt/quarantänepflichtig.")

    if not item.walk_forward_ok:
        reasons.append("Walk-forward-Evidence fehlt.")
    if not item.slippage_fees_funding_ok:
        reasons.append("Slippage/Fees/Funding-Evidence fehlt.")
    if not item.backtest_ok:
        reasons.append("Backtest-Evidence fehlt.")
    if not item.out_of_sample_ok:
        reasons.append("Out-of-sample-Evidence fehlt.")
    if not item.paper_ok:
        reasons.append("Paper-Evidence fehlt.")
    if not item.shadow_ok:
        reasons.append("Shadow-Burn-in-Evidence fehlt.")
    if not item.drawdown_ok:
        reasons.append("Drawdown-Regel verletzt.")
    if not item.regime_breakdown_ok:
        reasons.append("Regime-Breakdown unzureichend.")
    if not item.asset_class_breakdown_ok:
        reasons.append("Asset-Klassen-Breakdown unzureichend.")
    if not item.no_trade_quality_ok:
        reasons.append("No-Trade-Qualität unzureichend.")
    if not item.data_quality_ok:
        reasons.append("Datenqualität nicht ausreichend.")
    if item.asset_class == "low_liquidity" and not item.liquidity_execution_evidence_ok:
        reasons.append("Low-liquidity ohne Execution-Evidence bleibt live-blockiert.")
    if item.expectancy_after_costs <= 0:
        reasons.append("Negative oder null Expectancy nach Kosten.")
    if item.max_drawdown_pct > 0.20:
        reasons.append("Max-Drawdown über 20%.")

    if item.trade_count < 50:
        warnings.append("Zu wenige Trades für robuste Aussage.")
    if item.trade_count < 20:
        reasons.append("Extrem geringe Trade-Anzahl.")

    if item.live_requested and (not item.backtest_ok or not item.paper_ok):
        reasons.append("Backtest-only oder Paper-only reicht nicht für Live.")

    if reasons:
        verdict: Verdict = "FAIL"
    elif warnings:
        verdict = "PASS_WITH_WARNINGS"
    else:
        verdict = "PASS"

    details = reasons if reasons else warnings
    if not details:
        text = (
            f"Strategie {item.strategy_id} für {item.asset_symbol}/{item.asset_class}: "
            "Eignung ausreichend (PASS)."
        )
    else:
        text = (
            f"Strategie {item.strategy_id} für {item.asset_symbol}/{item.asset_class}: "
            + "; ".join(details)
        )
    return verdict, reasons + warnings, text
