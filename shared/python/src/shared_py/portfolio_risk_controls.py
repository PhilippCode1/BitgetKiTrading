from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Side = Literal["long", "short"]


@dataclass(frozen=True)
class ExposureItem:
    symbol: str
    market_family: str
    notional: float
    risk_pct: float
    side: Side
    funding_rate_abs: float = 0.0
    basis_bps_abs: float = 0.0


@dataclass(frozen=True)
class PortfolioRiskLimits:
    max_total_notional: float
    max_margin_usage: float
    max_largest_position_risk: float
    max_concurrent_positions: int
    max_pending_orders: int
    max_pending_live_candidates: int
    max_net_directional_exposure: float
    max_correlation_stress: float
    max_funding_concentration: float
    max_family_exposure: float


@dataclass(frozen=True)
class PortfolioSnapshot:
    open_positions: list[ExposureItem]
    pending_orders: list[ExposureItem]
    pending_live_candidates: list[ExposureItem]
    account_equity: float
    used_margin: float
    snapshot_fresh: bool
    correlation_stress: float | None
    unknown_correlation: bool


@dataclass(frozen=True)
class PortfolioRiskResult:
    total_exposure: float
    margin_usage: float
    open_positions_count: int
    pending_orders_count: int
    pending_live_candidates_count: int
    net_long_exposure: float
    net_short_exposure: float
    family_exposure: dict[str, float]
    correlation_stress: float
    funding_concentration: float
    basis_risk: float
    largest_position_risk: float
    block_reasons: list[str]
    cap_reasons: list[str]
    allows_next_gate_only: bool


def validate_portfolio_risk_context(snapshot: PortfolioSnapshot | None) -> list[str]:
    reasons: list[str] = []
    if snapshot is None:
        reasons.append("portfolio_snapshot_fehlt")
        return reasons
    if not snapshot.snapshot_fresh:
        reasons.append("portfolio_snapshot_stale")
    if snapshot.account_equity <= 0:
        reasons.append("account_equity_ungueltig")
    return reasons


def compute_total_exposure(snapshot: PortfolioSnapshot) -> float:
    total = 0.0
    for item in snapshot.open_positions + snapshot.pending_orders + snapshot.pending_live_candidates:
        total += max(0.0, item.notional)
    return total


def compute_directional_exposure(snapshot: PortfolioSnapshot) -> tuple[float, float]:
    net_long = 0.0
    net_short = 0.0
    for item in snapshot.open_positions + snapshot.pending_orders + snapshot.pending_live_candidates:
        if item.side == "long":
            net_long += max(0.0, item.notional)
        else:
            net_short += max(0.0, item.notional)
    return net_long, net_short


def compute_family_exposure(snapshot: PortfolioSnapshot) -> dict[str, float]:
    out: dict[str, float] = {}
    for item in snapshot.open_positions + snapshot.pending_orders + snapshot.pending_live_candidates:
        key = item.market_family.lower()
        out[key] = out.get(key, 0.0) + max(0.0, item.notional)
    return out


def apply_correlation_stress_cap(*, correlation_stress: float | None, unknown_correlation: bool) -> tuple[float, list[str]]:
    reasons: list[str] = []
    if unknown_correlation:
        reasons.append("correlation_unbekannt_konservativ")
        return 1.0, reasons
    if correlation_stress is None:
        reasons.append("correlation_fehlt_konservativ")
        return 1.0, reasons
    return max(0.0, correlation_stress), reasons


def evaluate_portfolio_risk(snapshot: PortfolioSnapshot | None, limits: PortfolioRiskLimits) -> PortfolioRiskResult:
    block_reasons = validate_portfolio_risk_context(snapshot)
    cap_reasons: list[str] = []

    if snapshot is None:
        return PortfolioRiskResult(
            total_exposure=0.0,
            margin_usage=0.0,
            open_positions_count=0,
            pending_orders_count=0,
            pending_live_candidates_count=0,
            net_long_exposure=0.0,
            net_short_exposure=0.0,
            family_exposure={},
            correlation_stress=1.0,
            funding_concentration=0.0,
            basis_risk=0.0,
            largest_position_risk=0.0,
            block_reasons=block_reasons,
            cap_reasons=cap_reasons,
            allows_next_gate_only=False,
        )

    total_exposure = compute_total_exposure(snapshot)
    margin_usage = snapshot.used_margin / snapshot.account_equity if snapshot.account_equity > 0 else 1.0
    net_long, net_short = compute_directional_exposure(snapshot)
    family_exposure = compute_family_exposure(snapshot)
    correlation_stress, correlation_reasons = apply_correlation_stress_cap(
        correlation_stress=snapshot.correlation_stress,
        unknown_correlation=snapshot.unknown_correlation,
    )
    cap_reasons.extend(correlation_reasons)
    if correlation_stress >= limits.max_correlation_stress:
        block_reasons.append("correlation_stress_zu_hoch")

    largest_position_risk = 0.0
    basis_risk = 0.0
    funding_concentration = 0.0
    all_items = snapshot.open_positions + snapshot.pending_orders + snapshot.pending_live_candidates
    if all_items:
        largest_position_risk = max(max(0.0, item.risk_pct) for item in all_items)
        basis_risk = max(max(0.0, item.basis_bps_abs) for item in all_items)
        funding_sum = sum(max(0.0, item.funding_rate_abs) for item in all_items)
        funding_concentration = funding_sum / len(all_items)

    if total_exposure > limits.max_total_notional:
        block_reasons.append("total_exposure_ueber_limit")
    if margin_usage > limits.max_margin_usage:
        block_reasons.append("margin_usage_ueber_limit")
    if largest_position_risk > limits.max_largest_position_risk:
        block_reasons.append("largest_position_risk_ueber_limit")
    if len(snapshot.open_positions) > limits.max_concurrent_positions:
        block_reasons.append("max_concurrent_positions_ueberschritten")
    if len(snapshot.pending_orders) > limits.max_pending_orders:
        block_reasons.append("zu_viele_pending_orders")
    if len(snapshot.pending_live_candidates) > limits.max_pending_live_candidates:
        block_reasons.append("zu_viele_pending_live_candidates")
    if net_long > limits.max_net_directional_exposure:
        block_reasons.append("net_long_exposure_ueber_limit")
    if net_short > limits.max_net_directional_exposure:
        block_reasons.append("net_short_exposure_ueber_limit")
    if funding_concentration > limits.max_funding_concentration:
        block_reasons.append("funding_konzentration_zu_hoch")
    if any(value > limits.max_family_exposure for value in family_exposure.values()):
        block_reasons.append("family_exposure_zu_hoch")

    return PortfolioRiskResult(
        total_exposure=total_exposure,
        margin_usage=margin_usage,
        open_positions_count=len(snapshot.open_positions),
        pending_orders_count=len(snapshot.pending_orders),
        pending_live_candidates_count=len(snapshot.pending_live_candidates),
        net_long_exposure=net_long,
        net_short_exposure=net_short,
        family_exposure=family_exposure,
        correlation_stress=correlation_stress,
        funding_concentration=funding_concentration,
        basis_risk=basis_risk,
        largest_position_risk=largest_position_risk,
        block_reasons=list(dict.fromkeys(block_reasons)),
        cap_reasons=list(dict.fromkeys(cap_reasons)),
        allows_next_gate_only=len(block_reasons) == 0,
    )


def portfolio_risk_blocks_live(result: PortfolioRiskResult) -> bool:
    return len(result.block_reasons) > 0


def build_portfolio_risk_summary_de(result: PortfolioRiskResult) -> str:
    if result.block_reasons:
        return (
            "Portfolio-Risiko blockiert Live-Opening: "
            + ", ".join(result.block_reasons)
            + ". Portfolio-Go/No-Go: NO_GO."
        )
    return (
        f"Portfolio-Risiko im Rahmen: Exposure={result.total_exposure:.2f}, "
        f"Margin={result.margin_usage:.4f}, Positionen={result.open_positions_count}, "
        f"Pending Orders={result.pending_orders_count}, Pending Candidates={result.pending_live_candidates_count}. "
        "Portfolio-Go/No-Go: nur naechster Gate-Schritt."
    )
