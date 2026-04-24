"""
Zentraler Risk-Governor + Leverage-Allocator (Hebel 7..75, konservativ).

Globale Reihenfolge (Audit / Operatoren):
1) Harte Verbote (Account, Exchange, Unsicherheits-Abstinenz, Streak, Korrelation, …)
2) Max-Exposure / Positionsgroesse (Fraktion des Kontexts)
3) Hebel-Obergrenze aus Qualitaetslage, dann Zusammenfuehrung mit Hybrid-Faktor-Caps

News/LLM: hier nicht beteiligt — nur deterministische Inputs (Snapshot, Signal-Spalten, Settings).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from signal_engine.portfolio_risk import (
    assess_portfolio_structural_live_blocks,
    build_portfolio_synthesis,
    extract_portfolio_risk,
)
from signal_engine.product_family_risk import (
    maintenance_margin_rate_from_instrument,
    market_family_from_signal_row,
)
from shared_py.observability.vpin_redis import (
    VPIN_HARD_HALT_THRESHOLD_0_1,
    VPIN_ORDER_SIZE_REDUCE_THRESHOLD_0_1,
)
from shared_py.resilience.survival_kernel import (
    RISK_VOLATILITY_CLAMP_ACTIVE,
    adaptive_leverage_cap_from_atr_percent,
    effective_atr_percent_for_volatility_clamp,
)

RISK_GOVERNOR_VERSION = "risk-governor-v4"
logger = logging.getLogger("signal_engine.risk_governor")
RISK_RAMP_CAP_ENFORCED_EVENT = "RISK_RAMP_CAP_ENFORCED"
# Konservativ-Profil (FINAL_READINESS: Ensemble/Uncertainty)
CONSERVATIVE_SPECIALIST_DISSENT_0_1 = 0.35
CONSERVATIVE_ELEVATED_UNCERTAINTY_LEV1_0_1 = 0.50
# Adversarial- / Stress-Attribution: synthetische Black-Swan-Pfade (Prompt 71)
RISK_GOVERNOR_MARKET_ANOMALY_HALT_0_1 = 0.80

# Explizite Phasenreihenfolge (Dokumentation + UI)
GOVERNOR_PHASE_ORDER_DE: tuple[str, ...] = (
    "1. Universal-Hard vs. Live-Execution: Unsicherheit blocked, exchange_health_ok=false; "
    "Konto-Stress/Portfolio optional nur Live (RISK_GOVERNOR_ACCOUNT_STRESS_LIVE_ONLY); "
    "Ensemble-Disagreement / hohe Unsicherheit: Abstinenz (konservatives Profil)",
    "2. Max-Exposure / Positionsgroessen-Deckel (Tier A–D)",
    "3. Hebel 7..75; bei EXECUTION_MODE=live Ramp-Cap in max_leverage_cap + apply_live_ramp_cap",
)

QualityTier = Literal["A", "B", "C", "D"]
AllowedSide = Literal["none", "long", "short", "both"]


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _f(x: Any) -> float | None:
    if x in (None, ""):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _i(x: Any) -> int | None:
    if x in (None, ""):
        return None
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def _vpin_0_1_from_primary_tf(primary_tf: dict[str, Any]) -> float | None:
    for k in (
        "market_vpin_score",
        "vpin_toxicity_0_1",
        "vpin_0_1",
        "vpin_score_0_1",
    ):
        v = _f(primary_tf.get(k))
        if v is not None:
            return v
    return None


def _clamp_leverage(v: int, *, lo: int = 7, hi: int = 75) -> int:
    return max(lo, min(hi, int(v)))


def _execution_mode_str(settings: Any) -> str:
    em = getattr(settings, "execution_mode", "paper")
    if em is None:
        return "paper"
    v = getattr(em, "value", em)
    return str(v or "paper").strip().lower()


def _live_ramp_max_leverage(settings: Any) -> int:
    """RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE (7..75), validiert in BaseServiceSettings."""
    r = int(getattr(settings, "risk_governor_live_ramp_max_leverage", 7))
    return _clamp_leverage(r)


def _specialist_ensemble_disagreement(source_snapshot: dict[str, Any]) -> bool:
    specs = _as_dict(source_snapshot.get("specialists"))
    adv = _as_dict(specs.get("adversary_check"))
    reasons = adv.get("reasons") or []
    if isinstance(reasons, list) and any(
        isinstance(r, str) and (r or "").strip() for r in reasons
    ):
        return True
    d = _f(adv.get("dissent_score_0_1"))
    return d is not None and d >= CONSERVATIVE_SPECIALIST_DISSENT_0_1


def extract_risk_account_snapshot(source_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Liest risk_account_snapshot aus source_snapshot_json; fehlende Keys = kein hartes Gate."""
    if not isinstance(source_snapshot, dict):
        return {}
    raw = source_snapshot.get("risk_account_snapshot")
    return _as_dict(raw)


def _classify_quality_tier(
    *,
    settings: Any,
    signal_row: dict[str, Any],
    source_snapshot: dict[str, Any],
    primary_tf: dict[str, Any],
) -> tuple[QualityTier, list[str]]:
    notes: list[str] = []
    qg = _as_dict(source_snapshot.get("quality_gate"))
    data_issues = list(source_snapshot.get("data_issues") or [])
    if qg.get("passed") is False or data_issues:
        notes.append("tier_driver_data_quality")
        return "C", notes

    ood = _f(signal_row.get("model_ood_score_0_1"))
    if ood is not None and ood >= 0.42:
        notes.append("tier_driver_ood")
        return "B", notes

    unc = _f(signal_row.get("model_uncertainty_0_1"))
    if unc is not None and unc >= 0.40:
        notes.append("tier_driver_uncertainty")
        return "B", notes

    regime = str(signal_row.get("market_regime") or "").strip().lower()
    regime_state = str(signal_row.get("regime_state") or "").strip().lower() or regime
    rconf = _f(signal_row.get("regime_confidence_0_1")) or 0.0
    fragile = (
        regime_state
        in {
            "shock",
            "low_liquidity",
            "delivery_sensitive",
            "news_driven",
            "mean_reverting",
            "range_grind",
        }
        and rconf < 0.38
    ) or (regime in {"chop", "dislocation"} and rconf < 0.38)
    if fragile:
        notes.append("tier_driver_fragile_regime")
        return "D", notes

    spread = _f(primary_tf.get("spread_bps"))
    smax = float(settings.signal_max_spread_bps)
    if spread is not None and spread > smax * 0.92:
        notes.append("tier_driver_spread")
        return "B", notes

    depth = _f(primary_tf.get("depth_to_bar_volume_ratio"))
    if depth is not None and depth < 0.45:
        notes.append("tier_driver_liquidity")
        return "B", notes

    return "A", notes


def _tier_base_leverage_cap(tier: QualityTier) -> int:
    return {"A": 75, "B": 35, "C": 14, "D": 7}[tier]


def _tier_exposure_fraction(tier: QualityTier) -> float:
    return {"A": 1.0, "B": 0.65, "C": 0.35, "D": 0.20}[tier]


def assess_risk_governor(
    *,
    settings: Any,
    signal_row: dict[str, Any],
    direction: str,
) -> dict[str, Any]:
    """
    Erzeugt Risk-Entscheidung ohne Seiteneffekte.
    `trade_action_recommendation` ist nur Vorschlag; Hybrid setzt final trade_action.
    """
    product_family = market_family_from_signal_row(signal_row)
    source_snapshot = _as_dict(signal_row.get("source_snapshot_json"))
    feature_snapshot = _as_dict(source_snapshot.get("feature_snapshot"))
    primary_tf = _as_dict(feature_snapshot.get("primary_tf"))
    acct = extract_risk_account_snapshot(source_snapshot)
    instrument_snap = _as_dict(source_snapshot.get("instrument"))
    maint_rate = maintenance_margin_rate_from_instrument(instrument_snap)

    live_only = bool(getattr(settings, "risk_governor_account_stress_live_only", True))
    d = direction.strip().lower()
    sides = acct.get("allowed_entry_sides")

    # --- Phase 1a: Konto-/Portfolio-Stress (nur Live, wenn live_only) ---
    live_stress: list[str] = []

    mu = _f(acct.get("margin_utilization_0_1"))
    if mu is not None and mu > float(settings.risk_max_account_margin_usage):
        live_stress.append("risk_governor_margin_utilization_exceeded")

    dd = _f(acct.get("account_drawdown_0_1"))
    if dd is not None and dd > float(settings.risk_max_account_drawdown_pct):
        live_stress.append("risk_governor_account_drawdown_exceeded")

    ddd = _f(acct.get("daily_drawdown_0_1"))
    if ddd is not None and ddd > float(settings.risk_max_daily_drawdown_pct):
        live_stress.append("risk_governor_daily_drawdown_exceeded")

    ddw = _f(acct.get("weekly_drawdown_0_1"))
    if ddw is not None and ddw > float(settings.risk_max_weekly_drawdown_pct):
        live_stress.append("risk_governor_weekly_drawdown_exceeded")

    dloss = _f(acct.get("daily_realized_loss_usdt"))
    if dloss is not None and dloss > float(settings.risk_max_daily_loss_usdt):
        live_stress.append("risk_governor_daily_loss_usd_exceeded")

    streak = _i(acct.get("consecutive_losses"))
    streak_max = int(settings.risk_governor_loss_streak_max)
    if streak is not None and streak >= streak_max:
        live_stress.append("risk_governor_loss_streak_exceeded")

    corr = _f(acct.get("portfolio_correlation_stress_0_1"))
    corr_lim = float(settings.risk_governor_correlation_stress_abstain)
    if corr is not None and corr >= corr_lim:
        live_stress.append("risk_governor_correlation_stress_high")

    pos_n = _i(acct.get("open_positions_count"))
    if pos_n is not None and pos_n >= int(settings.risk_max_concurrent_positions):
        live_stress.append("risk_governor_max_concurrent_positions")

    gross = _f(acct.get("gross_exposure_ratio_0_1"))
    if gross is not None and gross >= 0.92:
        live_stress.append("risk_governor_gross_exposure_critical")

    lpr = _f(acct.get("largest_position_risk_to_equity_0_1"))
    lim_lpr = float(getattr(settings, "risk_portfolio_live_max_largest_position_risk_0_1", 0.22))
    if lpr is not None and lpr > lim_lpr:
        live_stress.append("risk_governor_largest_position_risk_exceeded")

    if isinstance(sides, list) and d in {"long", "short"}:
        flat = [str(x).strip().lower() for x in sides if isinstance(x, str)]
        if flat and d not in flat:
            live_stress.append("risk_governor_side_not_permitted_by_account_policy")

    smc_snap = source_snapshot.get("structured_market_context")
    if isinstance(smc_snap, dict):
        for tag in smc_snap.get("live_execution_block_reasons_json") or []:
            if isinstance(tag, str) and tag.strip():
                t = tag.strip()
                if t not in live_stress:
                    live_stress.append(t)

    # --- Phase 1b: signalweite Hard-Blocks ---
    universal: list[str] = []
    unc_phase = str(signal_row.get("uncertainty_gate_phase") or "").strip().lower()
    if unc_phase == "blocked":
        universal.append("risk_governor_uncertainty_phase_blocked")

    specialist_ensemble_disagreement = _specialist_ensemble_disagreement(source_snapshot)
    if specialist_ensemble_disagreement:
        universal.append("risk_governor_specialist_ensemble_disagreement")
    # Ohne 1:1-Hebel in Futures (min. Konfig-Hebel 7x): statt 1x-Klemme -> Abstinenz
    u0 = _f(signal_row.get("model_uncertainty_0_1"))
    if (
        not specialist_ensemble_disagreement
        and u0 is not None
        and u0 >= CONSERVATIVE_ELEVATED_UNCERTAINTY_LEV1_0_1
    ):
        universal.append("risk_governor_elevated_market_uncertainty")

    if product_family == "margin" and maint_rate is not None:
        halt_thr = float(
            getattr(settings, "risk_margin_mmr_halt_threshold_0_1", 0.20),
        )
        if maint_rate > halt_thr:
            universal.append("risk_governor_margin_maintenance_margin_rate_too_high")

    exch_ok = acct.get("exchange_health_ok")
    if exch_ok is False:
        universal.append("risk_governor_exchange_health_bad")

    inf_gov = source_snapshot.get("inference_governance")
    if (
        isinstance(inf_gov, dict)
        and str(inf_gov.get("state") or "").strip() == "INFERENCE_TIMEOUT"
    ):
        universal.append("INFERENCE_TIMEOUT")

    m_anom = _f(signal_row.get("market_anomaly_confidence_0_1"))
    if m_anom is not None and m_anom > RISK_GOVERNOR_MARKET_ANOMALY_HALT_0_1:
        universal.append("risk_governor_market_anomaly_confidence_high")

    vpin_m = _vpin_0_1_from_primary_tf(primary_tf)
    if vpin_m is not None and vpin_m > VPIN_HARD_HALT_THRESHOLD_0_1:
        universal.append("RISK_VPIN_HALT")

    struct_live = assess_portfolio_structural_live_blocks(
        settings=settings,
        acct=acct,
        signal_row=signal_row,
    )
    live_execution: list[str] = []
    for bucket in (live_stress, struct_live):
        for tag in bucket:
            if tag not in live_execution:
                live_execution.append(tag)

    if live_only:
        hard = list(universal)
    else:
        hard = list(universal) + list(live_execution)

    if product_family == "spot" and bool(acct.get("insufficient_balance")) is True:
        if getattr(settings, "risk_spot_balance_check_enabled", True):
            hard.append("risk_governor_spot_insufficient_balance")
    if product_family == "spot" and not bool(acct.get("insufficient_balance", False)):
        sa = _f(acct.get("spot_quote_available_usdt"))
        need = _f(
            acct.get("proposed_notional_usdt")
            or signal_row.get("proposed_notional_usdt"),
        )
        if (
            getattr(settings, "risk_spot_balance_check_enabled", True)
            and sa is not None
            and need is not None
            and need > sa
        ):
            hard.append("risk_governor_spot_notional_exceeds_wallet")

    # --- Phase 2: Exposure-Tier ---
    tier, tier_notes = _classify_quality_tier(
        settings=settings,
        signal_row=signal_row,
        source_snapshot=source_snapshot,
        primary_tf=primary_tf,
    )
    max_exposure_fraction = _tier_exposure_fraction(tier)
    if (
        vpin_m is not None
        and vpin_m > VPIN_ORDER_SIZE_REDUCE_THRESHOLD_0_1
        and vpin_m <= VPIN_HARD_HALT_THRESHOLD_0_1
    ):
        max_exposure_fraction = max(0.0, max_exposure_fraction * 0.5)

    # --- Phase 3: Hebel-Obergrenze (Matrix + Mikro-Gates) ---
    cap = _tier_base_leverage_cap(tier)

    unc = _f(signal_row.get("model_uncertainty_0_1"))
    if unc is not None:
        if unc >= 0.62:
            cap = min(cap, 10)
        elif unc >= 0.48:
            cap = min(cap, 18)

    ood = _f(signal_row.get("model_ood_score_0_1"))
    ood_alert = bool(signal_row.get("model_ood_alert"))
    if ood_alert:
        cap = min(cap, 10)
    elif ood is not None:
        if ood >= 0.72:
            cap = min(cap, 10)
        elif ood >= 0.52:
            cap = min(cap, 16)

    spread = _f(primary_tf.get("spread_bps"))
    smax = float(settings.signal_max_spread_bps)
    if spread is not None and spread > smax * 0.85:
        cap = min(cap, 12)

    if _as_dict(source_snapshot.get("quality_gate")).get("passed") is False:
        cap = min(cap, 7)
    if list(source_snapshot.get("data_issues") or []):
        cap = min(cap, 10)

    liq_src = str(primary_tf.get("liquidity_source") or "").strip().lower()
    if liq_src and liq_src != "orderbook_levels":
        cap = min(cap, 14)

    depth = _f(primary_tf.get("depth_to_bar_volume_ratio"))
    if depth is not None and depth < float(settings.leverage_signal_min_depth_ratio) * 0.75:
        cap = min(cap, 10)

    # --- Resilience: Volatility Clamp (ATR vs. 24h-EMA, Prompt 73) ---
    risk_volatility_clamp_active = False
    governor_bff_risk_flags_json: list[str] = []
    cap_before_vol = cap
    p_atr = _f(primary_tf.get("atrp_14"))
    p_ema = _f(primary_tf.get("atrp_14_ema_24h"))
    if p_ema is None:
        p_ema = _f(signal_row.get("atrp_14_ema_24h"))
    if p_atr is not None and p_atr > 0 and product_family != "spot":
        atr_now_pct = float(p_atr) * 100.0
        ema_pct = (float(p_ema) * 100.0) if p_ema is not None and p_ema > 0 else None
        eff_atr = effective_atr_percent_for_volatility_clamp(
            atr_percent=atr_now_pct, atr_ema_24h_percent=ema_pct
        )
        sys_max = int(
            max(1, int(getattr(settings, "risk_allowed_leverage_max", 75) or 75))
        )
        v_cap = adaptive_leverage_cap_from_atr_percent(
            eff_atr, system_max_leverage=sys_max
        )
        cap = min(cap, v_cap)
        if cap < cap_before_vol and v_cap <= cap_before_vol:
            risk_volatility_clamp_active = True
            if RISK_VOLATILITY_CLAMP_ACTIVE not in governor_bff_risk_flags_json:
                governor_bff_risk_flags_json.append(RISK_VOLATILITY_CLAMP_ACTIVE)
            tier_notes.append("RISK_VOLATILITY_CLAMP_ACTIVE")

    if _execution_mode_str(settings) == "live" and product_family != "spot":
        rmax = _live_ramp_max_leverage(settings)
        if cap > rmax:
            tier_notes.append("live_ramp_max_baked_into_governor_cap")
        cap = min(cap, rmax)

    if product_family == "spot":
        cap = 1
        tier_notes.append("spot_cash_no_leverage_governor_max_1x")
    else:
        cap = _clamp_leverage(cap)

    allowed_side: AllowedSide
    if universal:
        allowed_side = "none"
    elif d in {"long", "short"}:
        allowed_side = "both"
    else:
        allowed_side = "none"

    direction_permitted = d in {"long", "short"} and allowed_side != "none"
    if isinstance(sides, list) and d in {"long", "short"} and not live_only:
        flat = [str(x).strip().lower() for x in sides if isinstance(x, str)]
        if flat and d not in flat:
            direction_permitted = False

    trade_action_recommendation = "do_not_trade" if hard or not direction_permitted else "allow_trade"

    exit_strategies, emergency = _exit_and_emergency(
        tier=tier,
        hard_blocked=bool(universal),
        settings=settings,
    )

    pr = extract_portfolio_risk(acct)
    synthesis = build_portfolio_synthesis(
        acct=acct,
        pr=pr,
        signal_row=signal_row,
        portfolio_live_reasons=struct_live,
        account_stress_live_reasons=live_stress,
    )

    mmr_halt = (
        product_family == "margin"
        and maint_rate is not None
        and maint_rate
        > float(getattr(settings, "risk_margin_mmr_halt_threshold_0_1", 0.20))
    )
    return {
        "version": RISK_GOVERNOR_VERSION,
        "phase_order_de": list(GOVERNOR_PHASE_ORDER_DE),
        "market_family": product_family,
        "maintenance_margin_rate_0_1": maint_rate,
        "maintenance_margin_signoff": "halt" if mmr_halt else "ok",
        "hard_block_reasons_json": hard,
        "universal_hard_block_reasons_json": universal,
        "live_execution_block_reasons_json": live_execution,
        "portfolio_risk_synthesis_json": synthesis,
        "risk_governor_account_stress_live_only": live_only,
        "trade_action_recommendation": trade_action_recommendation,
        "allowed_side": allowed_side,
        "direction_permitted": direction_permitted,
        "max_exposure_fraction_0_1": max_exposure_fraction,
        "quality_tier": tier,
        "quality_tier_notes_json": tier_notes,
        "max_leverage_cap": cap,
        "risk_volatility_clamp_active": risk_volatility_clamp_active,
        "governor_bff_risk_flags_json": governor_bff_risk_flags_json,
        "exit_strategies_allowed_json": exit_strategies,
        "emergency_rules_json": emergency,
        "account_snapshot_echo_json": {k: acct.get(k) for k in sorted(acct.keys())} if acct else {},
    }


def _exit_and_emergency(
    *,
    tier: QualityTier,
    hard_blocked: bool,
    settings: Any,
) -> tuple[list[str], dict[str, Any]]:
    if hard_blocked or tier == "D":
        exits = ["stop_mandatory", "reduce_only_flat_on_alert"]
    elif tier == "C":
        exits = ["stop_mandatory", "target_ladder", "time_stop_short"]
    else:
        exits = ["stop_mandatory", "target_ladder", "time_stop_optional", "trail_after_be_optional"]

    emergency = {
        "flatten_on_margin_critical": True,
        "cancel_new_entries_on_exchange_degraded": True,
        "force_reduce_only_on_risk_alert": bool(settings.risk_force_reduce_only_on_alert),
        "halt_on_uncertainty_blocked_phase": True,
    }
    return exits, emergency


def leverage_escalation_ok(signal_row: dict[str, Any], governor: dict[str, Any]) -> bool:
    """Explizite Freigabe + messbare Stabilitaet (Snapshot), sonst Live-Ramp 7."""
    snap = extract_risk_account_snapshot(_as_dict(signal_row.get("source_snapshot_json")))
    approved = bool(snap.get("leverage_escalation_approved"))
    stable = bool(snap.get("measurably_stable_for_escalation"))
    return approved and stable


def apply_live_ramp_cap(
    *,
    settings: Any,
    meta_trade_lane: str,
    allowed_leverage: int,
    recommended_leverage: int | None,
    signal_row: dict[str, Any],
    governor: dict[str, Any],
) -> tuple[int, int | None]:
    """
    Live-Ramp: RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE vs. EXECUTION_MODE.

    execution_mode=live: Hebel nie ueber Ramp-Cap (Eskalation nur ausserhalb live).
    Sonst: Kandidaten-Lane + Eskalation wie bisher.
    """
    ramp = _live_ramp_max_leverage(settings)
    live = _execution_mode_str(settings) == "live"
    a0 = int(allowed_leverage)
    r0: int | None
    r0 = int(recommended_leverage) if recommended_leverage is not None else None

    if live:
        new_allowed = min(a0, ramp)
        new_rec: int | None = None if r0 is None else min(r0, ramp)
        if a0 > ramp or (r0 is not None and r0 > ramp):
            mlane = str(meta_trade_lane or "").strip().lower() or None
            logger.info(
                "%s prior_allowed=%s prior_recommended=%s ramp_cap=%s meta_lane=%s",
                RISK_RAMP_CAP_ENFORCED_EVENT,
                a0,
                r0,
                ramp,
                mlane,
                extra={
                    "event": RISK_RAMP_CAP_ENFORCED_EVENT,
                    "execution_mode": "live",
                    "prior_allowed": a0,
                    "prior_recommended": r0,
                    "ramp_cap": ramp,
                    "meta_trade_lane": mlane,
                },
            )
        return new_allowed, new_rec

    lane = str(meta_trade_lane or "").strip().lower()
    if lane != "candidate_for_live":
        return a0, r0
    if leverage_escalation_ok(signal_row, governor):
        return a0, r0
    new_a = min(a0, ramp)
    new_r = None if r0 is None else min(r0, ramp)
    return new_a, new_r
