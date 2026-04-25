from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

Decision = Literal["GO", "GO_WITH_WARNINGS", "NO_GO", "NOT_ENOUGH_EVIDENCE", "EXTERNAL_REQUIRED"]
Mode = Literal[
    "local_dev",
    "paper",
    "shadow",
    "staging",
    "private_live_candidate",
    "private_live_allowed",
    "full_autonomous_live",
]

PROJECT_NAME = "bitget-btc-ai"
SCORECARD_VERSION = "private-main-console-scorecard-v1"

MODES: tuple[Mode, ...] = (
    "local_dev",
    "paper",
    "shadow",
    "staging",
    "private_live_candidate",
    "private_live_allowed",
    "full_autonomous_live",
)

REQUIRED_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("private_owner_scope", "Private Owner Scope"),
    ("german_only_ui", "German-only UI"),
    ("main_console_information_architecture", "Main Console Structure"),
    ("bitget_asset_universe", "Bitget Asset Universe"),
    ("instrument_catalog", "Instrument Catalog"),
    ("market_data_quality_per_asset", "Asset Data Quality"),
    ("liquidity_spread_slippage_per_asset", "Liquidity/Spread/Slippage"),
    ("asset_risk_tiers", "Asset Risk Tiers"),
    ("strategy_validation_per_asset_class", "Strategy Evidence"),
    ("portfolio_risk", "Portfolio Risk"),
    ("live_broker_fail_closed", "Live-Broker"),
    ("reconcile_safety", "Reconcile"),
    ("order_idempotency", "Order Idempotency"),
    ("kill_switch_safety_latch", "Kill-Switch/Safety-Latch"),
    ("bitget_exchange_readiness", "Bitget Readiness"),
    ("env_secrets_profiles", "Env/Secrets"),
    ("backup_restore", "Restore Test"),
    ("shadow_burn_in", "Shadow Burn-in"),
    ("emergency_flatten", "Safety Drill"),
    ("observability_slos", "Observability/Alerts"),
    ("deployment_parity", "Deployment Parity"),
    ("final_go_no_go_scorecard", "Final Owner Signoff"),
)

PRIVATE_LIVE_REQUIRED_VERIFIED = frozenset(
    {
        "bitget_exchange_readiness",
        "backup_restore",
        "shadow_burn_in",
        "emergency_flatten",
        "bitget_asset_universe",
        "market_data_quality_per_asset",
        "asset_risk_tiers",
        "live_broker_fail_closed",
        "reconcile_safety",
        "kill_switch_safety_latch",
        "final_go_no_go_scorecard",
    }
)

REPORT_HINTS = {
    "bitget_exchange_readiness": ("bitget_readiness.md",),
    "backup_restore": ("dr_restore_test.md", "dr_staging", "restore"),
    "shadow_burn_in": ("shadow_burn_in", "sbi"),
    "emergency_flatten": ("live_safety_drill", "emergency"),
    "final_go_no_go_scorecard": ("production_readiness_scorecard",),
}


@dataclass(frozen=True)
class CategoryScore:
    id: str
    title: str
    status: str
    severity: str
    blocks_live_trading: bool
    decision: Decision
    missing_evidence: list[str] = field(default_factory=list)
    next_action: str = ""


@dataclass(frozen=True)
class ModeDecision:
    mode: Mode
    decision: Decision
    reason: str


@dataclass(frozen=True)
class ReadinessScorecard:
    version: str
    project: str
    generated_at: str
    git_sha: str
    overall_status: Decision
    mode_decisions: list[ModeDecision]
    categories: list[CategoryScore]
    live_blockers: list[str]
    private_live_blockers: list[str]
    asset_blockers: list[str]
    missing_evidence: list[str]
    next_steps: list[str]
    owner_signoff_required: bool = True
    owner_signoff: str = "Philipp Crljic: PENDING"


def _decision_for_category(status: str, *, blocks_live: bool) -> Decision:
    if status == "verified":
        return "GO"
    if status == "implemented":
        return "GO_WITH_WARNINGS" if not blocks_live else "NOT_ENOUGH_EVIDENCE"
    if status == "external_required":
        return "EXTERNAL_REQUIRED"
    if status in {"missing", "partial"}:
        return "NOT_ENOUGH_EVIDENCE"
    return "NO_GO"


def categories_from_matrix(matrix: dict[str, Any], report_names: list[str] | None = None) -> list[CategoryScore]:
    report_names = report_names or []
    by_id = {str(item.get("id")): item for item in matrix.get("categories", []) if isinstance(item, dict)}
    categories: list[CategoryScore] = []
    for category_id, fallback_title in REQUIRED_CATEGORIES:
        raw = by_id.get(category_id, {})
        status = str(raw.get("status") or "missing")
        blocks = bool(raw.get("blocks_live_trading", True))
        missing = []
        if status != "verified":
            missing.append(f"{category_id}: status={status}")
        hints = REPORT_HINTS.get(category_id, ())
        if hints and not any(any(hint in report for hint in hints) for report in report_names):
            missing.append(f"{category_id}: runtime report missing")
        categories.append(
            CategoryScore(
                id=category_id,
                title=str(raw.get("title") or fallback_title),
                status=status,
                severity=str(raw.get("severity") or "P0"),
                blocks_live_trading=blocks,
                decision=_decision_for_category(status, blocks_live=blocks),
                missing_evidence=missing,
                next_action=str(raw.get("next_action") or "Evidence ergaenzen."),
            )
        )
    return categories


def summarize_live_blockers(categories: list[CategoryScore]) -> list[str]:
    blockers: list[str] = []
    for category in categories:
        if category.blocks_live_trading and category.status != "verified":
            blockers.append(f"{category.id}: {category.status} ({category.severity})")
    return blockers


def summarize_asset_blockers(categories: list[CategoryScore], *, asset_data_quality_verified: bool = False) -> list[str]:
    blockers: list[str] = []
    for category_id in (
        "bitget_asset_universe",
        "instrument_catalog",
        "market_data_quality_per_asset",
        "liquidity_spread_slippage_per_asset",
        "asset_risk_tiers",
    ):
        category = next((item for item in categories if item.id == category_id), None)
        if category and category.status != "verified":
            blockers.append(f"{category_id}: {category.status}")
    if not asset_data_quality_verified:
        blockers.append("asset_data_quality_for_concrete_assets_missing")
    return blockers


def readiness_allows_mode(scorecard: ReadinessScorecard, mode: Mode) -> bool:
    decision = next((item for item in scorecard.mode_decisions if item.mode == mode), None)
    return bool(decision and decision.decision in {"GO", "GO_WITH_WARNINGS"})


def _required_private_live_blockers(categories: list[CategoryScore], report_names: list[str]) -> list[str]:
    by_id = {item.id: item for item in categories}
    blockers: list[str] = []
    for category_id in sorted(PRIVATE_LIVE_REQUIRED_VERIFIED):
        category = by_id.get(category_id)
        if category is None or category.status != "verified":
            status = category.status if category else "missing"
            blockers.append(f"{category_id}_not_verified:{status}")
    for category_id, hints in REPORT_HINTS.items():
        if category_id in PRIVATE_LIVE_REQUIRED_VERIFIED:
            if not any(any(hint in report for hint in hints) for report in report_names):
                blockers.append(f"{category_id}_runtime_report_missing")
    return blockers


def _mode_decisions(
    categories: list[CategoryScore],
    live_blockers: list[str],
    asset_blockers: list[str],
    report_names: list[str],
) -> list[ModeDecision]:
    p0_blockers = [item for item in live_blockers if "(P0)" in item]
    private_live_blockers = _required_private_live_blockers(categories, report_names)
    paper_risky = any(
        item.id in {"env_secrets_profiles", "private_owner_scope"}
        and item.status in {"missing"}
        for item in categories
    )
    decisions: list[ModeDecision] = [
        ModeDecision("local_dev", "GO_WITH_WARNINGS", "Local ist erlaubt, aber nicht production-ready."),
        ModeDecision(
            "paper",
            "NO_GO" if paper_risky else "GO",
            "Paper ist erlaubt, solange keine Live-Gefahr aus ENV/Scope entsteht.",
        ),
        ModeDecision(
            "shadow",
            "GO_WITH_WARNINGS",
            "Shadow darf ohne Live-Submits laufen; fehlende Live-Evidence bleibt sichtbar.",
        ),
        ModeDecision(
            "staging",
            "NOT_ENOUGH_EVIDENCE" if p0_blockers else "GO_WITH_WARNINGS",
            "Staging braucht fehlende P0-Evidence vor privatem Live-Go.",
        ),
        ModeDecision(
            "private_live_candidate",
            "NO_GO" if p0_blockers or asset_blockers else "EXTERNAL_REQUIRED",
            "Private Live Candidate bleibt blockiert, solange P0-/Asset-Blocker offen sind.",
        ),
        ModeDecision(
            "private_live_allowed",
            "GO" if not private_live_blockers and not live_blockers and not asset_blockers else "NO_GO",
            "Private Live braucht verifizierte Bitget-, Restore-, Burn-in-, Safety-, Asset-, Broker-, Reconcile- und Owner-Evidence.",
        ),
        ModeDecision(
            "full_autonomous_live",
            "NO_GO",
            "Full Autonomous Live bleibt standardmaessig NO_GO ohne vollstaendig verified Matrix und lange echte Live-Historie.",
        ),
    ]
    return decisions


def build_readiness_scorecard(
    matrix: dict[str, Any],
    *,
    git_sha: str = "unknown",
    report_names: list[str] | None = None,
    asset_data_quality_verified: bool = False,
) -> ReadinessScorecard:
    report_names = report_names or []
    categories = categories_from_matrix(matrix, report_names)
    live_blockers = summarize_live_blockers(categories)
    asset_blockers = summarize_asset_blockers(
        categories,
        asset_data_quality_verified=asset_data_quality_verified,
    )
    missing_evidence = [
        evidence
        for category in categories
        for evidence in category.missing_evidence
    ]
    next_steps = [
        category.next_action
        for category in categories
        if category.blocks_live_trading and category.status != "verified"
    ][:12]
    mode_decisions = _mode_decisions(categories, live_blockers, asset_blockers, report_names)
    private_live_blockers = _required_private_live_blockers(categories, report_names)
    private_live = next(item for item in mode_decisions if item.mode == "private_live_allowed")
    overall: Decision = "GO" if private_live.decision == "GO" else "NO_GO"
    return ReadinessScorecard(
        version=SCORECARD_VERSION,
        project=PROJECT_NAME,
        generated_at=datetime.now(tz=UTC).isoformat(),
        git_sha=git_sha,
        overall_status=overall,
        mode_decisions=mode_decisions,
        categories=categories,
        live_blockers=live_blockers,
        private_live_blockers=private_live_blockers,
        asset_blockers=asset_blockers,
        missing_evidence=missing_evidence,
        next_steps=next_steps,
    )


def scorecard_to_console_payload(scorecard: ReadinessScorecard) -> dict[str, Any]:
    return {
        **asdict(scorecard),
        "allows": {
            mode: readiness_allows_mode(scorecard, mode) for mode in MODES
        },
        "live_blocker_count": len(scorecard.live_blockers),
        "asset_blocker_count": len(scorecard.asset_blockers),
    }
