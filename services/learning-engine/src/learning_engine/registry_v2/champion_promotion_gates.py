"""
Harte Promotionsregeln fuer Registry-Champion (Walk-Forward, Purged-CV, Test-Safety, Shadow-Evidenz).

Kein reines Backtest-Ranking: Schwellen kommen aus LearningEngineSettings.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from learning_engine.config import LearningEngineSettings
from learning_engine.registry_v2.model_run_governance import (
    evaluate_training_run_governance,
    parse_online_drift_promotion_block_tiers,
)
from shared_py.model_registry_policy import parse_metadata_json
from shared_py.take_trade_model import (
    MARKET_REGIME_CLASSIFIER_MODEL_NAME,
    TAKE_TRADE_MODEL_NAME,
)


def _as_metrics_dict(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            o = json.loads(raw)
            return o if isinstance(o, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


@dataclass(frozen=True)
class PromotionGateResult:
    ok: bool
    reasons: tuple[str, ...]
    details: dict[str, Any]


def evaluate_champion_promotion_gates(
    *,
    model_name: str,
    metrics_json: Any,
    metadata_json: Any,
    settings: LearningEngineSettings,
    online_drift_effective_action: str | None = None,
    promotion_scope_type: str = "global",
    promotion_scope_key: str = "",
) -> PromotionGateResult:
    if not settings.model_promotion_gates_enabled:
        return PromotionGateResult(True, (), {"skipped": True, "reason": "gates_disabled"})

    mn = (model_name or "").strip()
    mj = _as_metrics_dict(metrics_json)
    meta = parse_metadata_json(metadata_json)
    reasons: list[str] = []
    details: dict[str, Any] = {"model_name": mn}

    if mn == TAKE_TRADE_MODEL_NAME:
        cv = mj.get("cv_summary")
        if not isinstance(cv, dict):
            cv = {}
        details["cv_summary"] = cv
        wf = cv.get("walk_forward_mean_roc_auc")
        pk = cv.get("purged_kfold_mean_roc_auc")
        if wf is not None:
            try:
                wfv = float(wf)
                details["walk_forward_mean_roc_auc"] = wfv
                if wfv < float(settings.model_promotion_min_walk_forward_mean_roc_auc):
                    reasons.append("walk_forward_mean_roc_auc_below_minimum")
            except (TypeError, ValueError):
                reasons.append("walk_forward_mean_roc_auc_unparseable")
        else:
            reasons.append("walk_forward_mean_roc_auc_missing")

        if pk is not None:
            try:
                pkv = float(pk)
                details["purged_kfold_mean_roc_auc"] = pkv
                if pkv < float(settings.model_promotion_min_purged_kfold_mean_roc_auc):
                    reasons.append("purged_kfold_mean_roc_auc_below_minimum")
            except (TypeError, ValueError):
                reasons.append("purged_kfold_mean_roc_auc_unparseable")
        else:
            reasons.append("purged_kfold_mean_roc_auc_missing")

        test_auc = mj.get("roc_auc")
        if test_auc is not None:
            try:
                tauc = float(test_auc)
                details["test_roc_auc"] = tauc
                if tauc < float(settings.model_promotion_min_test_roc_auc_take_trade):
                    reasons.append("test_roc_auc_below_minimum")
            except (TypeError, ValueError):
                reasons.append("test_roc_auc_unparseable")
        else:
            reasons.append("test_roc_auc_missing")

        brier = mj.get("brier_score")
        if brier is not None:
            try:
                br = float(brier)
                details["test_brier_score"] = br
                if br > float(settings.model_promotion_max_test_brier_take_trade):
                    reasons.append("test_brier_above_maximum")
            except (TypeError, ValueError):
                reasons.append("test_brier_unparseable")
        else:
            reasons.append("test_brier_missing")

        if settings.model_promotion_fail_on_cv_symbol_leakage_take_trade:
            max_ov = int(settings.model_promotion_max_cv_symbol_overlap_folds_take_trade)
            cvsum = mj.get("cv_summary")
            if not isinstance(cvsum, dict):
                cvsum = {}
            wf_leak = cvsum.get("symbol_leakage_walk_forward") or {}
            pk_leak = cvsum.get("symbol_leakage_purged_kfold_embargo") or {}
            wf_n = (
                int(wf_leak.get("folds_with_symbol_overlap") or 0)
                if isinstance(wf_leak, dict)
                else 0
            )
            pk_n = (
                int(pk_leak.get("folds_with_symbol_overlap") or 0)
                if isinstance(pk_leak, dict)
                else 0
            )
            details["cv_symbol_overlap_folds_walk_forward"] = wf_n
            details["cv_symbol_overlap_folds_purged_kfold"] = pk_n
            if wf_n > max_ov:
                reasons.append("walk_forward_cv_symbol_overlap_exceeds_maximum")
            if pk_n > max_ov:
                reasons.append("purged_kfold_cv_symbol_overlap_exceeds_maximum")

        st_sc = (promotion_scope_type or "global").strip().lower()
        sk_sc = (promotion_scope_key or "").strip()
        if st_sc == "symbol" and sk_sc:
            try:
                tr_sym = int(meta.get("train_rows") or 0)
            except (TypeError, ValueError):
                tr_sym = 0
            details["train_rows_for_symbol_scope"] = tr_sym
            details["specialist_symbol_min_rows"] = int(settings.specialist_symbol_min_rows)
            if tr_sym < int(settings.specialist_symbol_min_rows):
                reasons.append("symbol_scope_insufficient_train_rows")

        if settings.model_promotion_require_trade_relevance_gates_take_trade:
            trs = mj.get("trade_relevance_summary")
            if not isinstance(trs, dict):
                reasons.append("trade_relevance_summary_missing")
            else:
                hcfp = trs.get("high_confidence_false_positive_rate")
                cap = float(settings.model_promotion_trade_relevance_max_high_conf_fp_rate)
                details["trade_relevance_high_conf_fp_rate"] = hcfp
                details["trade_relevance_high_conf_fp_cap"] = cap
                if hcfp is None:
                    reasons.append("trade_relevance_high_conf_fp_rate_missing")
                else:
                    try:
                        if float(hcfp) > cap:
                            reasons.append("trade_relevance_high_conf_fp_above_cap")
                    except (TypeError, ValueError):
                        reasons.append("trade_relevance_high_conf_fp_unparseable")

    elif mn == MARKET_REGIME_CLASSIFIER_MODEL_NAME:
        cv = mj.get("cv_summary")
        if not isinstance(cv, dict):
            cv = {}
        acc_wf = cv.get("walk_forward_mean_accuracy")
        acc_pk = cv.get("purged_kfold_mean_accuracy")
        details["cv_summary"] = cv
        if acc_wf is not None:
            try:
                if float(acc_wf) < float(settings.model_promotion_min_walk_forward_mean_accuracy_regime):
                    reasons.append("walk_forward_mean_accuracy_below_minimum")
            except (TypeError, ValueError):
                reasons.append("walk_forward_mean_accuracy_unparseable")
        else:
            reasons.append("walk_forward_mean_accuracy_missing")
        if acc_pk is not None:
            try:
                if float(acc_pk) < float(settings.model_promotion_min_purged_kfold_mean_accuracy_regime):
                    reasons.append("purged_kfold_mean_accuracy_below_minimum")
            except (TypeError, ValueError):
                reasons.append("purged_kfold_mean_accuracy_unparseable")
        else:
            reasons.append("purged_kfold_mean_accuracy_missing")

    # Shadow- / Safety-Evidenz (optional JSON aus Training oder Post-Shadow-Eval)
    if settings.model_promotion_require_shadow_evidence:
        shadow = meta.get("shadow_validation")
        if not isinstance(shadow, dict):
            shadow = mj.get("shadow_vs_champion")
        details["shadow_validation_present"] = isinstance(shadow, dict)
        if not isinstance(shadow, dict) or not shadow.get("passed"):
            reasons.append("shadow_evidence_missing_or_failed")

    gov_ok, gov_reasons, gov_details = evaluate_training_run_governance(
        model_name=mn,
        metadata_json=metadata_json,
        metrics_json=metrics_json,
        settings=settings,
    )
    details["governance"] = gov_details
    if not gov_ok:
        reasons.extend(gov_reasons)

    st = (promotion_scope_type or "global").strip().lower()
    sk = (promotion_scope_key or "").strip()
    if (
        settings.model_promotion_apply_online_drift_gate
        and mn == TAKE_TRADE_MODEL_NAME
        and st == "global"
        and sk == ""
        and online_drift_effective_action is not None
    ):
        eff = str(online_drift_effective_action).strip().lower() or "ok"
        blocked = parse_online_drift_promotion_block_tiers(settings)
        details["online_drift_effective_action"] = eff
        details["online_drift_promotion_blocked_tiers"] = sorted(blocked)
        if eff in blocked:
            reasons.append("online_drift_blocks_champion_promotion")

    ok = len(reasons) == 0
    return PromotionGateResult(ok, tuple(reasons), details)
