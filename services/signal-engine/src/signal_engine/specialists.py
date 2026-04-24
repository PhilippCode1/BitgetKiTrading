from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from shared_py.bitget.instruments import BitgetInstrumentIdentity
from shared_py.model_contracts import extract_primary_feature_snapshot
from shared_py.playbook_registry import (
    PLAYBOOK_REGISTRY,
    PLAYBOOK_REGISTRY_HASH,
    PLAYBOOK_REGISTRY_VERSION,
    PlaybookDefinition,
)
from shared_py.regime_policy import REGIME_ROUTING_POLICY_VERSION, get_regime_playbook_policy
from shared_py.specialist_ensemble_contract import ENSEMBLE_ROUTER_VERSION

from signal_engine.product_family_risk import risk_dispatch_lane
from signal_engine.specialist_proposals import (
    apply_adversary_to_router,
    build_base_model_proposal,
    build_family_proposal,
    build_liquidity_vol_cluster_proposal,
    build_playbook_proposal,
    build_product_margin_proposal,
    build_regime_proposal,
    build_symbol_specialist_proposal,
    run_adversary_check,
)

_PLAYBOOK_SELECTION_MIN_SCORE = 0.45


def build_specialist_stack(
    *,
    signal_row: dict[str, Any],
    instrument: BitgetInstrumentIdentity,
) -> dict[str, Any]:
    direction = str(signal_row.get("direction") or "").strip().lower()
    market_regime = str(signal_row.get("market_regime") or "").strip().lower() or "unknown"
    regime_state = str(signal_row.get("regime_state") or "").strip().lower() or market_regime
    signal_class = str(signal_row.get("signal_class") or "").strip().lower() or "warnung"
    trade_action = str(signal_row.get("trade_action") or "").strip().lower() or "do_not_trade"
    meta_trade_lane = str(signal_row.get("meta_trade_lane") or "").strip().lower() or None
    source_snapshot = signal_row.get("source_snapshot_json") or {}
    primary_feature = extract_primary_feature_snapshot(
        source_snapshot.get("feature_snapshot") if isinstance(source_snapshot, dict) else {}
    )
    regime_policy = get_regime_playbook_policy(regime_state)

    product_family = str(instrument.market_family).strip().lower() or "futures"
    risk_lane = risk_dispatch_lane(product_family)

    family_blockers: list[str] = []
    if instrument.market_family == "spot" and direction == "short":
        family_blockers.append("spot_short_not_supported")
    if instrument.market_family == "spot" and instrument.supports_leverage:
        family_blockers.append("spot_leverage_contract_invalid")

    ranked_candidates = _rank_playbooks(
        signal_row=signal_row,
        instrument=instrument,
        primary_feature=primary_feature,
    )
    selected = ranked_candidates[0] if ranked_candidates else None
    if selected and selected.get("policy_blockers"):
        selected = None
    playbook = selected["playbook"] if selected and selected["score"] >= _PLAYBOOK_SELECTION_MIN_SCORE else None
    playbook_decision_mode = "selected" if playbook is not None else "playbookless"
    playbook_id = playbook.playbook_id if playbook is not None else None
    playbook_family = playbook.playbook_family if playbook is not None else None
    anti_pattern_hits = list(selected["anti_pattern_hits"]) if selected else []
    blacklist_hits = list(selected["blacklist_hits"]) if selected else []
    invalid_context_hits = list(selected["invalid_context_hits"]) if selected else []
    policy_blockers = list(selected["policy_blockers"]) if selected else []
    router_action = trade_action
    if family_blockers or blacklist_hits or (
        playbook_decision_mode == "playbookless" and trade_action == "allow_trade"
    ) or policy_blockers:
        router_action = "do_not_trade"
    router_reasons = list(family_blockers)
    router_reasons.extend(f"playbook_blacklist:{item}" for item in blacklist_hits)
    router_reasons.extend(f"regime_policy:{item}" for item in policy_blockers)
    if playbook_decision_mode == "playbookless" and trade_action == "allow_trade":
        router_reasons.append("playbook_selection_missing_for_trade")
    if meta_trade_lane:
        router_reasons.append(f"meta_trade_lane_{meta_trade_lane}")
    if router_action == "do_not_trade" and not router_reasons:
        router_reasons.append("router_inherits_core_no_trade")

    pre_adversary_trade_action = router_action
    base_proposal = build_base_model_proposal(signal_row=signal_row)
    family_proposal = build_family_proposal(
        signal_row=signal_row,
        instrument=instrument,
        family_blockers=family_blockers,
    )
    regime_proposal = build_regime_proposal(signal_row=signal_row)
    playbook_proposal = build_playbook_proposal(
        signal_row=signal_row,
        playbook_id=playbook_id,
        playbook_family=playbook_family,
        playbook_decision_mode=playbook_decision_mode,
        selection_score=float(selected["score"]) if selected else 0.0,
        exit_families=list(playbook.exit_families) if playbook else [],
    )
    product_margin_proposal = build_product_margin_proposal(
        signal_row=signal_row,
        instrument=instrument,
    )
    liquidity_vol_proposal = build_liquidity_vol_cluster_proposal(
        signal_row=signal_row,
        primary_feature=primary_feature,
    )
    symbol_proposal, symbol_expert_mode = build_symbol_specialist_proposal(
        signal_row=signal_row,
        instrument=instrument,
        primary_feature=primary_feature,
    )
    proposals_ordered: list[Any] = [
        base_proposal,
        family_proposal,
        product_margin_proposal,
        liquidity_vol_proposal,
        regime_proposal,
        playbook_proposal,
        symbol_proposal,
    ]
    ensemble_hierarchy = [
        {"layer": i, "role": pr.get("specialist_role"), "specialist_id": pr.get("specialist_id")}
        for i, pr in enumerate(proposals_ordered)
    ]
    adversary_check = run_adversary_check(
        proposals=proposals_ordered,
        signal_row=signal_row,
        playbook=playbook,
        primary_feature=primary_feature,
    )
    router_action, adversary_router_reasons, _ensemble_shrink_flag, ensemble_conf_mult = (
        apply_adversary_to_router(pre_trade_action=pre_adversary_trade_action, adversary=adversary_check)
    )
    router_reasons.extend(adversary_router_reasons)

    counterfactual_candidates = [
        {
            "playbook_id": candidate["playbook"].playbook_id,
            "playbook_family": candidate["playbook"].playbook_family,
            "score_0_1": round(candidate["score"], 6),
        }
        for candidate in ranked_candidates
        if playbook is None or candidate["playbook"].playbook_id != playbook.playbook_id
    ][:3]
    playbook_context = {
        "registry_version": PLAYBOOK_REGISTRY_VERSION,
        "registry_hash": PLAYBOOK_REGISTRY_HASH,
        "decision_mode": playbook_decision_mode,
        "selected_playbook_id": playbook_id,
        "selected_playbook_family": playbook_family,
        "recommended_strategy_name": (
            playbook.preferred_strategy_name if playbook is not None else None
        ),
        "selection_score_0_1": round(selected["score"], 6) if selected else 0.0,
        "selection_reasons": list(selected["selection_reasons"]) if selected else [],
        "invalid_context_hits": invalid_context_hits,
        "anti_pattern_hits": anti_pattern_hits,
        "blacklist_hits": blacklist_hits,
        "policy_blockers": policy_blockers,
        "allowed_playbook_families": list(regime_policy.allowed_playbook_families) if regime_policy else [],
        "blocked_playbook_families": list(regime_policy.blocked_playbook_families) if regime_policy else [],
        "regime_policy_version": REGIME_ROUTING_POLICY_VERSION,
        "preferred_stop_families": list(playbook.preferred_stop_families) if playbook else [],
        "exit_families": list(playbook.exit_families) if playbook else [],
        "preferred_timeframes": list(playbook.preferred_timeframes) if playbook else [],
        "benchmark_rule_ids": (
            [rule.benchmark_id for rule in playbook.benchmark_rules] if playbook else []
        ),
        "counterfactual_candidates": counterfactual_candidates,
        "playbookless_reason": (
            "no_suitable_registered_playbook" if playbook is None else None
        ),
        "candidate_scores": [
            {
                "playbook_id": candidate["playbook"].playbook_id,
                "playbook_family": candidate["playbook"].playbook_family,
                "score_0_1": round(candidate["score"], 6),
            }
            for candidate in ranked_candidates[:5]
        ],
    }

    return {
        "ensemble_contract": {
            "ensemble_router_version": ENSEMBLE_ROUTER_VERSION,
            "specialist_proposal_version": base_proposal.get("proposal_version"),
            "adversary_version": adversary_check.get("adversary_version"),
        },
        "product_family_risk": {
            "product_family": product_family,
            "risk_dispatch_lane": risk_lane,
            "source": "instrument.market_family",
        },
        "ensemble_hierarchy": ensemble_hierarchy,
        "specialist_proposals_all": [dict(pr) for pr in proposals_ordered],
        "base_model": {
            "specialist_id": base_proposal["specialist_id"],
            "model_lane": "scoring_composite_take_trade_proxy",
            "proposal": dict(base_proposal),
        },
        "family_specialist": {
            "specialist_id": f"family:{instrument.market_family}",
            "market_family": instrument.market_family,
            "symbol": instrument.symbol,
            "product_type": instrument.product_type,
            "margin_account_mode": instrument.margin_account_mode,
            "blockers": family_blockers,
            "supports_long_short": instrument.supports_long_short,
            "supports_leverage": instrument.supports_leverage,
            "uses_spot_public_market_data": instrument.uses_spot_public_market_data,
            "proposal": dict(family_proposal),
        },
        "product_margin_specialist": {
            "specialist_id": product_margin_proposal.get("specialist_id"),
            "proposal": dict(product_margin_proposal),
        },
        "liquidity_vol_cluster_specialist": {
            "specialist_id": liquidity_vol_proposal.get("specialist_id"),
            "cluster_key": str(liquidity_vol_proposal.get("specialist_id") or "").replace("liqvol:", ""),
            "proposal": dict(liquidity_vol_proposal),
        },
        "regime_specialist": {
            "specialist_id": f"regime:{regime_state}",
            "market_regime": market_regime,
            "regime_state": regime_state,
            "regime_bias": signal_row.get("regime_bias"),
            "regime_confidence_0_1": signal_row.get("regime_confidence_0_1"),
            "allowed_playbook_families": playbook_context["allowed_playbook_families"],
            "blocked_playbook_families": playbook_context["blocked_playbook_families"],
            "regime_policy_version": playbook_context["regime_policy_version"],
            "proposal": dict(regime_proposal),
        },
        "playbook_specialist": {
            "specialist_id": f"playbook:{playbook_id or 'playbookless'}",
            "playbook_id": playbook_id,
            "playbook_family": playbook_family,
            "playbook_decision_mode": playbook_decision_mode,
            "playbook_registry_version": PLAYBOOK_REGISTRY_VERSION,
            "signal_class": signal_class,
            "direction": direction or None,
            "selection_score_0_1": playbook_context["selection_score_0_1"],
            "selection_reasons": playbook_context["selection_reasons"],
            "preferred_stop_families": playbook_context["preferred_stop_families"],
            "exit_families": playbook_context["exit_families"],
            "benchmark_rule_ids": playbook_context["benchmark_rule_ids"],
            "anti_pattern_hits": anti_pattern_hits,
            "blacklist_hits": blacklist_hits,
            "invalid_context_hits": invalid_context_hits,
            "policy_blockers": policy_blockers,
            "recommended_strategy_name": playbook_context["recommended_strategy_name"],
            "proposal": dict(playbook_proposal),
        },
        "symbol_specialist": {
            "specialist_id": symbol_proposal.get("specialist_id"),
            "symbol_expert_mode": symbol_expert_mode,
            "proposal": dict(symbol_proposal),
        },
        "adversary_check": adversary_check,
        "router_arbitration": {
            "router_id": "deterministic_specialist_router_v2",
            "ensemble_router_version": ENSEMBLE_ROUTER_VERSION,
            "pre_adversary_trade_action": pre_adversary_trade_action,
            "ensemble_confidence_multiplier_0_1": ensemble_conf_mult,
            "selected_playbook_id": playbook_id,
            "selected_playbook_family": playbook_family,
            "selected_trade_action": router_action,
            "selected_meta_trade_lane": meta_trade_lane,
            "reasons": router_reasons,
            "operator_gate_required": meta_trade_lane == "candidate_for_live",
        },
        "playbook_context": playbook_context,
    }


def _rank_playbooks(
    *,
    signal_row: dict[str, Any],
    instrument: BitgetInstrumentIdentity,
    primary_feature: dict[str, Any],
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    regime_state = str(signal_row.get("regime_state") or "").strip().lower() or str(
        signal_row.get("market_regime") or ""
    ).strip().lower()
    regime_policy = get_regime_playbook_policy(regime_state)
    for playbook in PLAYBOOK_REGISTRY:
        if instrument.market_family not in playbook.target_market_families:
            continue
        policy_blockers: list[str] = []
        if regime_policy and playbook.playbook_family in regime_policy.blocked_playbook_families:
            policy_blockers.append(f"blocked_family:{playbook.playbook_family}")
        if (
            regime_policy
            and regime_policy.allowed_playbook_families
            and playbook.playbook_family not in regime_policy.allowed_playbook_families
        ):
            policy_blockers.append(f"not_allowed_family:{playbook.playbook_family}")
        score, selection_reasons = _score_playbook(
            playbook=playbook,
            signal_row=signal_row,
            instrument=instrument,
            primary_feature=primary_feature,
        )
        anti_pattern_hits = _anti_pattern_hits(
            playbook=playbook,
            signal_row=signal_row,
            instrument=instrument,
            primary_feature=primary_feature,
        )
        blacklist_hits = _blacklist_hits(
            playbook=playbook,
            signal_row=signal_row,
            instrument=instrument,
            primary_feature=primary_feature,
        )
        invalid_context_hits = _invalid_context_hits(
            playbook=playbook,
            signal_row=signal_row,
            instrument=instrument,
            primary_feature=primary_feature,
        )
        penalty = (0.18 * len(anti_pattern_hits)) + (0.35 * len(blacklist_hits)) + (
            0.22 * len(invalid_context_hits)
        )
        if policy_blockers:
            penalty += 0.55 * len(policy_blockers)
        ranked.append(
            {
                "playbook": playbook,
                "score": max(0.0, min(1.0, score - penalty)),
                "selection_reasons": selection_reasons,
                "anti_pattern_hits": anti_pattern_hits,
                "blacklist_hits": blacklist_hits,
                "invalid_context_hits": invalid_context_hits,
                "policy_blockers": policy_blockers,
            }
        )
    ranked.sort(
        key=lambda item: (
            -float(item["score"]),
            len(item["blacklist_hits"]),
            len(item["invalid_context_hits"]),
            item["playbook"].playbook_id,
        )
    )
    return ranked


def _score_playbook(
    *,
    playbook: PlaybookDefinition,
    signal_row: dict[str, Any],
    instrument: BitgetInstrumentIdentity,
    primary_feature: dict[str, Any],
) -> tuple[float, list[str]]:
    market_regime = str(signal_row.get("market_regime") or "").strip().lower()
    regime_state = str(signal_row.get("regime_state") or "").strip().lower() or market_regime
    direction = str(signal_row.get("direction") or "").strip().lower()
    signal_class = str(signal_row.get("signal_class") or "").strip().lower()
    regime_bias = str(signal_row.get("regime_bias") or "").strip().lower()
    timeframe = str(signal_row.get("timeframe") or "").strip()
    news_score = _coerce_float(signal_row.get("news_score_0_100"))
    decision_confidence = _coerce_float(signal_row.get("decision_confidence_0_1"))
    confluence = _coerce_float(primary_feature.get("confluence_score_0_100"))
    range_score = _coerce_float(primary_feature.get("range_score"))
    mean_reversion = _coerce_float(primary_feature.get("mean_reversion_pressure_0_100"))
    compression = _coerce_float(primary_feature.get("breakout_compression_score_0_100"))
    realized_vol_cluster = _coerce_float(primary_feature.get("realized_vol_cluster_0_100"))
    funding_rate_bps = _coerce_float(primary_feature.get("funding_rate_bps"))
    basis_bps = _coerce_float(primary_feature.get("basis_bps"))
    event_distance_ms = _coerce_float(primary_feature.get("event_distance_ms"))
    trend_dir = _coerce_float(primary_feature.get("trend_dir"))

    reasons: list[str] = []
    score = 0.05
    if regime_state in playbook.regime_suitability:
        score += 0.28
        reasons.append(f"regime_state_match:{regime_state}")
    if timeframe in playbook.preferred_timeframes:
        score += 0.08
        reasons.append(f"timeframe_match:{timeframe}")
    if decision_confidence is not None:
        score += min(0.12, max(0.0, decision_confidence) * 0.12)
    if signal_class in {"kern", "gross"} and playbook.playbook_family in {
        "trend_continuation",
        "breakout",
        "pullback",
    }:
        score += 0.08
        reasons.append("signal_class_supports_directional_playbook")
    if signal_class == "mikro" and playbook.playbook_family in {
        "mean_reversion",
        "liquidity_sweep",
        "range_rotation",
    }:
        score += 0.08
        reasons.append("signal_class_supports_micro_playbook")
    if direction in {"long", "short"} and regime_bias in {"neutral", direction}:
        score += 0.08
        reasons.append("regime_bias_aligned")
    if confluence is not None and playbook.playbook_family in {"trend_continuation", "pullback"}:
        score += min(0.14, max(0.0, confluence / 100.0) * 0.14)
        reasons.append("mtf_confluence_support")
    if playbook.playbook_family == "trend_continuation" and trend_dir is not None and direction in {"long", "short"}:
        if (direction == "long" and trend_dir >= 0) or (direction == "short" and trend_dir <= 0):
            score += 0.12
            reasons.append("trend_continuation_alignment")
    if compression is not None and playbook.playbook_family in {
        "breakout",
        "volatility_compression_expansion",
    }:
        score += min(0.18, max(0.0, compression / 100.0) * 0.18)
        reasons.append("compression_signal_present")
    if mean_reversion is not None and playbook.playbook_family in {
        "mean_reversion",
        "range_rotation",
        "liquidity_sweep",
    }:
        score += min(0.18, max(0.0, mean_reversion / 100.0) * 0.18)
        reasons.append("mean_reversion_pressure_present")
    if range_score is not None and playbook.playbook_family == "range_rotation":
        score += min(0.16, max(0.0, range_score / 100.0) * 0.16)
        reasons.append("range_balance_present")
    if realized_vol_cluster is not None and playbook.playbook_family == "volatility_compression_expansion":
        score += min(0.10, max(0.0, realized_vol_cluster / 100.0) * 0.10)
        reasons.append("realized_vol_cluster_support")
    if playbook.playbook_family == "carry_funding":
        if instrument.market_family == "futures":
            score += 0.12
            reasons.append("futures_family_required")
        if funding_rate_bps is not None and abs(funding_rate_bps) >= 0.8:
            score += 0.16
            reasons.append("funding_edge_present")
        if basis_bps is not None and abs(basis_bps) >= 1.0:
            score += 0.10
            reasons.append("basis_edge_present")
        if event_distance_ms is not None and event_distance_ms <= 14_400_000:
            score += 0.08
            reasons.append("event_window_relevant")
    if playbook.playbook_family == "news_shock":
        if market_regime in {"shock", "dislocation"}:
            score += 0.25
            reasons.append("shock_regime_match")
        if news_score is not None and news_score >= 55.0:
            score += 0.16
            reasons.append("news_layer_support")
    if playbook.playbook_family == "session_open" and _session_window_label(signal_row.get("analysis_ts_ms")):
        score += 0.22
        reasons.append("session_window_match")
    if playbook.playbook_family == "time_window_effect":
        if event_distance_ms is not None and event_distance_ms <= 3_600_000:
            score += 0.18
            reasons.append("near_event_window")
        if _near_hourly_boundary(signal_row.get("analysis_ts_ms")):
            score += 0.10
            reasons.append("near_hourly_boundary")
    if playbook.playbook_family == "liquidity_sweep":
        upper_wick = _coerce_float(primary_feature.get("impulse_upper_wick_ratio"))
        lower_wick = _coerce_float(primary_feature.get("impulse_lower_wick_ratio"))
        if (upper_wick is not None and upper_wick >= 0.28) or (
            lower_wick is not None and lower_wick >= 0.28
        ):
            score += 0.16
            reasons.append("wick_dislocation_present")
    if playbook.playbook_family == "pullback" and trend_dir is not None and direction in {"long", "short"}:
        if (
            (direction == "long" and trend_dir >= 0) or (direction == "short" and trend_dir <= 0)
        ) and mean_reversion is not None and 25.0 <= mean_reversion <= 80.0:
            score += 0.10
            reasons.append("trend_dir_alignment")
    return max(0.0, min(score, 1.0)), reasons


def _invalid_context_hits(
    *,
    playbook: PlaybookDefinition,
    signal_row: dict[str, Any],
    instrument: BitgetInstrumentIdentity,
    primary_feature: dict[str, Any],
) -> list[str]:
    market_regime = str(signal_row.get("market_regime") or "").strip().lower()
    regime_state = str(signal_row.get("regime_state") or "").strip().lower() or market_regime
    direction = str(signal_row.get("direction") or "").strip().lower()
    regime_bias = str(signal_row.get("regime_bias") or "").strip().lower()
    regime_confidence = _coerce_float(signal_row.get("regime_confidence_0_1")) or 0.0
    hits: list[str] = []
    for item in playbook.invalid_contexts:
        if item == market_regime:
            hits.append(item)
        elif item == regime_state:
            hits.append(item)
        elif item == "counter_regime_high_confidence":
            if direction in {"long", "short"} and regime_bias not in {"", "neutral", direction} and regime_confidence >= 0.65:
                hits.append(item)
        elif item == "trend_acceleration":
            if market_regime in {"trend", "breakout"} and (_coerce_float(primary_feature.get("confluence_score_0_100")) or 0.0) >= 70.0:
                hits.append(item)
        elif item == "range_rotation_without_compression":
            if (_coerce_float(primary_feature.get("breakout_compression_score_0_100")) or 0.0) < 45.0:
                hits.append(item)
        elif item == "shock_without_event":
            if market_regime == "shock" and _coerce_float(primary_feature.get("event_distance_ms")) is None:
                hits.append(item)
        elif item == "funding_missing":
            if instrument.market_family == "futures" and _coerce_float(primary_feature.get("funding_rate_bps")) is None:
                hits.append(item)
        elif item == "news_context_missing":
            if (_coerce_float(signal_row.get("news_score_0_100")) or 0.0) < 55.0:
                hits.append(item)
        elif item == "session_window_absent":
            if not _session_window_label(signal_row.get("analysis_ts_ms")):
                hits.append(item)
        elif item == "time_window_absent":
            if (
                _coerce_float(primary_feature.get("event_distance_ms")) is None
                and not _near_hourly_boundary(signal_row.get("analysis_ts_ms"))
            ):
                hits.append(item)
        elif item == "trend_broken":
            trend_dir = _coerce_float(primary_feature.get("trend_dir"))
            if direction == "long" and trend_dir is not None and trend_dir < 0:
                hits.append(item)
            if direction == "short" and trend_dir is not None and trend_dir > 0:
                hits.append(item)
    return sorted(set(hits))


def _anti_pattern_hits(
    *,
    playbook: PlaybookDefinition,
    signal_row: dict[str, Any],
    instrument: BitgetInstrumentIdentity,
    primary_feature: dict[str, Any],
) -> list[str]:
    hits: list[str] = []
    confluence = _coerce_float(primary_feature.get("confluence_score_0_100")) or 0.0
    mean_reversion = _coerce_float(primary_feature.get("mean_reversion_pressure_0_100")) or 0.0
    compression = _coerce_float(primary_feature.get("breakout_compression_score_0_100")) or 0.0
    news_score = _coerce_float(signal_row.get("news_score_0_100")) or 0.0
    event_distance_ms = _coerce_float(primary_feature.get("event_distance_ms"))
    for item in playbook.anti_patterns:
        if item == "late_trend_chase" and confluence < 55.0:
            hits.append(item)
        elif item == "mtf_confluence_missing" and confluence < 60.0:
            hits.append(item)
        elif item == "event_too_close" and event_distance_ms is not None and event_distance_ms < 300_000:
            hits.append(item)
        elif item == "breakout_without_compression" and compression < 55.0:
            hits.append(item)
        elif item == "breakout_into_thin_book" and _liquidity_below_hard_floor(playbook, primary_feature):
            hits.append(item)
        elif item == "fade_strong_trend" and str(signal_row.get("regime_state") or "").strip().lower() == "trend":
            hits.append(item)
        elif item == "mean_reversion_without_pressure" and mean_reversion < 55.0:
            hits.append(item)
        elif item == "compression_absent" and compression < 60.0:
            hits.append(item)
        elif item == "depth_imbalance_missing" and _coerce_float(primary_feature.get("orderbook_imbalance")) is None:
            hits.append(item)
        elif item == "sweep_without_reclaim":
            upper = _coerce_float(primary_feature.get("impulse_upper_wick_ratio")) or 0.0
            lower = _coerce_float(primary_feature.get("impulse_lower_wick_ratio")) or 0.0
            if max(upper, lower) < 0.28:
                hits.append(item)
        elif item == "book_depth_missing" and _coerce_float(primary_feature.get("depth_to_bar_volume_ratio")) is None:
            hits.append(item)
        elif item == "pullback_too_deep" and mean_reversion > 80.0:
            hits.append(item)
        elif item == "range_boundary_missing" and (_coerce_float(primary_feature.get("range_score")) or 0.0) < 60.0:
            hits.append(item)
        elif item == "breakout_pressure_high" and compression > 60.0:
            hits.append(item)
        elif item == "carry_without_edge":
            if abs(_coerce_float(primary_feature.get("funding_rate_bps")) or 0.0) < 0.8 and abs(
                _coerce_float(primary_feature.get("basis_bps")) or 0.0
            ) < 1.0:
                hits.append(item)
        elif item == "funding_event_too_far" and (
            event_distance_ms is None or event_distance_ms > 14_400_000
        ):
            hits.append(item)
        elif item == "shock_without_news_support" and news_score < 55.0:
            hits.append(item)
        elif item == "event_too_old" and (
            event_distance_ms is None or event_distance_ms > 7_200_000
        ):
            hits.append(item)
        elif item == "session_open_without_liquidity" and _liquidity_below_hard_floor(playbook, primary_feature):
            hits.append(item)
        elif item == "open_drive_after_delay" and not _session_window_label(signal_row.get("analysis_ts_ms")):
            hits.append(item)
        elif item == "window_absent" and (
            event_distance_ms is None and not _near_hourly_boundary(signal_row.get("analysis_ts_ms"))
        ):
            hits.append(item)
    return sorted(set(hits))


def _blacklist_hits(
    *,
    playbook: PlaybookDefinition,
    signal_row: dict[str, Any],
    instrument: BitgetInstrumentIdentity,
    primary_feature: dict[str, Any],
) -> list[str]:
    hits: list[str] = []
    for item in playbook.blacklist_criteria:
        if item == "feature_quality_degraded":
            if str(primary_feature.get("feature_quality_status") or "").strip().lower() not in {"", "ok"}:
                hits.append(item)
            if (_coerce_float(primary_feature.get("staleness_score_0_1")) or 0.0) > playbook.minimum_liquidity.max_staleness_score_0_1:
                hits.append(item)
            if (_coerce_float(primary_feature.get("data_completeness_0_1")) or 0.0) < playbook.minimum_liquidity.min_data_completeness_0_1:
                hits.append(item)
        elif item == "liquidity_below_hard_floor" and _liquidity_below_hard_floor(playbook, primary_feature):
            hits.append(item)
        elif item == "missing_futures_context" and instrument.market_family != "futures":
            hits.append(item)
    return sorted(set(hits))


def _liquidity_below_hard_floor(playbook: PlaybookDefinition, primary_feature: dict[str, Any]) -> bool:
    spread_bps = _coerce_float(primary_feature.get("spread_bps"))
    execution_cost_bps = _coerce_float(primary_feature.get("execution_cost_bps"))
    depth_ratio = _coerce_float(primary_feature.get("depth_to_bar_volume_ratio"))
    liquidity_source = str(primary_feature.get("liquidity_source") or "").strip().lower()
    constraints = playbook.minimum_liquidity
    if constraints.max_spread_bps is not None and spread_bps is not None and spread_bps > constraints.max_spread_bps:
        return True
    if (
        constraints.max_execution_cost_bps is not None
        and execution_cost_bps is not None
        and execution_cost_bps > constraints.max_execution_cost_bps
    ):
        return True
    if (
        constraints.min_depth_to_bar_volume_ratio is not None
        and depth_ratio is not None
        and depth_ratio < constraints.min_depth_to_bar_volume_ratio
    ):
        return True
    if constraints.require_orderbook_context and not liquidity_source.startswith("orderbook_levels"):
        return True
    return False


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _session_window_label(analysis_ts_ms: Any) -> str | None:
    if analysis_ts_ms in (None, ""):
        return None
    dt = datetime.fromtimestamp(int(analysis_ts_ms) / 1000.0, tz=timezone.utc)
    minute_of_day = dt.hour * 60 + dt.minute
    windows = {
        "asia_open": 0,
        "europe_open": 7 * 60,
        "us_open": 13 * 60 + 30,
    }
    for label, anchor in windows.items():
        if abs(minute_of_day - anchor) <= 20:
            return label
    return None


def _near_hourly_boundary(analysis_ts_ms: Any) -> bool:
    if analysis_ts_ms in (None, ""):
        return False
    dt = datetime.fromtimestamp(int(analysis_ts_ms) / 1000.0, tz=timezone.utc)
    return dt.minute <= 5 or dt.minute >= 55
