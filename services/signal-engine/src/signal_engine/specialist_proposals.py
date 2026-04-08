"""
Deterministische Spezialisten-Vorschlaege + Gegnercheck fuer das Ensemble-Routing.

Alle Werte sind aus signal_row, Instrument und Primary-Features ableitbar — keine LLMs.
"""

from __future__ import annotations

from typing import Any

from shared_py.bitget.instruments import BitgetInstrumentIdentity
from shared_py.playbook_registry import PlaybookDefinition, get_playbook
from shared_py.specialist_ensemble_contract import (
    ENSEMBLE_ADVERSARY_VERSION,
    SpecialistProposalV1,
    clamp01,
    empty_proposal,
)

_BASE_SPECIALIST_ID = "ensemble:base_scoring_v1"

# Gewichte fuer Richtungsabstimmung (Summe beliebig; nur relative Groessenordnung)
_WEIGHT_BASE = 1.0
_WEIGHT_FAMILY = 0.82
_WEIGHT_PRODUCT_MARGIN = 0.78
_WEIGHT_LIQVOL = 0.88
_WEIGHT_REGIME = 0.96
_WEIGHT_PLAYBOOK = 0.9
_WEIGHT_SYMBOL_ACTIVE = 0.52
_WEIGHT_SYMBOL_CLUSTER = 0.32

_OOD_HARD_SCORE = 0.82
_DISSENT_MIN_CAMP = 0.2
_DISSENT_RATIO_TRIGGER = 0.58
_EDGE_DISPERSION_BPS_TRIGGER = 52.0
_THREE_WAY_CAMP_MIN = 0.16


def finalize_proposal_audit_fields(
    p: SpecialistProposalV1,
    *,
    signal_row: dict[str, Any],
) -> SpecialistProposalV1:
    mae = _coerce_float(signal_row.get("expected_mae_bps"))
    mfe = _coerce_float(signal_row.get("expected_mfe_bps"))
    if mae is not None:
        p["expected_mae_bps"] = mae
    if mfe is not None:
        p["expected_mfe_bps"] = mfe
    p["stop_budget_hint_0_1"] = clamp01(float(p.get("stop_budget_0_1") or 0.5))
    lb = p.get("leverage_band")
    if isinstance(lb, dict):
        p["leverage_band_hint"] = {
            "min_fraction_0_1": clamp01(float(lb.get("min_fraction_0_1") or 0.0)),
            "max_fraction_0_1": clamp01(float(lb.get("max_fraction_0_1") or 1.0)),
        }
    return p


def _symbol_expert_data_sufficient(
    primary_feature: dict[str, Any],
) -> tuple[bool, list[str]]:
    issues: list[str] = []
    fq = str(primary_feature.get("feature_quality_status") or "").strip().lower()
    if fq and fq != "ok":
        issues.append("feature_quality_not_ok")
    dc = _coerce_float(primary_feature.get("data_completeness_0_1"))
    if dc is None or dc < 0.82:
        issues.append("data_completeness_below_symbol_threshold")
    st = _coerce_float(primary_feature.get("staleness_score_0_1"))
    if st is not None and st > 0.48:
        issues.append("staleness_too_high_for_symbol_expert")
    aux = primary_feature.get("auxiliary_inputs")
    if isinstance(aux, dict):
        ptm = str(aux.get("pipeline_trade_mode") or "").strip().lower()
        if ptm == "do_not_trade":
            issues.append("pipeline_trade_mode_do_not_trade")
    return (len(issues) == 0), issues


def _liquidity_vol_cluster_key(primary_feature: dict[str, Any]) -> str:
    spread = _coerce_float(primary_feature.get("spread_bps"))
    rv = _coerce_float(primary_feature.get("realized_vol_cluster_0_100"))
    ec = _coerce_float(primary_feature.get("execution_cost_bps"))
    if spread is not None and spread > 18.0:
        sp = "wide_spread"
    elif spread is not None and spread <= 5.0:
        sp = "tight_spread"
    else:
        sp = "mid_spread"
    if rv is not None and rv >= 62.0:
        rvb = "high_rv_cluster"
    elif rv is not None and rv <= 38.0:
        rvb = "low_rv_cluster"
    else:
        rvb = "mid_rv_cluster"
    cost = "cost_stress" if ec is not None and ec > 25.0 else "cost_ok"
    return f"{sp}_{rvb}_{cost}"


def build_product_margin_proposal(
    *,
    signal_row: dict[str, Any],
    instrument: BitgetInstrumentIdentity,
) -> SpecialistProposalV1:
    fam = instrument.market_family
    pt = instrument.product_type or "none"
    mam = instrument.margin_account_mode
    sid = f"product_margin:{fam}:{pt}:{mam}"
    p = empty_proposal(role="product_margin", specialist_id=sid)
    sig_dir = str(signal_row.get("direction") or "").strip().lower()
    if sig_dir not in ("long", "short"):
        sig_dir = "neutral"
    if fam == "spot" and sig_dir == "short":
        sig_dir = "neutral"
    p["direction"] = sig_dir  # type: ignore[assignment]
    p["no_trade_probability_0_1"] = 0.2 if fam == "futures" else 0.24
    edge = _coerce_float(signal_row.get("expected_return_bps"))
    if edge is not None:
        adj = 0.0
        if fam == "margin" and mam == "crossed":
            adj -= 3.0
            p["reasons"].append("product_margin_crossed_edge_discount")
        elif fam == "margin" and mam == "isolated":
            adj -= 1.5
            p["reasons"].append("product_margin_isolated_edge_discount")
        p["expected_edge_bps"] = edge + adj
    if fam == "spot":
        p["stop_budget_0_1"] = 0.53
        p["leverage_band"] = {"min_fraction_0_1": 0.15, "max_fraction_0_1": 0.72}
    elif fam == "margin":
        p["stop_budget_0_1"] = 0.48 if mam == "crossed" else 0.5
        p["leverage_band"] = (
            {"min_fraction_0_1": 0.22, "max_fraction_0_1": 0.82}
            if mam == "crossed"
            else {"min_fraction_0_1": 0.32, "max_fraction_0_1": 0.9}
        )
        p["reasons"].append(f"product_margin_mode:{mam}")
    else:
        p["stop_budget_0_1"] = 0.44
        p["leverage_band"] = {"min_fraction_0_1": 0.38, "max_fraction_0_1": 1.0}
    mu = _coerce_float(signal_row.get("model_uncertainty_0_1")) or 0.48
    p["uncertainty_0_1"] = clamp01(mu)
    p["exit_families_ranked"] = ["scale_out", "liquidity_target", "time_stop"]
    p["exit_family_primary"] = "scale_out"
    p["reasons"].append("product_margin_lane")
    return finalize_proposal_audit_fields(p, signal_row=signal_row)


def build_liquidity_vol_cluster_proposal(
    *,
    signal_row: dict[str, Any],
    primary_feature: dict[str, Any],
) -> SpecialistProposalV1:
    ckey = _liquidity_vol_cluster_key(primary_feature)
    p = empty_proposal(role="liquidity_vol_cluster", specialist_id=f"liqvol:{ckey}")
    sig_dir = str(signal_row.get("direction") or "").strip().lower()
    p["direction"] = sig_dir if sig_dir in ("long", "short") else "neutral"  # type: ignore[assignment]
    spread = _coerce_float(primary_feature.get("spread_bps"))
    st = _coerce_float(primary_feature.get("staleness_score_0_1"))
    dc = _coerce_float(primary_feature.get("data_completeness_0_1"))
    ntp = 0.28
    if spread is not None and spread > 22.0:
        ntp += 0.34
        p["reasons"].append("liqvol_wide_spread_abstain")
    if st is not None and st > 0.42:
        ntp += 0.22
        p["reasons"].append("liqvol_stale_microstructure")
    if dc is not None and dc < 0.78:
        ntp += 0.2
        p["reasons"].append("liqvol_low_completeness")
    p["no_trade_probability_0_1"] = clamp01(ntp)
    p["expected_edge_bps"] = _coerce_float(signal_row.get("expected_return_bps"))
    if p["expected_edge_bps"] is not None and spread is not None and spread > 15.0:
        ee = float(p["expected_edge_bps"])
        p["expected_edge_bps"] = ee - min(18.0, spread * 0.35)
        p["reasons"].append("liqvol_edge_cost_adjusted")
    p["stop_budget_0_1"] = 0.42 if (spread or 0) > 14 else 0.52
    unc = 0.35 + (st or 0.0) * 0.85 + (1.0 - (dc or 0.8)) * 0.4
    p["uncertainty_0_1"] = clamp01(unc)
    p["exit_family_primary"] = "liquidity_target"
    p["exit_families_ranked"] = ["liquidity_target", "scale_out", "time_stop"]
    p["reasons"].append(f"liqvol_cluster:{ckey}")
    return finalize_proposal_audit_fields(p, signal_row=signal_row)


def build_symbol_specialist_proposal(
    *,
    signal_row: dict[str, Any],
    instrument: BitgetInstrumentIdentity,
    primary_feature: dict[str, Any],
) -> tuple[SpecialistProposalV1, str]:
    ok, issues = _symbol_expert_data_sufficient(primary_feature)
    if ok:
        p = empty_proposal(role="symbol", specialist_id=f"symbol:{instrument.symbol}")
        mode = "symbol_active"
        sig_dir = str(signal_row.get("direction") or "").strip().lower()
        p["direction"] = sig_dir if sig_dir in ("long", "short") else "neutral"  # type: ignore[assignment]
        mu_sym = _coerce_float(signal_row.get("model_uncertainty_0_1")) or 0.35
        p["no_trade_probability_0_1"] = clamp01(0.15 + mu_sym * 0.45)
        p["expected_edge_bps"] = _coerce_float(signal_row.get("expected_return_bps"))
        p["reasons"].append("symbol_expert_data_sufficient")
    else:
        p = empty_proposal(
            role="symbol",
            specialist_id=f"cluster:family_xs:{instrument.market_family}",
            reasons=[f"symbol_deferred:{item}" for item in issues],
        )
        mode = "cluster_family_cross_section"
        p["direction"] = "neutral"  # type: ignore[assignment]
        p["no_trade_probability_0_1"] = clamp01(0.62 + len(issues) * 0.06)
        p["expected_edge_bps"] = None
        p["reasons"].append("symbol_expert_deferred_to_family_cluster")
    p["stop_budget_0_1"] = 0.5
    p["leverage_band"] = {"min_fraction_0_1": 0.3, "max_fraction_0_1": 0.95}
    mu2 = _coerce_float(signal_row.get("model_uncertainty_0_1")) or 0.55
    p["uncertainty_0_1"] = clamp01(mu2)
    return finalize_proposal_audit_fields(p, signal_row=signal_row), mode


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_base_model_proposal(*, signal_row: dict[str, Any]) -> SpecialistProposalV1:
    p = empty_proposal(role="base", specialist_id=_BASE_SPECIALIST_ID)
    direction = str(signal_row.get("direction") or "").strip().lower()
    if direction not in ("long", "short"):
        direction = "neutral"
    p["direction"] = direction  # type: ignore[assignment]
    decision_conf = _coerce_float(signal_row.get("decision_confidence_0_1")) or 0.55
    rejection = bool(signal_row.get("rejection_state"))
    dstate = str(signal_row.get("decision_state") or "").strip().lower()
    if rejection or dstate == "rejected":
        p["no_trade_probability_0_1"] = 0.98
        p["reasons"].append("base_rejection_or_rejected_state")
    elif dstate == "downgraded":
        p["no_trade_probability_0_1"] = clamp01(0.55 + (1.0 - decision_conf) * 0.35)
        p["reasons"].append("base_downgraded_decision_state")
    else:
        p["no_trade_probability_0_1"] = clamp01(1.0 - decision_conf)
        p["reasons"].append("base_from_decision_confidence")
    p["expected_edge_bps"] = _coerce_float(signal_row.get("expected_return_bps"))
    if p["expected_edge_bps"] is None:
        comp = _coerce_float(signal_row.get("weighted_composite_score_0_100")) or 0.0
        p["expected_edge_bps"] = round((comp / 100.0) * 28.0 - 8.0, 4)
        p["reasons"].append("base_edge_from_composite_proxy")
    rr = _coerce_float(signal_row.get("reward_risk_ratio"))
    if rr is not None and rr > 0:
        p["stop_budget_0_1"] = clamp01(min(1.0, rr / 2.8))
        p["reasons"].append("stop_budget_from_reward_risk")
    else:
        p["stop_budget_0_1"] = 0.48
    p["uncertainty_0_1"] = clamp01(_coerce_float(signal_row.get("model_uncertainty_0_1")) or 0.5)
    allowed = _coerce_float(signal_row.get("allowed_leverage"))
    if allowed is not None and allowed > 0:
        rec = _coerce_float(signal_row.get("recommended_leverage"))
        if rec is not None and rec > 0:
            p["leverage_band"] = {
                "min_fraction_0_1": clamp01(rec / allowed * 0.65),
                "max_fraction_0_1": 1.0,
            }
        else:
            p["leverage_band"] = {"min_fraction_0_1": 0.35, "max_fraction_0_1": 1.0}
        p["reasons"].append("leverage_band_from_engine_caps")
    playbook = get_playbook(str(signal_row.get("playbook_id") or "").strip() or None)
    if playbook and playbook.exit_families:
        p["exit_families_ranked"] = list(playbook.exit_families)
        p["exit_family_primary"] = playbook.exit_families[0]
        p["reasons"].append("base_exit_from_playbook_registry")
    else:
        p["exit_families_ranked"] = ["scale_out", "runner", "time_stop"]
        p["exit_family_primary"] = "scale_out"
        p["reasons"].append("base_exit_default_playbookless")
    return finalize_proposal_audit_fields(p, signal_row=signal_row)


def build_family_proposal(
    *,
    signal_row: dict[str, Any],
    instrument: BitgetInstrumentIdentity,
    family_blockers: list[str],
) -> SpecialistProposalV1:
    p = empty_proposal(role="family", specialist_id=f"family:{instrument.market_family}")
    direction = str(signal_row.get("direction") or "").strip().lower()
    if direction not in ("long", "short"):
        direction = "neutral"
    if instrument.market_family == "spot" and direction == "short":
        direction = "neutral"
    p["direction"] = direction  # type: ignore[assignment]
    if family_blockers:
        p["no_trade_probability_0_1"] = 0.96
        p["reasons"].extend(f"family_blocker:{b}" for b in family_blockers)
    else:
        p["no_trade_probability_0_1"] = 0.12
        p["reasons"].append("family_no_hard_blocker")
    edge = _coerce_float(signal_row.get("expected_return_bps"))
    if edge is not None:
        penalty = 0.0
        if instrument.market_family == "margin":
            penalty = 4.0
        elif instrument.market_family == "spot":
            penalty = 2.0
        p["expected_edge_bps"] = edge - penalty
        if penalty:
            p["reasons"].append(f"family_edge_penalty_bps_{penalty:g}")
    if instrument.market_family == "spot":
        p["stop_budget_0_1"] = 0.52
        p["leverage_band"] = {"min_fraction_0_1": 0.2, "max_fraction_0_1": 0.75}
    elif instrument.market_family == "margin":
        p["stop_budget_0_1"] = 0.5
        p["leverage_band"] = {"min_fraction_0_1": 0.35, "max_fraction_0_1": 0.92}
    else:
        p["stop_budget_0_1"] = 0.45
        p["leverage_band"] = {"min_fraction_0_1": 0.4, "max_fraction_0_1": 1.0}
    p["uncertainty_0_1"] = clamp01(_coerce_float(signal_row.get("model_uncertainty_0_1")) or 0.5)
    p["exit_family_primary"] = "liquidity_target" if instrument.market_family == "spot" else None
    return finalize_proposal_audit_fields(p, signal_row=signal_row)


def build_regime_proposal(*, signal_row: dict[str, Any]) -> SpecialistProposalV1:
    regime_state = str(signal_row.get("regime_state") or "").strip().lower() or str(
        signal_row.get("market_regime") or ""
    ).strip().lower()
    p = empty_proposal(role="regime", specialist_id=f"regime:{regime_state or 'unknown'}")
    bias = str(signal_row.get("regime_bias") or "").strip().lower()
    sig_dir = str(signal_row.get("direction") or "").strip().lower()
    if bias in ("long", "short"):
        p["direction"] = bias  # type: ignore[assignment]
    elif sig_dir in ("long", "short"):
        p["direction"] = sig_dir  # type: ignore[assignment]
    rc = _coerce_float(signal_row.get("regime_confidence_0_1")) or 0.0
    if sig_dir in ("long", "short") and bias in ("long", "short") and bias != sig_dir and rc >= 0.58:
        p["no_trade_probability_0_1"] = clamp01(0.42 + rc * 0.45)
        p["reasons"].append("regime_bias_conflicts_with_signal_direction")
    elif regime_state in {"shock", "low_liquidity", "delivery_sensitive"}:
        p["no_trade_probability_0_1"] = clamp01(0.72 + (1.0 - rc) * 0.2)
        p["reasons"].append(f"regime_fragile_state:{regime_state}")
    else:
        p["no_trade_probability_0_1"] = clamp01(0.18 + (1.0 - rc) * 0.35)
        p["reasons"].append("regime_default_no_trade_from_confidence")
    p["uncertainty_0_1"] = clamp01(0.25 + (1.0 - rc) * 0.55)
    p["expected_edge_bps"] = _coerce_float(signal_row.get("expected_return_bps"))
    if regime_state == "mean_reverting":
        p["exit_family_primary"] = "mean_reversion_unwind"
        p["exit_families_ranked"] = ["mean_reversion_unwind", "time_stop", "scale_out"]
        p["reasons"].append("regime_exit_hint_mean_reversion")
    elif regime_state in {"trend", "expansion"}:
        p["exit_family_primary"] = "trend_follow_runner"
        p["exit_families_ranked"] = ["trend_follow_runner", "trend_hold", "scale_out", "runner"]
        p["reasons"].append("regime_exit_hint_trend")
    elif regime_state == "compression":
        p["exit_family_primary"] = "event_exit"
        p["exit_families_ranked"] = ["event_exit", "scale_out"]
        p["reasons"].append("regime_exit_hint_compression")
    p["stop_budget_0_1"] = 0.46 if regime_state in {"shock", "dislocation", "low_liquidity"} else 0.5
    return finalize_proposal_audit_fields(p, signal_row=signal_row)


def build_playbook_proposal(
    *,
    signal_row: dict[str, Any],
    playbook_id: str | None,
    playbook_family: str | None,
    playbook_decision_mode: str,
    selection_score: float,
    exit_families: list[str],
) -> SpecialistProposalV1:
    pid = playbook_id or "playbookless"
    p = empty_proposal(role="playbook", specialist_id=f"playbook:{pid}")
    sig_dir = str(signal_row.get("direction") or "").strip().lower()
    p["direction"] = sig_dir if sig_dir in ("long", "short") else "neutral"  # type: ignore[assignment]
    if playbook_decision_mode == "playbookless" or not playbook_family:
        p["no_trade_probability_0_1"] = 0.88
        p["reasons"].append("playbookless_high_abstention_prior")
    else:
        p["no_trade_probability_0_1"] = clamp01(0.22 + (1.0 - clamp01(selection_score)) * 0.62)
        p["reasons"].append("playbook_score_to_no_trade")
    p["expected_edge_bps"] = round(clamp01(selection_score) * 42.0 - 6.0, 4)
    p["exit_families_ranked"] = list(exit_families)
    p["exit_family_primary"] = exit_families[0] if exit_families else None
    p["uncertainty_0_1"] = clamp01(0.35 + (1.0 - clamp01(selection_score)) * 0.5)
    p["stop_budget_0_1"] = 0.44 if playbook_family in {"breakout", "trend_continuation"} else 0.52
    return finalize_proposal_audit_fields(p, signal_row=signal_row)


def run_adversary_check(
    *,
    proposals: list[SpecialistProposalV1],
    signal_row: dict[str, Any],
    playbook: PlaybookDefinition | None = None,
    primary_feature: dict[str, Any] | None = None,
) -> dict[str, Any]:
    primary_feature = primary_feature or {}
    ood = _coerce_float(signal_row.get("model_ood_score_0_1")) or 0.0
    ood_alert = bool(signal_row.get("model_ood_alert"))
    reasons: list[str] = []
    signal_dir = str(signal_row.get("direction") or "").strip().lower()
    regime_bias = str(signal_row.get("regime_bias") or "").strip().lower()
    regime_state = str(signal_row.get("regime_state") or "").strip().lower() or str(
        signal_row.get("market_regime") or ""
    ).strip().lower()

    long_s = 0.0
    short_s = 0.0
    neutral_s = 0.0

    for pr in proposals:
        role = pr.get("specialist_role")
        sid = str(pr.get("specialist_id") or "")
        if role == "symbol":
            w = _WEIGHT_SYMBOL_ACTIVE if sid.startswith("symbol:") else _WEIGHT_SYMBOL_CLUSTER
        else:
            w = {
                "base": _WEIGHT_BASE,
                "family": _WEIGHT_FAMILY,
                "product_margin": _WEIGHT_PRODUCT_MARGIN,
                "liquidity_vol_cluster": _WEIGHT_LIQVOL,
                "regime": _WEIGHT_REGIME,
                "playbook": _WEIGHT_PLAYBOOK,
            }.get(str(role), 0.48)
        no_trade_p = clamp01(float(pr.get("no_trade_probability_0_1") or 1.0))
        if role == "regime":
            rc = clamp01(_coerce_float(signal_row.get("regime_confidence_0_1")) or 0.5)
            conviction = clamp01(rc * (1.0 - 0.45 * no_trade_p))
        else:
            conviction = clamp01(1.0 - no_trade_p)
        mass = w * conviction
        if (
            role == "regime"
            and signal_dir in ("long", "short")
            and regime_bias in ("long", "short")
            and regime_bias != signal_dir
        ):
            mass *= 3.0
            reasons.append("adversary_regime_signal_direction_conflict_boost")
        d = str(pr.get("direction") or "neutral").strip().lower()
        if d == "long":
            long_s += mass
        elif d == "short":
            short_s += mass
        else:
            neutral_s += mass

    total_dir = long_s + short_s + 1e-9
    dissent = 0.0
    if long_s >= _DISSENT_MIN_CAMP and short_s >= _DISSENT_MIN_CAMP:
        ratio = min(long_s, short_s) / max(long_s, short_s)
        if ratio >= _DISSENT_RATIO_TRIGGER:
            dissent = clamp01(ratio * 0.92 + 0.14)
            reasons.append("adversary_directional_split")

    total_mass = long_s + short_s + neutral_s + 1e-9
    lc = long_s / total_mass
    sc = short_s / total_mass
    nc = neutral_s / total_mass
    tri_way_veto = (
        lc > _THREE_WAY_CAMP_MIN and sc > _THREE_WAY_CAMP_MIN and nc > _THREE_WAY_CAMP_MIN
    )
    if tri_way_veto:
        reasons.append("adversary_three_way_conviction_split")
        dissent = max(dissent, 0.71)

    edges: list[float] = []
    for pr in proposals:
        e = _coerce_float(pr.get("expected_edge_bps"))
        if e is not None:
            edges.append(float(e))
    edge_dispersion_veto = False
    if len(edges) >= 3:
        span = max(edges) - min(edges)
        if span >= _EDGE_DISPERSION_BPS_TRIGGER:
            edge_dispersion_veto = True
            reasons.append("adversary_edge_dispersion_high")
            dissent = max(dissent, clamp01(0.52 + min(0.35, span / 200.0)))

    regime_mismatch_veto = False
    if playbook is not None:
        suit = list(playbook.regime_suitability or [])
        if suit and regime_state and regime_state not in suit:
            regime_mismatch_veto = True
            reasons.append("adversary_playbook_regime_mismatch")

    playbook_family = str(playbook.playbook_family) if playbook is not None else ""
    confluence = _coerce_float(primary_feature.get("confluence_score_0_100")) or 0.0
    if (
        playbook_family in {"trend_continuation", "pullback"}
        and regime_state in {"compression", "chop", "range_grind"}
        and confluence < 52.0
        and signal_dir in ("long", "short")
    ):
        regime_mismatch_veto = True
        reasons.append("adversary_regime_playbook_style_mismatch")

    ood_escalation = "none"
    if ood_alert:
        ood_escalation = "hard_veto"
        reasons.append("adversary_ood_alert")
    elif ood >= _OOD_HARD_SCORE:
        ood_escalation = "hard_veto"
        reasons.append("adversary_ood_score_hard")

    hard_veto = ood_escalation == "hard_veto"
    directional_veto = dissent >= 0.66 and not hard_veto and not tri_way_veto and not edge_dispersion_veto

    regime_bias_conflict_veto = False
    if (
        signal_dir in ("long", "short")
        and regime_bias in ("long", "short")
        and regime_bias != signal_dir
    ):
        rc = clamp01(_coerce_float(signal_row.get("regime_confidence_0_1")) or 0.0)
        if rc >= 0.62:
            regime_bias_conflict_veto = True
            reasons.append("adversary_regime_bias_opposes_signal_direction")

    all_reasons = list(dict.fromkeys(reasons))

    return {
        "adversary_version": ENSEMBLE_ADVERSARY_VERSION,
        "dissent_score_0_1": round(dissent, 6),
        "long_vote_strength_0_1": round(long_s / total_dir, 6),
        "short_vote_strength_0_1": round(short_s / total_dir, 6),
        "neutral_vote_strength_0_1": round(neutral_s / (long_s + short_s + neutral_s + 1e-9), 6),
        "ood_escalation": ood_escalation,
        "ood_score_0_1": round(ood, 6),
        "hard_veto_recommended": hard_veto,
        "directional_veto_recommended": directional_veto,
        "tri_way_veto_recommended": tri_way_veto,
        "edge_dispersion_veto_recommended": edge_dispersion_veto,
        "regime_mismatch_veto_recommended": regime_mismatch_veto,
        "regime_bias_conflict_veto_recommended": regime_bias_conflict_veto,
        "confidence_shrink_0_1": round(
            0.78 if dissent >= 0.45 and not hard_veto and not directional_veto else 1.0,
            6,
        ),
        "reasons": all_reasons,
    }


def apply_adversary_to_router(
    *,
    pre_trade_action: str,
    adversary: dict[str, Any],
) -> tuple[str, list[str], bool, float]:
    """
    Returns: final_trade_action, extra_reasons, confidence_shrink_applied, multiplier
    """
    reasons: list[str] = []
    mult = float(adversary.get("confidence_shrink_0_1") or 1.0)
    shrink = mult < 0.999
    action = pre_trade_action
    if pre_trade_action == "allow_trade":
        if adversary.get("hard_veto_recommended"):
            action = "do_not_trade"
            reasons.append("ensemble_adversary_ood_veto")
        elif adversary.get("regime_mismatch_veto_recommended"):
            action = "do_not_trade"
            reasons.append("ensemble_adversary_regime_playbook_mismatch")
        elif adversary.get("tri_way_veto_recommended"):
            action = "do_not_trade"
            reasons.append("ensemble_adversary_three_way_split")
        elif adversary.get("edge_dispersion_veto_recommended"):
            action = "do_not_trade"
            reasons.append("ensemble_adversary_edge_dispersion")
        elif adversary.get("regime_bias_conflict_veto_recommended"):
            action = "do_not_trade"
            reasons.append("ensemble_adversary_regime_bias_conflict")
        elif adversary.get("directional_veto_recommended"):
            action = "do_not_trade"
            reasons.append("ensemble_adversary_directional_veto")
    return action, reasons, shrink, mult
