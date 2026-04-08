from __future__ import annotations

from typing import Any

from learning_engine.analytics import error_patterns, promotion_gates
from learning_engine.config import LearningEngineSettings
from shared_py.model_contracts import extract_primary_feature_snapshot


def build_signal_and_risk_recommendations(
    rows: list[dict[str, Any]],
    settings: LearningEngineSettings,
) -> list[dict[str, Any]]:
    """Deterministische Regeln — keine ML-Blackbox."""
    recs: list[dict[str, Any]] = []
    n_loss = sum(1 for r in rows if error_patterns._dec_loss(r))
    if n_loss == 0:
        n_loss = 1

    high_tf_conflict_losses = error_patterns.label_frequency_on_losses(rows, "HIGH_TF_CONFLICT")
    if high_tf_conflict_losses >= 3 and high_tf_conflict_losses / n_loss >= 0.2:
        recs.append(
            {
                "type": "signal_weights",
                "payload": {
                    "rule": "high_tf_conflict_on_losses",
                    "suggestion": "Erhöhe SIGNAL_WEIGHT_MULTI_TIMEFRAME oder LEARN_MULTI_TF_THRESHOLD / Gate strenger.",
                    "evidence": {
                        "loss_trades_with_label": high_tf_conflict_losses,
                        "loss_trade_sample": n_loss,
                    },
                },
            }
        )

    stop_tight = error_patterns.label_frequency_on_losses(rows, "STOP_TOO_TIGHT")
    if stop_tight >= 3 and stop_tight / n_loss >= 0.15:
        recs.append(
            {
                "type": "risk_rules",
                "payload": {
                    "rule": "stop_too_tight",
                    "suggestion": "Erhöhe LEARN_STOP_MIN_ATR_MULT oder STOP_MIN_ATR_MULT um 0.05–0.15.",
                    "evidence": {"loss_trades_with_label": stop_tight},
                },
            }
        )

    costly_or_thin_losses = _costly_or_thin_loss_count(rows)
    if costly_or_thin_losses >= 3 and costly_or_thin_losses / n_loss >= 0.15:
        recs.append(
            {
                "type": "execution_gates",
                "payload": {
                    "rule": "cost_or_liquidity_drag_on_losses",
                    "suggestion": (
                        "Verschärfe SIGNAL_MAX_SPREAD_BPS / SIGNAL_MAX_EXECUTION_COST_BPS "
                        "und handle ticker-Fallback nur noch als reject."
                    ),
                    "evidence": {
                        "loss_trades_with_cost_or_liquidity_drag": costly_or_thin_losses,
                        "loss_trade_sample": n_loss,
                    },
                },
            }
        )

    return recs


def build_promotion_recommendations(
    strategy_id: str,
    strategy_name: str,
    metrics: dict[str, Any],
    settings: LearningEngineSettings,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if promotion_gates.should_suggest_retire(metrics, settings):
        out.append(
            {
                "type": "retire",
                "payload": promotion_gates.retire_payload(strategy_id, strategy_name, metrics),
            }
        )
    elif promotion_gates.should_suggest_promote(metrics, settings):
        out.append(
            {
                "type": "promotion",
                "payload": promotion_gates.promote_payload(strategy_id, strategy_name, metrics),
            }
        )
    return out


def _costly_or_thin_loss_count(rows: list[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        if not error_patterns._dec_loss(row):
            continue
        feat = extract_primary_feature_snapshot(row.get("feature_snapshot_json"))
        execution_cost = _feature_float(feat, "execution_cost_bps")
        spread = _feature_float(feat, "spread_bps")
        depth_ratio = _feature_float(feat, "depth_to_bar_volume_ratio")
        liquidity_source = str(feat.get("liquidity_source") or "").strip()
        if execution_cost is not None and execution_cost > 18.0:
            count += 1
            continue
        if spread is not None and spread > 8.0:
            count += 1
            continue
        if depth_ratio is not None and depth_ratio < 0.35:
            count += 1
            continue
        if liquidity_source and liquidity_source != "orderbook_levels":
            count += 1
    return count


def _feature_float(feat: dict[str, Any], field: str) -> float | None:
    value = feat.get(field)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
