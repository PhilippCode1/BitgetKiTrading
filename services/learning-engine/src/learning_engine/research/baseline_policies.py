"""
Heuristische Baselines auf Feature-Snapshots aus trade_evaluations.

Nur fuer evidenzbasierte Vergleiche — keine Produktions-Strategie.
"""

from __future__ import annotations

from typing import Any

from shared_py.model_contracts import extract_primary_feature_snapshot


def _primary(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("feature_snapshot_json")
    if not isinstance(raw, dict):
        return {}
    p = extract_primary_feature_snapshot(raw)
    return p if isinstance(p, dict) else {}


def _f(d: dict[str, Any], key: str, default: float = 0.0) -> float:
    v = d.get(key)
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def baseline_pred_take_always_no_trade(_row: dict[str, Any]) -> int:
    return 0


def baseline_pred_take_momentum_follow(row: dict[str, Any], *, ret_threshold: float = 0.0003) -> int:
    p = _primary(row)
    ret5 = _f(p, "ret_5")
    mom = _f(p, "momentum_score")
    if ret5 > ret_threshold and mom >= 48.0:
        return 1
    return 0


def baseline_pred_take_mean_reversion_rsi(row: dict[str, Any]) -> int:
    p = _primary(row)
    rsi = _f(p, "rsi_14", 50.0)
    if rsi < 32.0 or rsi > 68.0:
        return 1
    return 0


def baseline_pred_take_conservative_quality(row: dict[str, Any]) -> int:
    """Nur wenn Spread/Execution moderat und erwartete Edge aus Zeile positiv."""
    p = _primary(row)
    spread = _f(p, "spread_bps", 999.0)
    ex = _f(p, "execution_cost_bps", 999.0)
    er = row.get("expected_return_bps")
    try:
        er_f = float(er) if er is not None else -999.0
    except (TypeError, ValueError):
        er_f = -999.0
    if spread <= 12.0 and ex <= 25.0 and er_f >= 8.0:
        return 1
    return 0


def baseline_pred_take_playbook_strategy_proxy(row: dict[str, Any]) -> int:
    """
    Grobe Playbook-Familien-Heuristik aus signal_snapshot (kein echtes Playbook-Scoring).
    Trend-Familien: Momentum-Follow; Mean-Reversion-Familien: RSI-Extrem.
    """
    snap = row.get("signal_snapshot_json")
    if not isinstance(snap, dict):
        return baseline_pred_take_momentum_follow(row)
    fam = str(snap.get("playbook_family") or "").strip().lower()
    if "mean" in fam or "range" in fam or "rotation" in fam:
        return baseline_pred_take_mean_reversion_rsi(row)
    return baseline_pred_take_momentum_follow(row)


BASELINE_REGISTRY: dict[str, Any] = {
    "always_no_trade": baseline_pred_take_always_no_trade,
    "momentum_follow": baseline_pred_take_momentum_follow,
    "mean_reversion_rsi": baseline_pred_take_mean_reversion_rsi,
    "conservative_quality": baseline_pred_take_conservative_quality,
    "playbook_strategy_proxy": baseline_pred_take_playbook_strategy_proxy,
}


def compute_baseline_vector(row: dict[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for name, fn in BASELINE_REGISTRY.items():
        out[name] = int(bool(fn(row)))
    return out
