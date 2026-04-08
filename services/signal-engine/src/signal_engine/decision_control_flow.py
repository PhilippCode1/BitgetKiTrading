"""
Kontrollierter Endentscheid: auditierbarer Entscheidungsgraph fuer Operatoren.

Reihenfolge orientiert sich an der Signal-Engine: Hybrid ->
Stop-Budget/Ausfuehrbarkeit -> optional Online-Drift -> Spezialisten-Router/Adversary ->
Meta-Decision-Kernel (Persistenz vor diesem Schritt).

Siehe docs/signal_engine_end_decision.md
"""

from __future__ import annotations

import json
from typing import Any

from shared_py.exit_family_resolver import resolve_exit_family_resolution
from shared_py.signal_contracts import META_DECISION_ACTION_VALUES

DECISION_PIPELINE_VERSION = "se-end-decision-v4"

# Reihenfolge der Phasen (IDs stabil fuer UI/Tests/Monitoring)
PHASE_ORDER: tuple[tuple[str, str], ...] = (
    ("data_quality", "Datenqualitaet und Feature-Gates"),
    ("deterministic_safety", "Deterministische Safety- und Reject-Regeln"),
    ("regime_scoring", "Regime und deterministisches Composite-Scoring"),
    ("probabilistic_models", "Probabilistische Modelle (Take-Trade, Return/MAE/MFE)"),
    ("uncertainty_ood", "Unsicherheit, Kalibrierung und OOD-Gates"),
    (
        "hybrid_risk_leverage_meta",
        "Hybrid-Policy, Risk-Governor, Hebel-Caps und Meta-Lane",
    ),
    (
        "stop_budget_executability",
        "Stop-Budget-Kurve, Tick/Spread/ATR, Liquidationspuffer, ggf. Hebelreduktion",
    ),
    (
        "specialist_arbitration",
        "Spezialisten-Ensemble, Playbook-Router, Adversary, finales Routing",
    ),
    ("online_drift_optional", "Optional: Online-Drift-Sperre"),
    (
        "meta_decision_closure",
        "Meta-Decision-Kernel: Evidenz, EU-Proxy, finale Aktionssemantik",
    ),
)


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


def _specialists_bundle(db_row: dict[str, Any], rj: dict[str, Any], snap: dict[str, Any]) -> dict[str, Any]:
    spec = rj.get("specialists")
    if isinstance(spec, dict) and spec:
        return spec
    spec2 = snap.get("specialists")
    return dict(spec2) if isinstance(spec2, dict) else {}


def _end_decision_binding(db_row: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """Gebundene Endentscheidung: Playbook + konservative Ausfuehrungs-Hints aus Ensemble-Proposals."""
    exit_ranked: list[str] = []
    stop_budgets: list[float] = []
    lev_min: list[float] = []
    lev_max: list[float] = []

    for key in (
        "base_model",
        "family_specialist",
        "product_margin_specialist",
        "liquidity_vol_cluster_specialist",
        "regime_specialist",
        "playbook_specialist",
        "symbol_specialist",
    ):
        block = spec.get(key)
        if not isinstance(block, dict):
            continue
        prop = block.get("proposal")
        if not isinstance(prop, dict):
            continue
        sb = prop.get("stop_budget_0_1")
        if isinstance(sb, (int, float)):
            stop_budgets.append(float(sb))
        for ex in prop.get("exit_families_ranked") or []:
            if isinstance(ex, str) and ex.strip() and ex not in exit_ranked:
                exit_ranked.append(ex.strip())
        ep = prop.get("exit_family_primary")
        if isinstance(ep, str) and ep.strip() and ep.strip() not in exit_ranked:
            exit_ranked.insert(0, ep.strip())
        lb = prop.get("leverage_band")
        if isinstance(lb, dict):
            try:
                lev_min.append(float(lb.get("min_fraction_0_1") or 0.0))
                lev_max.append(float(lb.get("max_fraction_0_1") or 1.0))
            except (TypeError, ValueError):
                pass

    router = spec.get("router_arbitration") if isinstance(spec.get("router_arbitration"), dict) else {}
    adv = spec.get("adversary_check") if isinstance(spec.get("adversary_check"), dict) else {}

    exit_primary = None
    pb_prop = spec.get("playbook_specialist") if isinstance(spec.get("playbook_specialist"), dict) else {}
    pp = pb_prop.get("proposal") if isinstance(pb_prop.get("proposal"), dict) else {}
    if isinstance(pp.get("exit_family_primary"), str) and pp.get("exit_family_primary").strip():
        exit_primary = pp.get("exit_family_primary").strip()
    elif exit_ranked:
        exit_primary = exit_ranked[0]
    base_prop = spec.get("base_model") if isinstance(spec.get("base_model"), dict) else {}
    bp = base_prop.get("proposal") if isinstance(base_prop.get("proposal"), dict) else {}
    if exit_primary is None and isinstance(bp.get("exit_family_primary"), str):
        exit_primary = (bp.get("exit_family_primary") or "").strip() or None

    return {
        "schema_version": "1",
        "playbook_id": db_row.get("playbook_id"),
        "playbook_family": db_row.get("playbook_family"),
        "playbook_decision_mode": db_row.get("playbook_decision_mode"),
        "playbook_registry_version": db_row.get("playbook_registry_version"),
        "strategy_name": db_row.get("strategy_name"),
        "stop_budget_0_1": min(stop_budgets) if stop_budgets else None,
        "stop_budget_source": "min_across_specialist_proposals",
        "exit_family_primary": exit_primary,
        "exit_families_ranked": exit_ranked[:12],
        "leverage_band_fraction_0_1": {
            "min": max(lev_min) if lev_min else None,
            "max": min(lev_max) if lev_max else None,
            "semantics_de": "Schnittmenge der Spezialisten-Baender (konservativ)",
        },
        "allowed_leverage": db_row.get("allowed_leverage"),
        "recommended_leverage": db_row.get("recommended_leverage"),
        "ensemble_router_version": (spec.get("ensemble_contract") or {}).get("ensemble_router_version")
        if isinstance(spec.get("ensemble_contract"), dict)
        else None,
        "router_pre_adversary_trade_action": router.get("pre_adversary_trade_action"),
        "router_selected_trade_action": router.get("selected_trade_action"),
        "adversary_hard_veto": adv.get("hard_veto_recommended"),
        "adversary_directional_veto": adv.get("directional_veto_recommended"),
        "adversary_dissent_score_0_1": adv.get("dissent_score_0_1"),
    }


def _no_trade_path_analysis(
    *,
    phases: list[dict[str, Any]],
    trade_action: str,
    db_row: dict[str, Any],
) -> dict[str, Any]:
    """No-Trade als gleichwertiger Pfad: strukturierte Begruendungskette."""
    is_no_trade = trade_action == "do_not_trade"
    drivers: list[dict[str, Any]] = []
    if is_no_trade:
        for p in phases:
            if not isinstance(p, dict):
                continue
            pid = p.get("id")
            out = str(p.get("outcome") or "")
            if out in ("blocked", "failed", "arbitrated_no_trade", "degraded_block"):
                drivers.append(
                    {
                        "phase_id": pid,
                        "outcome": out,
                        "notes_de": p.get("notes_de"),
                    }
                )
            elif (
                is_no_trade
                and pid == "hybrid_risk_leverage_meta"
                and out == "do_not_trade"
            ):
                drivers.append(
                    {
                        "phase_id": pid,
                        "outcome": out,
                        "notes_de": p.get("notes_de"),
                    }
                )
        if str(db_row.get("uncertainty_gate_phase") or "").strip().lower() in (
            "blocked",
            "abstain",
            "hold",
        ):
            drivers.append(
                {
                    "phase_id": "uncertainty_ood",
                    "outcome": "gate_blocked",
                    "notes_de": "Unsicherheits-Gate in Abstinenz/Hold",
                }
            )
    abst = db_row.get("abstention_reasons_json") or []
    abst_tags: list[str] = []
    if isinstance(abst, list):
        for item in abst[:16]:
            if isinstance(item, str) and item.strip():
                abst_tags.append(item.strip())
    return {
        "no_trade_is_final_outcome": is_no_trade,
        "policy_de": (
            "Bei widerspruechlichen Signalen oder harten Gates ist **no_trade** der "
            "Standardpfad; **allow_trade** erfordert konsistente Freigaben — kein "
            "Stillhalten aus Schwaeche, sondern bewusste Risiko-Vermeidung."
        ),
        "phase_block_drivers": drivers[:14],
        "abstention_reasons_top": abst_tags,
    }


def build_decision_control_flow(db_row: dict[str, Any]) -> dict[str, Any]:
    """Baut den Entscheidungsgraphen aus dem finalen DB-Row (nach allen Subsystemen)."""
    rj = _as_dict(db_row.get("reasons_json"))
    det = _as_dict(rj.get("deterministic_gates"))
    snap = _as_dict(db_row.get("source_snapshot_json"))
    qg = _as_dict(snap.get("quality_gate"))
    ug = snap.get("uncertainty_gate")
    ug = ug if isinstance(ug, dict) else {}
    hd = snap.get("hybrid_decision")
    hd = hd if isinstance(hd, dict) else {}
    rg = hd.get("risk_governor") if isinstance(hd.get("risk_governor"), dict) else {}
    od = rj.get("online_drift")
    od = od if isinstance(od, dict) else {}
    spec = _specialists_bundle(db_row, rj, snap)

    det_blocked = bool(det.get("rejection_state"))
    q_pass = qg.get("passed")
    q_ok = True if q_pass is None else bool(q_pass)

    take_prob = db_row.get("take_trade_prob")
    models_ok = take_prob is not None and all(
        db_row.get(k) is not None for k in ("expected_return_bps", "expected_mae_bps", "expected_mfe_bps")
    )

    unc_phase = str(db_row.get("uncertainty_gate_phase") or ug.get("gate_phase") or "full")
    trade_action = str(db_row.get("trade_action") or "").strip().lower()

    drift_blocked = "online_drift_hard_block" in (db_row.get("rejection_reasons_json") or [])

    router_arb = spec.get("router_arbitration") if isinstance(spec.get("router_arbitration"), dict) else {}
    pre_adv = str(router_arb.get("pre_adversary_trade_action") or "").strip().lower()
    post_router = str(router_arb.get("selected_trade_action") or trade_action).strip().lower()
    specialist_outcome = "skipped"
    if spec:
        if post_router == "do_not_trade" and pre_adv == "allow_trade":
            specialist_outcome = "arbitrated_no_trade"
        elif post_router == "do_not_trade":
            specialist_outcome = "blocked"
        elif post_router == "allow_trade":
            specialist_outcome = "passed"
        else:
            specialist_outcome = "unknown"

    phases: list[dict[str, Any]] = []

    phases.append(
        {
            "id": "data_quality",
            "order": 1,
            "title_de": PHASE_ORDER[0][1],
            "outcome": "failed" if not q_ok else "passed",
            "notes_de": (
                "Quality-Gate nicht bestanden — nachgelagerte Schichten arbeiten unter "
                "Vorbehalt oder fuehren zu Abstinenz"
                if not q_ok
                else "Quality-Gate bestanden oder nicht gesetzt"
            ),
            "evidence": {"quality_gate_passed": q_pass, "data_issues": snap.get("data_issues") or []},
        }
    )

    phases.append(
        {
            "id": "deterministic_safety",
            "order": 2,
            "title_de": PHASE_ORDER[1][1],
            "outcome": "blocked" if det_blocked else "passed",
            "notes_de": (
                "Deterministische Reject-/Downgrade-Regeln (harte No-Trade-Kandidaten)"
                if det_blocked
                else "Keine harten deterministischen Blocker in dieser Schicht"
            ),
            "evidence": {
                "rejection_state": det.get("rejection_state"),
                "decision_state": det.get("decision_state"),
                "rejection_reasons_json": det.get("rejection_reasons_json") or [],
            },
        }
    )

    phases.append(
        {
            "id": "regime_scoring",
            "order": 3,
            "title_de": PHASE_ORDER[2][1],
            "outcome": "evaluated",
            "notes_de": "Regime, Layer-Scores und heuristische Wahrscheinlichkeit (ohne LLM)",
            "evidence": {
                "market_regime": db_row.get("market_regime"),
                "regime_state": db_row.get("regime_state"),
                "regime_substate": db_row.get("regime_substate"),
                "regime_transition_state": db_row.get("regime_transition_state"),
                "regime_bias": db_row.get("regime_bias"),
                "regime_confidence_0_1": db_row.get("regime_confidence_0_1"),
                "probability_0_1": db_row.get("probability_0_1"),
                "signal_strength_0_100": db_row.get("signal_strength_0_100"),
            },
        }
    )

    phases.append(
        {
            "id": "probabilistic_models",
            "order": 4,
            "title_de": PHASE_ORDER[3][1],
            "outcome": "degraded" if not models_ok else "ok",
            "notes_de": (
                "Take-Trade und/oder BPS-Projektion fehlen — konservatives Verhalten "
                "in nachgelagerten Gates"
                if not models_ok
                else "Modelloutputs vollstaendig"
            ),
            "evidence": {
                "take_trade_prob": take_prob,
                "expected_return_bps": db_row.get("expected_return_bps"),
                "expected_mae_bps": db_row.get("expected_mae_bps"),
                "expected_mfe_bps": db_row.get("expected_mfe_bps"),
                "take_trade_calibration_method": db_row.get("take_trade_calibration_method"),
            },
        }
    )

    unc_outcome = unc_phase
    if trade_action == "do_not_trade" and unc_phase in ("blocked", "abstain", "hold"):
        unc_outcome = f"{unc_phase}_no_trade_aligned"

    ua = snap.get("uncertainty_assessment")
    ua = ua if isinstance(ua, dict) else {}
    comp_v2 = ua.get("components_v2") if isinstance(ua.get("components_v2"), dict) else {}
    mon = ua.get("monitoring_hooks") if isinstance(ua.get("monitoring_hooks"), dict) else {}

    phases.append(
        {
            "id": "uncertainty_ood",
            "order": 5,
            "title_de": PHASE_ORDER[4][1],
            "outcome": unc_outcome,
            "notes_de": (
                "Unsicherheit/OOD: kann Ausfuehrung auf shadow/paper beschraenken oder "
                "Abstinenz erzwingen — gleichwertig zu anderen No-Trade-Pfaden"
            ),
            "evidence": {
                "uncertainty_policy_version": ua.get("policy_version"),
                "model_uncertainty_aggregate_0_1": db_row.get("model_uncertainty_0_1"),
                "uncertainty_effective_for_leverage_0_1": db_row.get(
                    "uncertainty_effective_for_leverage_0_1"
                ),
                "components_v2": comp_v2,
                "exit_execution_bias": (rj.get("uncertainty_exit_execution_bias") if isinstance(rj, dict) else None),
                "model_ood_score_0_1": db_row.get("model_ood_score_0_1"),
                "model_ood_alert": db_row.get("model_ood_alert"),
                "uncertainty_execution_lane": db_row.get("uncertainty_execution_lane"),
                "uncertainty_gate_phase": unc_phase,
                "shadow_divergence_0_1": db_row.get("shadow_divergence_0_1"),
                "monitoring_hooks": mon,
            },
        }
    )

    gov_hard = list(rg.get("hard_block_reasons_json") or [])
    gov_univ = list(rg.get("universal_hard_block_reasons_json") or [])
    live_exec = list(rg.get("live_execution_block_reasons_json") or [])
    hybrid_trade = str(hd.get("trade_action") or "").strip().lower()
    if hybrid_trade not in ("allow_trade", "do_not_trade"):
        hybrid_trade = str(db_row.get("trade_action") or "").strip().lower()
    hybrid_outcome = hybrid_trade if hybrid_trade in ("allow_trade", "do_not_trade") else "unknown"
    phases.append(
        {
            "id": "hybrid_risk_leverage_meta",
            "order": 6,
            "title_de": PHASE_ORDER[5][1],
            "outcome": hybrid_outcome,
            "notes_de": (
                "Hybrid-Gates (Return/MAE/MFE/Prob), Risk-Governor (universal vs. Live-Execution), "
                "Hebel-Allocator, Meta-Lane; Veto hat Vorrang vor Ausfuehrungswuenschen"
            ),
            "evidence": {
                "decision_policy_version": db_row.get("decision_policy_version"),
                "trade_action_after_hybrid_layer": hybrid_trade,
                "trade_action_final_on_row": trade_action,
                "decision_state_after_pipeline": db_row.get("decision_state"),
                "meta_trade_lane": db_row.get("meta_trade_lane"),
                "meta_trade_lane_hybrid_raw": hd.get("meta_trade_lane_hybrid_raw"),
                "allowed_leverage": db_row.get("allowed_leverage"),
                "recommended_leverage": db_row.get("recommended_leverage"),
                "decision_confidence_0_1": db_row.get("decision_confidence_0_1"),
                "risk_governor_version": rg.get("version"),
                "risk_governor_hard_block_reasons_json": gov_hard,
                "risk_governor_universal_hard_block_reasons_json": gov_univ,
                "live_execution_block_reasons_json": live_exec,
                "risk_governor_account_stress_live_only": rg.get(
                    "risk_governor_account_stress_live_only"
                ),
                "max_risk_exposure_fraction_0_1": rg.get("max_exposure_fraction_0_1"),
                "structured_market_context": snap.get("structured_market_context"),
            },
        }
    )

    sba = snap.get("stop_budget_assessment")
    sba = sba if isinstance(sba, dict) else {}
    sb_out = str(sba.get("outcome") or "unknown")
    phases.append(
        {
            "id": "stop_budget_executability",
            "order": 7,
            "title_de": PHASE_ORDER[6][1],
            "outcome": sb_out,
            "notes_de": (
                "Hebel-indexiertes Stop-Budget (7x->1%% Zielobergrenze, hoher Hebel enger); "
                "Mindestabstand aus Tick, Spread, ATR, Slippage; ggf. Hebel senken oder no_trade"
            ),
            "evidence": {
                "policy_version": sba.get("policy_version"),
                "stop_distance_pct": sba.get("stop_distance_pct"),
                "stop_budget_max_pct_allowed": sba.get("stop_budget_max_pct_allowed"),
                "stop_min_executable_pct": sba.get("stop_min_executable_pct"),
                "stop_to_spread_ratio": sba.get("stop_to_spread_ratio"),
                "stop_quality_0_1": sba.get("stop_quality_0_1"),
                "stop_executability_0_1": sba.get("stop_executability_0_1"),
                "stop_fragility_0_1": sba.get("stop_fragility_0_1"),
                "leverage_before": sba.get("leverage_before"),
                "leverage_after": sba.get("leverage_after"),
                "mark_trigger_note": sba.get("mark_trigger_note"),
                "liquidation_proximity_stress_0_1": sba.get("liquidation_proximity_stress_0_1"),
                "gate_reasons_json": (sba.get("gate_reasons_json") or [])[:12],
            },
        }
    )

    adv = spec.get("adversary_check") if isinstance(spec.get("adversary_check"), dict) else {}
    phases.append(
        {
            "id": "specialist_arbitration",
            "order": 8,
            "title_de": PHASE_ORDER[7][1],
            "outcome": specialist_outcome,
            "notes_de": (
                "Family/Regime/Playbook-Proposals, Router und Adversary; bindet Playbook-ID, "
                "Stop-Budget-, Exit- und Hebel-Band-Hints in die Endentscheidung"
                if spec
                else "Kein Spezialisten-Snapshot in reasons_json — Phase uebersprungen"
            ),
            "evidence": {
                "ensemble_contract": spec.get("ensemble_contract"),
                "router_arbitration": {
                    "pre_adversary_trade_action": router_arb.get("pre_adversary_trade_action"),
                    "selected_trade_action": router_arb.get("selected_trade_action"),
                    "ensemble_confidence_multiplier_0_1": router_arb.get(
                        "ensemble_confidence_multiplier_0_1"
                    ),
                    "reasons": (router_arb.get("reasons") or [])[:14],
                },
                "adversary_check": {
                    "dissent_score_0_1": adv.get("dissent_score_0_1"),
                    "hard_veto_recommended": adv.get("hard_veto_recommended"),
                    "directional_veto_recommended": adv.get("directional_veto_recommended"),
                    "tri_way_veto_recommended": adv.get("tri_way_veto_recommended"),
                    "edge_dispersion_veto_recommended": adv.get("edge_dispersion_veto_recommended"),
                    "regime_mismatch_veto_recommended": adv.get("regime_mismatch_veto_recommended"),
                    "regime_bias_conflict_veto_recommended": adv.get(
                        "regime_bias_conflict_veto_recommended"
                    ),
                    "reasons": (adv.get("reasons") or [])[:10],
                },
                "ensemble_hierarchy": (spec.get("ensemble_hierarchy") or [])[:10]
                if isinstance(spec.get("ensemble_hierarchy"), list)
                else [],
                "playbook_specialist_id": (spec.get("playbook_specialist") or {}).get("specialist_id")
                if isinstance(spec.get("playbook_specialist"), dict)
                else None,
            },
        }
    )

    phases.append(
        {
            "id": "online_drift_optional",
            "order": 9,
            "title_de": PHASE_ORDER[8][1],
            "outcome": "blocked" if drift_blocked else "passed",
            "notes_de": "Letzte harte Sperre bei aktivem Online-Drift-Block",
            "evidence": {
                "effective_action": od.get("effective_action"),
                "enable_online_drift_block": od.get("enable_online_drift_block"),
            },
        }
    )

    mdk_rj = rj.get("meta_decision_kernel")
    mdk_rj = mdk_rj if isinstance(mdk_rj, dict) else {}
    mdb = db_row.get("meta_decision_bundle_json")
    mdb = mdb if isinstance(mdb, dict) else {}
    mda = str(db_row.get("meta_decision_action") or "").strip().lower()
    mdk_outcome = mda if mda in set(META_DECISION_ACTION_VALUES) else "unknown"
    phases.append(
        {
            "id": "meta_decision_closure",
            "order": 10,
            "title_de": PHASE_ORDER[9][1],
            "outcome": mdk_outcome,
            "notes_de": (
                "Finale Fusion aller Subsysteme; harte Abstinenzregeln duerfen "
                "`do_not_trade` oder `blocked_by_policy` erzwingen; positives Pfad-Ziel ist "
                "Nutzen unter Risiko, nicht maximale Aktivitaet."
            ),
            "evidence": {
                "meta_decision_kernel_version": db_row.get("meta_decision_kernel_version"),
                "meta_decision_action": db_row.get("meta_decision_action"),
                "kernel_forces_do_not_trade": mdk_rj.get("kernel_forces_do_not_trade"),
                "abstention_codes": mdk_rj.get("abstention_codes"),
                "expected_utility_proxy_0_1": mdb.get("expected_utility_proxy_0_1"),
                "abstention_codes_evidence": mdb.get("abstention_codes_evidence"),
                "operator_override_audit_json": db_row.get("operator_override_audit_json"),
            },
        }
    )

    end_binding = _end_decision_binding(db_row, spec)
    exit_resolution = resolve_exit_family_resolution(db_row=db_row, end_decision_binding=end_binding)
    end_binding["exit_family_effective_primary"] = exit_resolution.get("primary")
    end_binding["exit_families_effective_ranked"] = list(exit_resolution.get("ranked") or [])
    end_binding["exit_resolution_drivers"] = list(exit_resolution.get("drivers") or [])
    end_binding["exit_execution_hints"] = exit_resolution.get("execution_hints") or {}
    end_binding["exit_family_resolution_version"] = exit_resolution.get("version")

    no_trade_analysis = _no_trade_path_analysis(phases=phases, trade_action=trade_action, db_row=db_row)

    return {
        "pipeline_version": DECISION_PIPELINE_VERSION,
        "phases": phases,
        "end_decision_binding": end_binding,
        "exit_family_resolution": exit_resolution,
        "no_trade_path": no_trade_analysis,
        "final_summary": {
            "trade_action": db_row.get("trade_action"),
            "meta_trade_lane": db_row.get("meta_trade_lane"),
            "meta_decision_action": db_row.get("meta_decision_action"),
            "meta_decision_kernel_version": db_row.get("meta_decision_kernel_version"),
            "expected_utility_proxy_0_1": mdb.get("expected_utility_proxy_0_1"),
            "decision_state": db_row.get("decision_state"),
            "signal_class": db_row.get("signal_class"),
            "end_decision_binding_ref": {
                "playbook_id": end_binding.get("playbook_id"),
                "exit_family_primary": end_binding.get("exit_family_primary"),
                "exit_family_effective_primary": end_binding.get("exit_family_effective_primary"),
                "stop_budget_0_1": end_binding.get("stop_budget_0_1"),
            },
        },
        "peripheral_boundary_de": (
            "News: nur als Layer-4-Score und optional deterministische Shock-Reject-Regel; "
            "kein LLM in der Kern-Entscheidungskette der Signal-Engine. "
            "Telegram/Chat duerfen keine Strategie-Parameter oder Risk-Limits aendern — "
            "nur lesen, erklaeren und explizit freigegebene Order-Aktionen."
        ),
    }


def attach_decision_control_flow_to_bundle(bundle: dict[str, Any]) -> None:
    """Schreibt decision_control_flow in reasons_json und source_snapshot."""
    db_row = bundle["db_row"]
    dcf = build_decision_control_flow(db_row)
    rj = db_row.get("reasons_json")
    if not isinstance(rj, dict):
        rj = {}
        db_row["reasons_json"] = rj
    rj["decision_control_flow"] = dcf
    snap = db_row.get("source_snapshot_json")
    if isinstance(snap, dict):
        snap["decision_control_flow"] = dcf
