"""Online-Drift-Auswertung: Feature-Staleness, Regime, OOD-Druck, Modell-Score-Streuung (Prompt 26)."""

from __future__ import annotations

import logging
import statistics
from typing import Any

import psycopg

from learning_engine.config import LearningEngineSettings
from learning_engine.registry_v2.service import try_auto_rollback_on_drift_hard_block
from learning_engine.storage import repo_learning_v1, repo_online_drift
from shared_py.online_drift import merge_online_drift_actions

logger = logging.getLogger("learning_engine.drift.online")

_DRIFT_CLASS = "online"


def _tier(value: float, warn: float, shadow: float, block: float) -> str:
    if value >= block:
        return "hard_block"
    if value >= shadow:
        return "shadow_only"
    if value >= warn:
        return "warn"
    return "ok"


def _normalize_counts(raw: dict[str, Any] | None) -> dict[str, float]:
    if not raw:
        return {}
    total = 0.0
    for v in raw.values():
        try:
            total += float(v)
        except (TypeError, ValueError):
            continue
    if total <= 0:
        return {}
    out: dict[str, float] = {}
    for k, v in raw.items():
        key = str(k).strip().lower()
        try:
            c = float(v)
        except (TypeError, ValueError):
            continue
        if c >= 0:
            out[key] = c / total
    return out


def regime_total_variation(
    baseline: dict[str, float],
    observed_counts: dict[str, int],
) -> float:
    if not baseline or not observed_counts:
        return 0.0
    n = sum(observed_counts.values())
    if n <= 0:
        return 0.0
    obs_p = {k: v / n for k, v in observed_counts.items()}
    keys = set(baseline) | set(obs_p)
    return 0.5 * sum(abs(baseline.get(k, 0.0) - obs_p.get(k, 0.0)) for k in keys)


def _max_liquidity_age_ms(feature_snapshot: dict[str, Any] | None) -> float | None:
    if not isinstance(feature_snapshot, dict):
        return None
    ages: list[float] = []
    primary = feature_snapshot.get("primary_tf")
    if isinstance(primary, dict):
        for key in ("orderbook_age_ms", "funding_age_ms", "open_interest_age_ms"):
            v = primary.get(key)
            if v is not None:
                try:
                    ages.append(float(v))
                except (TypeError, ValueError):
                    pass
    tfs = feature_snapshot.get("timeframes")
    if isinstance(tfs, dict):
        for row in tfs.values():
            if not isinstance(row, dict):
                continue
            for key in ("orderbook_age_ms", "funding_age_ms", "open_interest_age_ms"):
                v = row.get(key)
                if v is not None:
                    try:
                        ages.append(float(v))
                    except (TypeError, ValueError):
                        pass
    if not ages:
        return None
    return max(ages)


def _signal_health_fractions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    if n <= 0:
        return {"n": 0, "ood_alert_frac": 0.0, "missing_take_trade_prob_frac": 0.0, "hard_drift_tag_frac": 0.0}
    ood_alerts = 0
    missing_prob = 0
    hard_tag = 0
    for r in rows:
        if r.get("take_trade_prob") is None:
            missing_prob += 1
        if r.get("model_ood_alert") is True:
            ood_alerts += 1
        rj = r.get("rejection_reasons_json")
        if isinstance(rj, list) and "online_drift_hard_block" in [str(x) for x in rj]:
            hard_tag += 1
    return {
        "n": n,
        "ood_alert_frac": ood_alerts / n,
        "missing_take_trade_prob_frac": missing_prob / n,
        "hard_drift_tag_frac": hard_tag / n,
    }


def _shadow_champion_prob_mae(rows: list[dict[str, Any]]) -> tuple[float | None, int]:
    diffs: list[float] = []
    for r in rows:
        snap = r.get("source_snapshot_json")
        live = r.get("take_trade_prob")
        if not isinstance(snap, dict) or live is None:
            continue
        ttm = snap.get("take_trade_model")
        if not isinstance(ttm, dict):
            continue
        raw = ttm.get("challenger_take_trade_prob")
        if raw is None:
            continue
        try:
            diffs.append(abs(float(live) - float(raw)))
        except (TypeError, ValueError):
            continue
    if not diffs:
        return None, 0
    return float(sum(diffs) / len(diffs)), len(diffs)


def _feature_stale_fraction(
    rows: list[dict[str, Any]],
    *,
    age_threshold_ms: float,
) -> tuple[float, int]:
    stale = 0
    checked = 0
    for r in rows:
        snap = r.get("source_snapshot_json")
        if not isinstance(snap, dict):
            continue
        fs = snap.get("feature_snapshot")
        mx = _max_liquidity_age_ms(fs if isinstance(fs, dict) else None)
        if mx is None:
            continue
        checked += 1
        if mx > age_threshold_ms:
            stale += 1
    if checked <= 0:
        return 0.0, 0
    return stale / checked, checked


def run_online_drift_evaluation(
    conn: psycopg.Connection[Any],
    settings: LearningEngineSettings,
) -> dict[str, Any]:
    scope = "global"
    prev = repo_online_drift.fetch_online_drift_state(conn, scope=scope)
    prev_action = str(prev["effective_action"]) if prev else "ok"
    auto_rb: dict[str, Any] | None = None

    lb = settings.online_drift_lookback_minutes
    signals = repo_online_drift.fetch_recent_signals_for_online_drift(
        conn,
        lookback_minutes=lb,
        limit=settings.online_drift_max_signals_sample,
    )
    n = len(signals)
    min_s = settings.online_drift_min_samples

    breakdown: dict[str, Any] = {
        "signal_sample_size": n,
        "lookback_minutes": lb,
        "dimensions": {},
    }

    dims: dict[str, str] = {}

    if n >= min_s:
        ood_vals = []
        for r in signals:
            v = r.get("model_ood_score_0_1")
            if v is not None:
                try:
                    ood_vals.append(float(v))
                except (TypeError, ValueError):
                    pass
        ood_mean = statistics.mean(ood_vals) if ood_vals else 0.0
        ood_tier = _tier(
            ood_mean,
            settings.online_drift_ood_mean_warn,
            settings.online_drift_ood_mean_shadow,
            settings.online_drift_ood_mean_block,
        )
        dims["ood_pressure"] = ood_tier
        breakdown["dimensions"]["ood_pressure"] = {
            "mean_0_1": ood_mean,
            "samples": len(ood_vals),
            "tier": ood_tier,
        }

        stale_frac, stale_checked = _feature_stale_fraction(
            signals,
            age_threshold_ms=float(settings.online_drift_feature_stale_age_ms),
        )
        st_tier = (
            _tier(
                stale_frac,
                settings.online_drift_stale_frac_warn,
                settings.online_drift_stale_frac_shadow,
                settings.online_drift_stale_frac_block,
            )
            if stale_checked >= min_s // 2
            else "ok"
        )
        dims["feature_staleness"] = st_tier
        breakdown["dimensions"]["feature_staleness"] = {
            "stale_fraction": stale_frac,
            "checked_signals": stale_checked,
            "tier": st_tier,
        }

        probs = []
        for r in signals:
            v = r.get("take_trade_prob")
            if v is not None:
                try:
                    probs.append(float(v))
                except (TypeError, ValueError):
                    pass
        if len(probs) >= max(3, min_s // 2):
            p_std = float(statistics.pstdev(probs))
            ps_tier = _tier(
                p_std,
                settings.online_drift_prob_std_warn,
                settings.online_drift_prob_std_shadow,
                settings.online_drift_prob_std_block,
            )
            dims["model_score_dispersion"] = ps_tier
            breakdown["dimensions"]["model_score_dispersion"] = {
                "take_trade_prob_pstdev": p_std,
                "samples": len(probs),
                "tier": ps_tier,
            }
        else:
            dims["model_score_dispersion"] = "ok"
            breakdown["dimensions"]["model_score_dispersion"] = {
                "take_trade_prob_pstdev": None,
                "samples": len(probs),
                "tier": "ok",
                "reason": "insufficient_prob_samples",
            }

        ref = repo_online_drift.fetch_take_trade_champion_reference(conn)
        meta = ref.get("metadata_json") if ref else None
        if not isinstance(meta, dict):
            meta = {}
        raw_reg = meta.get("regime_counts_train")
        baseline = _normalize_counts(raw_reg if isinstance(raw_reg, dict) else None)
        obs_counts: dict[str, int] = {}
        for r in signals:
            reg = str(r.get("market_regime") or "unknown").strip().lower() or "unknown"
            obs_counts[reg] = obs_counts.get(reg, 0) + 1
        tv = regime_total_variation(baseline, obs_counts) if baseline else 0.0
        rg_tier = (
            _tier(
                tv,
                settings.online_drift_regime_tv_warn,
                settings.online_drift_regime_tv_shadow,
                settings.online_drift_regime_tv_block,
            )
            if baseline
            else "ok"
        )
        dims["regime_distribution"] = rg_tier
        breakdown["dimensions"]["regime_distribution"] = {
            "total_variation_distance": tv,
            "has_baseline": bool(baseline),
            "tier": rg_tier,
        }

        health = _signal_health_fractions(signals)
        oaf = float(health["ood_alert_frac"])
        oa_tier = _tier(
            oaf,
            settings.online_drift_ood_alert_frac_warn,
            settings.online_drift_ood_alert_frac_shadow,
            settings.online_drift_ood_alert_frac_block,
        )
        dims["inference_ood_alert_rate"] = oa_tier
        breakdown["dimensions"]["inference_ood_alert_rate"] = {
            **health,
            "ood_alert_frac": oaf,
            "tier": oa_tier,
        }

        mpf = float(health["missing_take_trade_prob_frac"])
        mp_tier = _tier(
            mpf,
            settings.online_drift_missing_prob_frac_warn,
            settings.online_drift_missing_prob_frac_shadow,
            settings.online_drift_missing_prob_frac_block,
        )
        dims["missing_take_trade_prob"] = mp_tier
        breakdown["dimensions"]["missing_take_trade_prob"] = {
            "missing_take_trade_prob_frac": mpf,
            "tier": mp_tier,
        }

        mae_mean, mae_n = _shadow_champion_prob_mae(signals)
        if mae_mean is not None and mae_n >= max(3, min_s // 4):
            sh_tier = _tier(
                mae_mean,
                settings.online_drift_shadow_prob_mae_warn,
                settings.online_drift_shadow_prob_mae_shadow,
                settings.online_drift_shadow_prob_mae_block,
            )
        else:
            sh_tier = "ok"
        dims["shadow_champion_prob_mae"] = sh_tier
        breakdown["dimensions"]["shadow_champion_prob_mae"] = {
            "mean_abs_error": mae_mean,
            "pairs": mae_n,
            "tier": sh_tier,
            "note": "Nutzt source_snapshot_json.take_trade_model.challenger_take_trade_prob falls gesetzt",
        }
    else:
        breakdown["insufficient_sample"] = True
        dims = {
            "ood_pressure": "ok",
            "feature_staleness": "ok",
            "model_score_dispersion": "ok",
            "regime_distribution": "ok",
            "inference_ood_alert_rate": "ok",
            "missing_take_trade_prob": "ok",
            "shadow_champion_prob_mae": "ok",
        }

    effective = merge_online_drift_actions(*dims.values())
    breakdown["effective_action"] = effective
    breakdown["per_dimension_action"] = dims

    event_ids: list = []
    for kind, action in dims.items():
        if action == "ok":
            continue
        eid = repo_learning_v1.insert_drift_event(
            conn,
            metric_name=f"online_drift.{kind}",
            severity=action,
            details_json={
                "drift_class": _DRIFT_CLASS,
                "drift_kind": kind,
                "block_action": action,
                "breakdown": breakdown["dimensions"].get(kind, {}),
            },
        )
        event_ids.append(eid)

    repo_online_drift.upsert_online_drift_state(
        conn,
        scope=scope,
        effective_action=effective,
        lookback_minutes=lb,
        breakdown_json=breakdown,
        drift_event_ids=event_ids,
    )

    if effective != prev_action:
        repo_online_drift.audit_online_drift_transition(
            conn,
            previous_action=prev_action,
            new_action=effective,
            payload={"breakdown": breakdown, "drift_event_ids": [str(x) for x in event_ids]},
        )

    auto_rb = try_auto_rollback_on_drift_hard_block(
        conn,
        settings,
        previous_effective_action=prev_action,
        new_effective_action=effective,
    )
    if auto_rb is not None:
        breakdown["registry_auto_rollback"] = auto_rb

    logger.info(
        "online_drift evaluated effective=%s prev=%s sample=%s events=%s",
        effective,
        prev_action,
        n,
        len(event_ids),
    )
    return {
        "effective_action": effective,
        "previous_action": prev_action,
        "breakdown": breakdown,
        "drift_event_ids": [str(x) for x in event_ids],
        "registry_auto_rollback": auto_rb,
    }
