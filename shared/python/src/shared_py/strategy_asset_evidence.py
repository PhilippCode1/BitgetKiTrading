from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

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
    return list(dict.fromkeys(reasons))


def strategy_evidence_blocks_live(evidence: StrategyAssetEvidence) -> bool:
    return len(validate_strategy_asset_evidence(evidence)) > 0


def build_strategy_asset_evidence_summary_de(evidence: StrategyAssetEvidence) -> str:
    reasons = validate_strategy_asset_evidence(evidence)
    status = strategy_evidence_status_for_asset(evidence)
    if reasons:
        return (
            f"Strategie {evidence.strategy_id or 'unbekannt'} v{evidence.strategy_version or '-'} "
            f"fuer {evidence.asset_symbol}/{evidence.asset_class} blockiert: {', '.join(reasons)}."
        )
    return (
        f"Strategie {evidence.strategy_id} v{evidence.strategy_version} fuer {evidence.asset_symbol}/{evidence.asset_class} "
        f"hat Evidence-Status {status} und darf nur den naechsten Gate-Schritt erreichen."
    )
