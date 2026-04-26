from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

EvidenceStatus = Literal[
    "missing",
    "research_only",
    "backtest_available",
    "walk_forward_available",
    "paper_available",
    "shadow_available",
    "shadow_passed",
    "live_candidate",
    "live_allowed",
    "rejected",
    "expired",
]

AssetClass = Literal[
    "top_liquid_futures",
    "major_spot",
    "mid_liquidity",
    "high_volatility",
    "low_liquidity",
    "new_listing",
    "delisting_risk",
    "unknown",
]

Decision = Literal["ALLOW_FOR_PAPER", "ALLOW_FOR_SHADOW", "BLOCK_FOR_LIVE", "BLOCK_ALL"]
EvidenceLevel = Literal["synthetic", "backtest", "paper", "shadow", "runtime"]


@dataclass(frozen=True)
class StrategyAssetEvidence:
    strategy_id: str | None
    strategy_version: str | None
    playbook_id: str | None
    asset_symbol: str
    asset_class: AssetClass
    market_family: str
    risk_tier: str | None
    data_quality_status: str
    evidence_status: EvidenceStatus
    backtest_available: bool
    walk_forward_available: bool
    paper_available: bool
    shadow_available: bool
    shadow_passed: bool
    expires_at: str | None
    scope_asset_symbols: list[str]
    scope_asset_classes: list[AssetClass]
    allowed_market_families: list[str]
    allowed_risk_tiers: list[str]
    symbols_tested: list[str] | None = None
    timeframe: str | None = None
    test_start: str | None = None
    test_end: str | None = None
    data_source: str | None = None
    fees_included: bool = False
    spread_included: bool = False
    slippage_included: bool = False
    funding_included: bool | None = None
    leverage_assumption: float | None = None
    risk_per_trade: float | None = None
    max_position_size: float | None = None
    number_of_trades: int = 0
    win_rate: float | None = None
    average_win: float | None = None
    average_loss: float | None = None
    profit_factor: float | None = None
    expectancy: float | None = None
    max_drawdown: float | None = None
    longest_loss_streak: int | None = None
    sharpe_or_sortino: float | None = None
    out_of_sample_result: str | None = None
    walk_forward_result: str | None = None
    paper_result: str | None = None
    shadow_result: str | None = None
    market_phases_tested: list[str] | None = None
    known_failure_modes: list[str] | None = None
    parameter_hash: str | None = None
    model_parameters_reproducible: bool = False
    evidence_level: EvidenceLevel = "synthetic"
    checked_at: str | None = None
    git_sha: str | None = None


def _bool_result_ok(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"ok", "passed", "pass", "green", "verified"}


def _has_sufficient_market_phase_coverage(evidence: StrategyAssetEvidence) -> bool:
    phases = evidence.market_phases_tested or []
    normalized = {p.strip().lower() for p in phases if str(p).strip()}
    if len(normalized) >= 2:
        return True
    return False


def _is_expired(expires_at: str | None, now: datetime | None = None) -> bool:
    if not expires_at:
        return False
    ts = expires_at.replace("Z", "+00:00")
    try:
        end = datetime.fromisoformat(ts)
    except ValueError:
        return True
    ref = now or datetime.now(UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    return end <= ref


def strategy_scope_matches_asset_class(evidence: StrategyAssetEvidence) -> bool:
    if evidence.asset_class == "unknown":
        return False
    if evidence.asset_symbol in evidence.scope_asset_symbols:
        return True
    return evidence.asset_class in evidence.scope_asset_classes


def strategy_evidence_status_for_asset(evidence: StrategyAssetEvidence) -> EvidenceStatus:
    if evidence.evidence_status == "rejected":
        return "rejected"
    if _is_expired(evidence.expires_at):
        return "expired"
    return evidence.evidence_status


def validate_strategy_asset_evidence(evidence: StrategyAssetEvidence) -> list[str]:
    reasons: list[str] = []
    status = strategy_evidence_status_for_asset(evidence)
    if not evidence.strategy_id:
        reasons.append("strategy_id_fehlt")
    if not evidence.strategy_version:
        reasons.append("strategy_version_fehlt")
    if not evidence.playbook_id:
        reasons.append("playbook_id_fehlt")
    if evidence.asset_class == "unknown":
        reasons.append("asset_class_unknown")
    if status in {"missing", "research_only", "backtest_available", "paper_available"}:
        reasons.append("evidence_status_nicht_live_faehig")
    if status == "rejected":
        reasons.append("strategy_evidence_rejected")
    if status == "expired":
        reasons.append("strategy_evidence_expired")
    if evidence.market_family.lower() not in {item.lower() for item in evidence.allowed_market_families}:
        reasons.append("market_family_mismatch")
    if evidence.risk_tier is None or evidence.risk_tier not in evidence.allowed_risk_tiers:
        reasons.append("risk_tier_mismatch")
    if evidence.data_quality_status != "data_ok":
        reasons.append("data_quality_mismatch")
    if not strategy_scope_matches_asset_class(evidence):
        reasons.append("strategy_scope_mismatch")
    if status in {"shadow_passed", "live_candidate", "live_allowed"} and not evidence.shadow_available:
        reasons.append("shadow_evidence_fehlt")
    if status == "live_allowed" and not evidence.shadow_passed:
        reasons.append("shadow_passed_fehlt")
    if not evidence.fees_included:
        reasons.append("fees_fehlen")
    if not evidence.spread_included:
        reasons.append("spread_fehlt")
    if not evidence.slippage_included:
        reasons.append("slippage_fehlt")
    if evidence.market_family.lower() == "futures" and evidence.funding_included is not True:
        reasons.append("funding_fehlt_futures")
    if evidence.max_drawdown is None:
        reasons.append("drawdown_fehlt")
    elif evidence.max_drawdown > 0.25:
        reasons.append("drawdown_limit_ueberschritten")
    if evidence.number_of_trades < 30:
        reasons.append("zu_wenige_trades")
    if evidence.profit_factor is None:
        reasons.append("profit_factor_fehlt")
    if evidence.evidence_level == "synthetic" and evidence.profit_factor is not None:
        reasons.append("profit_factor_nur_synthetisch")
    if not _bool_result_ok(evidence.out_of_sample_result):
        reasons.append("out_of_sample_fehlt_oder_nicht_bestanden")
    if not _bool_result_ok(evidence.walk_forward_result):
        reasons.append("walk_forward_fehlt_oder_nicht_bestanden")
    if not _bool_result_ok(evidence.paper_result):
        reasons.append("paper_evidence_fehlt_oder_nicht_bestanden")
    if not _bool_result_ok(evidence.shadow_result):
        reasons.append("shadow_evidence_fehlt_oder_nicht_bestanden")
    if not _has_sufficient_market_phase_coverage(evidence):
        reasons.append("marktphasen_nicht_ausreichend")
    if evidence.longest_loss_streak is None:
        reasons.append("verlustserie_nicht_bewertet")
    if evidence.risk_per_trade is None:
        reasons.append("risk_per_trade_unbekannt")
    if not evidence.strategy_version:
        reasons.append("strategy_version_ungebunden")
    if not evidence.parameter_hash:
        reasons.append("parameter_hash_fehlt")
    if not evidence.model_parameters_reproducible:
        reasons.append("parameter_nicht_reproduzierbar")
    if not evidence.checked_at:
        reasons.append("checked_at_fehlt")
    if not evidence.git_sha:
        reasons.append("git_sha_fehlt")
    return list(dict.fromkeys(reasons))


def strategy_evidence_blocks_live(evidence: StrategyAssetEvidence) -> bool:
    return len(validate_strategy_asset_evidence(evidence)) > 0


def strategy_evidence_decision(evidence: StrategyAssetEvidence) -> Decision:
    reasons = validate_strategy_asset_evidence(evidence)
    if not reasons:
        return "ALLOW_FOR_SHADOW"
    hard_all = {"strategy_evidence_rejected", "asset_class_unknown", "strategy_scope_mismatch"}
    if any(reason in hard_all for reason in reasons):
        return "BLOCK_ALL"
    if "paper_evidence_fehlt_oder_nicht_bestanden" in reasons:
        return "ALLOW_FOR_PAPER"
    return "BLOCK_FOR_LIVE"


def strategy_evidence_live_allowed(evidence: StrategyAssetEvidence) -> bool:
    if strategy_evidence_decision(evidence) in {"BLOCK_ALL", "BLOCK_FOR_LIVE"}:
        return False
    return evidence.evidence_level in {"shadow", "runtime"} and not strategy_evidence_blocks_live(evidence)


def llm_strategy_execution_authority_contract(payload: dict[str, Any] | None) -> list[str]:
    if not isinstance(payload, dict):
        return ["llm_payload_missing"]
    value = str(payload.get("execution_authority", "")).strip().lower()
    if value in {"none", "no", "disabled", "forbidden"}:
        return []
    return ["execution_authority_muss_none_sein"]


def build_strategy_asset_evidence_summary_de(evidence: StrategyAssetEvidence) -> str:
    reasons = validate_strategy_asset_evidence(evidence)
    status = strategy_evidence_status_for_asset(evidence)
    decision = strategy_evidence_decision(evidence)
    if reasons:
        return (
            f"Strategie {evidence.strategy_id or 'unbekannt'} v{evidence.strategy_version or '-'} "
            f"fuer {evidence.asset_symbol}/{evidence.asset_class} blockiert ({decision}): {', '.join(reasons)}."
        )
    return (
        f"Strategie {evidence.strategy_id} v{evidence.strategy_version} fuer {evidence.asset_symbol}/{evidence.asset_class} "
        f"hat Evidence-Status {status}, Decision {decision} und darf nur den naechsten Gate-Schritt erreichen."
    )
