from __future__ import annotations

from typing import Any

from learning_engine.config import LearningEngineSettings


def should_suggest_retire(metrics: dict[str, Any], settings: LearningEngineSettings) -> bool:
    pf = metrics.get("profit_factor")
    if pf is None:
        return False
    try:
        pfv = float(pf)
    except (TypeError, ValueError):
        return False
    return pfv < settings.learning_retire_pf and metrics.get("trades", 0) >= 5


def should_suggest_promote(metrics: dict[str, Any], settings: LearningEngineSettings) -> bool:
    pf = metrics.get("profit_factor")
    if pf is None or pf == float("inf"):
        return False
    try:
        pfv = float(pf)
    except (TypeError, ValueError):
        return False
    mdd = float(metrics.get("max_drawdown", 1.0))
    n = int(metrics.get("trades", 0))
    return (
        n >= 10
        and pfv >= settings.learning_promote_pf
        and mdd <= settings.learning_max_dd
    )


def retire_payload(strategy_id: str, strategy_name: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": "suggest_retire",
        "strategy_id": strategy_id,
        "strategy_name": strategy_name,
        "reason": "profit_factor_below_retire_threshold",
        "metrics": {
            "profit_factor": metrics.get("profit_factor"),
            "trades": metrics.get("trades"),
        },
        "audit_note": "Keine automatische Statusänderung — manuell prüfen/approven.",
    }


def promote_payload(strategy_id: str, strategy_name: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": "suggest_promotion",
        "strategy_id": strategy_id,
        "strategy_name": strategy_name,
        "reason": "gates_passed_v1",
        "metrics": {
            "profit_factor": metrics.get("profit_factor"),
            "max_drawdown": metrics.get("max_drawdown"),
            "trades": metrics.get("trades"),
        },
        "audit_note": "Keine Autopromotion — Registry-API mit manual_override nutzen.",
    }
