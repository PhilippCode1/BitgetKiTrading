from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

AssetRiskTier = Literal[
    "RISK_TIER_0_BLOCKED",
    "RISK_TIER_1_MAJOR_LIQUID",
    "RISK_TIER_2_LIQUID",
    "RISK_TIER_3_ELEVATED_RISK",
    "RISK_TIER_4_SHADOW_ONLY",
    "RISK_TIER_5_BANNED_OR_DELISTED",
]
TradingMode = Literal["paper", "shadow", "live"]
AssetRiskBand = Literal["RISK_TIER_A", "RISK_TIER_B", "RISK_TIER_C", "RISK_TIER_D", "RISK_TIER_E"]


@dataclass(frozen=True)
class AssetTierPolicy:
    tier: AssetRiskTier
    allowed_modes: tuple[TradingMode, ...]
    max_leverage: int
    max_position_notional_usdt: float
    max_risk_per_trade_0_1: float
    max_daily_loss_contribution_usdt: float
    required_liquidity_status: str
    required_data_quality_status: str
    required_strategy_evidence: bool
    required_owner_approval: bool
    default_action_on_uncertainty: str
    risk_band: AssetRiskBand
    recommended_operator_note_de: str


_POLICIES: dict[AssetRiskTier, AssetTierPolicy] = {
    "RISK_TIER_0_BLOCKED": AssetTierPolicy(
        tier="RISK_TIER_0_BLOCKED",
        allowed_modes=("paper",),
        max_leverage=1,
        max_position_notional_usdt=0.0,
        max_risk_per_trade_0_1=0.0,
        max_daily_loss_contribution_usdt=0.0,
        required_liquidity_status="green",
        required_data_quality_status="data_ok",
        required_strategy_evidence=True,
        required_owner_approval=True,
        default_action_on_uncertainty="block",
        risk_band="RISK_TIER_E",
        recommended_operator_note_de="Asset blockiert; nur Anzeige/Historie.",
    ),
    "RISK_TIER_1_MAJOR_LIQUID": AssetTierPolicy(
        tier="RISK_TIER_1_MAJOR_LIQUID",
        allowed_modes=("paper", "shadow", "live"),
        max_leverage=25,
        max_position_notional_usdt=20000.0,
        max_risk_per_trade_0_1=0.02,
        max_daily_loss_contribution_usdt=500.0,
        required_liquidity_status="green",
        required_data_quality_status="data_ok",
        required_strategy_evidence=True,
        required_owner_approval=True,
        default_action_on_uncertainty="block",
        risk_band="RISK_TIER_A",
        recommended_operator_note_de="Sehr liquide Hauptklasse; konservative Live-Freigabe mit vollen Gates.",
    ),
    "RISK_TIER_2_LIQUID": AssetTierPolicy(
        tier="RISK_TIER_2_LIQUID",
        allowed_modes=("paper", "shadow", "live"),
        max_leverage=14,
        max_position_notional_usdt=10000.0,
        max_risk_per_trade_0_1=0.015,
        max_daily_loss_contribution_usdt=350.0,
        required_liquidity_status="green",
        required_data_quality_status="data_ok",
        required_strategy_evidence=True,
        required_owner_approval=True,
        default_action_on_uncertainty="block",
        risk_band="RISK_TIER_B",
        recommended_operator_note_de="Liquide Klasse; Live nur mit stabilen Gates.",
    ),
    "RISK_TIER_3_ELEVATED_RISK": AssetTierPolicy(
        tier="RISK_TIER_3_ELEVATED_RISK",
        allowed_modes=("paper", "shadow", "live"),
        max_leverage=8,
        max_position_notional_usdt=4000.0,
        max_risk_per_trade_0_1=0.01,
        max_daily_loss_contribution_usdt=180.0,
        required_liquidity_status="green",
        required_data_quality_status="data_ok",
        required_strategy_evidence=True,
        required_owner_approval=True,
        default_action_on_uncertainty="block",
        risk_band="RISK_TIER_C",
        recommended_operator_note_de="Erhoehtes Risiko; nur kleine Groessen und Owner-Review.",
    ),
    "RISK_TIER_4_SHADOW_ONLY": AssetTierPolicy(
        tier="RISK_TIER_4_SHADOW_ONLY",
        allowed_modes=("paper", "shadow"),
        max_leverage=4,
        max_position_notional_usdt=1500.0,
        max_risk_per_trade_0_1=0.005,
        max_daily_loss_contribution_usdt=80.0,
        required_liquidity_status="green",
        required_data_quality_status="data_ok",
        required_strategy_evidence=True,
        required_owner_approval=True,
        default_action_on_uncertainty="block",
        risk_band="RISK_TIER_D",
        recommended_operator_note_de="Nur Research/Paper/Shadow; kein Live-Opening.",
    ),
    "RISK_TIER_5_BANNED_OR_DELISTED": AssetTierPolicy(
        tier="RISK_TIER_5_BANNED_OR_DELISTED",
        allowed_modes=(),
        max_leverage=1,
        max_position_notional_usdt=0.0,
        max_risk_per_trade_0_1=0.0,
        max_daily_loss_contribution_usdt=0.0,
        required_liquidity_status="green",
        required_data_quality_status="data_ok",
        required_strategy_evidence=True,
        required_owner_approval=True,
        default_action_on_uncertainty="block",
        risk_band="RISK_TIER_E",
        recommended_operator_note_de="Blockiert/Delisted/Suspended; kein Trading.",
    ),
}


def classify_asset_risk_tier(
    *,
    requested_tier: str | None,
    volatility_0_1: float | None,
    spread_bps: float | None,
    delisted: bool = False,
    suspended: bool = False,
) -> str | None:
    if delisted or suspended:
        return "RISK_TIER_5_BANNED_OR_DELISTED"
    if not requested_tier:
        return None
    tier = str(requested_tier).strip().upper()
    if tier not in _POLICIES:
        return None
    if spread_bps is not None and spread_bps > 120.0:
        return "RISK_TIER_0_BLOCKED"
    if volatility_0_1 is None:
        return tier
    if volatility_0_1 >= 0.85:
        return "RISK_TIER_0_BLOCKED"
    if volatility_0_1 >= 0.65:
        if tier == "RISK_TIER_1_MAJOR_LIQUID":
            return "RISK_TIER_2_LIQUID"
        if tier == "RISK_TIER_2_LIQUID":
            return "RISK_TIER_3_ELEVATED_RISK"
        if tier == "RISK_TIER_3_ELEVATED_RISK":
            return "RISK_TIER_4_SHADOW_ONLY"
    return tier


def classify_asset_risk_band(
    *,
    requested_tier: str | None,
    liquidity_tier: str | None,
    data_quality_status: str,
    volatility_0_1: float | None,
    spread_bps: float | None,
    slippage_bps: float | None,
    delisted: bool = False,
    suspended: bool = False,
    strategy_evidence_ready: bool = False,
) -> AssetRiskBand:
    tier = classify_asset_risk_tier(
        requested_tier=requested_tier,
        volatility_0_1=volatility_0_1,
        spread_bps=spread_bps,
        delisted=delisted,
        suspended=suspended,
    )
    if not tier:
        return "RISK_TIER_E"
    policy = _POLICIES.get(tier)  # type: ignore[arg-type]
    if policy is None:
        return "RISK_TIER_E"
    if data_quality_status != "data_ok":
        return "RISK_TIER_D"
    if slippage_bps is not None and slippage_bps > 120:
        return "RISK_TIER_D"
    if liquidity_tier and str(liquidity_tier).upper() in {"TIER_4", "TIER_5"}:
        return "RISK_TIER_D"
    if policy.risk_band == "RISK_TIER_C" and not strategy_evidence_ready:
        return "RISK_TIER_D"
    return policy.risk_band


def asset_tier_allows_mode(tier: str | None, mode: TradingMode) -> bool:
    if tier is None:
        return False
    policy = _POLICIES.get(str(tier).strip().upper())  # type: ignore[arg-type]
    if policy is None:
        return False
    return mode in policy.allowed_modes


def max_leverage_for_asset_tier(tier: str | None) -> int:
    if tier is None:
        return 1
    policy = _POLICIES.get(str(tier).strip().upper())  # type: ignore[arg-type]
    if policy is None:
        return 1
    return policy.max_leverage


def dynamic_max_leverage_for_asset(
    *,
    tier: str | None,
    volatility_0_1: float | None,
    live_start_phase: bool,
) -> int:
    base = max_leverage_for_asset_tier(tier)
    if volatility_0_1 is not None:
        if volatility_0_1 >= 0.8:
            base = min(base, 2)
        elif volatility_0_1 >= 0.65:
            base = min(base, max(3, base // 2))
    if live_start_phase:
        base = min(base, 5)
    return max(1, base)


def max_notional_for_asset_tier(tier: str | None) -> float:
    if tier is None:
        return 0.0
    policy = _POLICIES.get(str(tier).strip().upper())  # type: ignore[arg-type]
    if policy is None:
        return 0.0
    return policy.max_position_notional_usdt


def asset_tier_requires_owner_review(tier: str | None) -> bool:
    normalized_tier = str(tier).strip().upper() if tier else None
    if not normalized_tier:
        return True
    policy = _POLICIES.get(normalized_tier)  # type: ignore[arg-type]
    if policy is None:
        return True
    return policy.risk_band in {"RISK_TIER_C", "RISK_TIER_D", "RISK_TIER_E"} or policy.required_owner_approval


def asset_risk_tier_blocks_live(tier: str | None) -> bool:
    normalized_tier = str(tier).strip().upper() if tier else None
    if not normalized_tier:
        return True
    if normalized_tier in {"RISK_TIER_0_BLOCKED", "RISK_TIER_4_SHADOW_ONLY", "RISK_TIER_5_BANNED_OR_DELISTED"}:
        return True
    policy = _POLICIES.get(normalized_tier)  # type: ignore[arg-type]
    if policy is None:
        return True
    return "live" not in policy.allowed_modes


def asset_live_eligibility_reasons(
    *,
    tier: str | None,
    data_quality_status: str,
    liquidity_status: str,
    strategy_evidence_ready: bool,
    owner_approved: bool,
    account_context_fresh: bool,
    spread_bps: float | None,
) -> list[str]:
    reasons: list[str] = []
    normalized_tier = str(tier).strip().upper() if tier else None
    if not normalized_tier:
        reasons.append("asset_tier_missing")
        return reasons
    policy = _POLICIES.get(normalized_tier)  # type: ignore[arg-type]
    if policy is None:
        reasons.append("asset_tier_unknown")
        return reasons
    if normalized_tier == "RISK_TIER_0_BLOCKED":
        reasons.append("asset_tier_0_live_blocked")
    if normalized_tier == "RISK_TIER_4_SHADOW_ONLY":
        reasons.append("asset_tier_4_shadow_only")
    if normalized_tier == "RISK_TIER_5_BANNED_OR_DELISTED":
        reasons.append("asset_tier_5_banned")
    if data_quality_status != policy.required_data_quality_status:
        reasons.append("data_quality_not_green")
    if liquidity_status != policy.required_liquidity_status:
        reasons.append("liquidity_not_green")
    if policy.required_strategy_evidence and not strategy_evidence_ready:
        reasons.append("strategy_evidence_missing")
    if policy.required_owner_approval and not owner_approved:
        reasons.append("owner_approval_missing")
    if not account_context_fresh:
        reasons.append("account_context_stale")
    if spread_bps is not None and spread_bps > 100.0:
        reasons.append("spread_too_wide")
    if normalized_tier == "RISK_TIER_3_ELEVATED_RISK" and not owner_approved:
        reasons.append("tier_c_owner_review_required")
    return list(dict.fromkeys(reasons))


def validate_multi_asset_order_sizing(
    *,
    symbol: str,
    tier: str | None,
    mode: TradingMode,
    requested_leverage: int,
    requested_notional_usdt: float,
) -> dict:
    reasons: list[str] = []
    normalized_tier = str(tier).strip().upper() if tier else None
    policy = _POLICIES.get(normalized_tier) if normalized_tier else None  # type: ignore[arg-type]
    if policy is None:
        reasons.append("asset_tier_missing_or_unknown")
        return {
            "valid": False,
            "symbol": symbol,
            "tier": normalized_tier,
            "requested_leverage": requested_leverage,
            "requested_notional_usdt": requested_notional_usdt,
            "effective_leverage": 1,
            "effective_notional_usdt": 0.0,
            "reasons": reasons,
        }
    if mode not in policy.allowed_modes:
        reasons.append("mode_not_allowed_for_tier")
    effective_leverage = min(int(requested_leverage), policy.max_leverage)
    if mode == "live" and int(requested_leverage) > policy.max_leverage:
        reasons.append("leverage_above_tier_cap_live_blocked")
    elif int(requested_leverage) > policy.max_leverage:
        reasons.append("leverage_capped_to_tier_limit")
    if float(requested_notional_usdt) > policy.max_position_notional_usdt:
        reasons.append("position_notional_above_tier_cap")
    valid = len([r for r in reasons if r != "leverage_capped_to_tier_limit"]) == 0
    return {
        "valid": valid,
        "symbol": symbol,
        "tier": normalized_tier,
        "requested_leverage": int(requested_leverage),
        "requested_notional_usdt": float(requested_notional_usdt),
        "effective_leverage": int(effective_leverage),
        "effective_notional_usdt": min(float(requested_notional_usdt), policy.max_position_notional_usdt),
        "reasons": reasons,
    }


def build_asset_risk_audit_payload(
    *,
    symbol: str,
    tier: str | None,
    mode: TradingMode,
    reasons: list[str],
) -> dict:
    normalized_tier = str(tier).strip().upper() if tier else None
    policy = _POLICIES.get(normalized_tier) if normalized_tier else None  # type: ignore[arg-type]
    return {
        "symbol": symbol,
        "tier": normalized_tier,
        "risk_band": policy.risk_band if policy else "RISK_TIER_E",
        "mode": mode,
        "reasons": list(dict.fromkeys(reasons)),
        "policy": asdict(policy) if policy else None,
    }


def build_asset_risk_summary_de(
    *,
    symbol: str,
    tier: str | None,
    reasons: list[str],
    max_leverage: int | None = None,
    max_notional_usdt: float | None = None,
) -> str:
    normalized_tier = str(tier).strip().upper() if tier else "UNBEKANNT"
    policy = _POLICIES.get(normalized_tier) if normalized_tier in _POLICIES else None  # type: ignore[arg-type]
    band = policy.risk_band if policy else "RISK_TIER_E"
    lev = max_leverage if max_leverage is not None else max_leverage_for_asset_tier(tier)
    notional = max_notional_usdt if max_notional_usdt is not None else max_notional_for_asset_tier(tier)
    reason_text = ", ".join(reasons) if reasons else "keine offenen Blockgruende"
    note = policy.recommended_operator_note_de if policy else "Unbekannter Tier-Kontext, fail-closed blockiert."
    return (
        f"Asset {symbol}: Tier={normalized_tier} ({band}), "
        f"max Hebel={lev}x, max Notional={notional:.2f} USDT, "
        f"Grunde={reason_text}. Hinweis: {note}"
    )
