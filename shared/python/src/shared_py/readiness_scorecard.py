from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

OWNER_PRIVATE_LIVE_RELEASE_FILENAME = "owner_private_live_release.json"

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
    ("main_console_information_architecture", "Main Console Structure"),
    ("german_only_ui", "German-only UI"),
    ("bitget_asset_universe", "Bitget Asset Universe"),
    ("instrument_catalog", "Instrument Catalog"),
    ("asset_quarantine_and_delisting", "Asset Quarantine and Delisting"),
    ("market_data_quality_per_asset", "Asset Data Quality"),
    ("liquidity_spread_slippage_per_asset", "Liquidity/Spread/Slippage"),
    ("asset_risk_tiers", "Asset Risk Tiers"),
    ("multi_asset_order_sizing", "Multi-Asset Order Sizing"),
    ("strategy_validation_per_asset_class", "Strategy Evidence"),
    ("portfolio_risk", "Portfolio Risk"),
    ("live_broker_fail_closed", "Live-Broker"),
    ("order_idempotency", "Order Idempotency"),
    ("reconcile_safety", "Reconcile"),
    ("kill_switch_safety_latch", "Kill-Switch/Safety-Latch"),
    ("emergency_flatten", "Safety Drill"),
    ("bitget_exchange_readiness", "Bitget Readiness"),
    ("env_secrets_profiles", "Env/Secrets"),
    ("observability_slos", "Observability/Alerts"),
    ("alert_routing", "Alert Routing"),
    ("backup_restore", "Restore Test"),
    ("shadow_burn_in", "Shadow Burn-in"),
    ("disaster_recovery", "Disaster Recovery"),
    ("audit_forensics", "Audit/Forensics"),
    ("frontend_main_console_security", "Frontend Main Console Security"),
    ("admin_access_single_owner", "Admin Access Single Owner"),
    ("deployment_parity", "Deployment Parity"),
    ("supply_chain_security", "Supply Chain Security"),
    ("branch_protection_ci", "CI and Branch-Protection Evidence"),
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
        "liquidity_spread_slippage_per_asset",
        "asset_risk_tiers",
        "multi_asset_order_sizing",
        "portfolio_risk",
        "live_broker_fail_closed",
        "order_idempotency",
        "reconcile_safety",
        "kill_switch_safety_latch",
        "env_secrets_profiles",
        "alert_routing",
        "disaster_recovery",
        "audit_forensics",
        "admin_access_single_owner",
        "branch_protection_ci",
        "final_go_no_go_scorecard",
    }
)

REPORT_HINTS = {
    "bitget_exchange_readiness": ("bitget_readiness.md",),
    "backup_restore": ("dr_restore_test.md", "dr_staging", "restore"),
    "shadow_burn_in": ("shadow_burn_in", "sbi"),
    "emergency_flatten": ("live_safety_drill", "emergency"),
    "market_data_quality_per_asset": ("asset_preflight_evidence", "market_data_quality"),
    "liquidity_spread_slippage_per_asset": ("asset_preflight_evidence", "liquidity_quality"),
    "asset_risk_tiers": ("asset_preflight_evidence", "asset_risk"),
    "multi_asset_order_sizing": ("asset_preflight_evidence",),
    "final_go_no_go_scorecard": ("production_readiness_scorecard",),
    "branch_protection_ci": ("branch_protection_ci_evidence",),
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
    owner_private_live_release_confirmed: bool = False


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


def owner_private_live_release_payload_ok(payload: Any) -> bool:
    """
    Strikte Pruefung der lokalen Owner-Freigabe-Datei (ohne Secrets).
    Allein ein auf ``verified`` gesetztes YAML reicht nicht fuer private_live_allowed.
    """
    if not isinstance(payload, dict):
        return False
    if payload.get("owner_private_live_go") is not True:
        return False
    ref = payload.get("signoff_reference")
    if not isinstance(ref, str) or len(ref.strip()) < 8:
        return False
    recorded = payload.get("recorded_at")
    if not isinstance(recorded, str) or len(recorded.strip()) < 10:
        return False
    return True


def asset_preflight_fixture_evidence_ok(report_payloads: dict[str, Any] | None = None) -> bool:
    report_payloads = report_payloads or {}
    payload = report_payloads.get("asset_preflight_evidence")
    if not isinstance(payload, dict):
        return False
    assets = payload.get("assets")
    if not isinstance(assets, list) or not assets:
        return False
    if int(payload.get("assets_checked") or 0) < 1:
        return False
    if int(payload.get("live_allowed_count") or 0) != 0:
        return False
    if payload.get("private_live_decision") != "NO_GO":
        return False
    return all(
        isinstance(item, dict)
        and item.get("live_preflight_status") == "LIVE_BLOCKED"
        and isinstance(item.get("block_reasons"), list)
        and len(item.get("block_reasons") or []) > 0
        for item in assets
    )


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
    *,
    owner_private_live_release_confirmed: bool,
) -> list[ModeDecision]:
    p0_blockers = [item for item in live_blockers if "(P0)" in item]
    private_live_blockers = _required_private_live_blockers(categories, report_names)
    if not owner_private_live_release_confirmed:
        private_live_blockers = [
            *private_live_blockers,
            "owner_private_live_release:not_confirmed",
        ]
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
            "GO"
            if (
                not private_live_blockers
                and not live_blockers
                and not asset_blockers
                and owner_private_live_release_confirmed
            )
            else "NO_GO",
            "Private Live braucht verifizierte Bitget-, Restore-, Burn-in-, Safety-, Asset-, Broker-, Reconcile- und Owner-Evidence "
            "sowie die maschinelle Datei reports/owner_private_live_release.json (gitignored) mit gueltiger Struktur.",
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
    report_payloads: dict[str, Any] | None = None,
    owner_private_live_release_confirmed: bool = False,
) -> ReadinessScorecard:
    report_names = report_names or []
    asset_fixture_evidence = asset_preflight_fixture_evidence_ok(report_payloads)
    categories = categories_from_matrix(matrix, report_names)
    live_blockers = summarize_live_blockers(categories)
    asset_blockers = summarize_asset_blockers(
        categories,
        asset_data_quality_verified=asset_data_quality_verified or asset_fixture_evidence,
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
    private_live_blockers = _required_private_live_blockers(categories, report_names)
    if not owner_private_live_release_confirmed:
        private_live_blockers = [
            *private_live_blockers,
            "owner_private_live_release:not_confirmed",
        ]
    mode_decisions = _mode_decisions(
        categories,
        live_blockers,
        asset_blockers,
        report_names,
        owner_private_live_release_confirmed=owner_private_live_release_confirmed,
    )
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
        owner_private_live_release_confirmed=owner_private_live_release_confirmed,
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
