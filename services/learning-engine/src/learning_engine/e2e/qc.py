"""
QC-/Label-Felder fuer E2E-Lernrecords (heuristisch + regelbasiert).

Explizite Human-Labels koennen spaeter via API/Operator ergaenzt werden (merge in label_qc_json).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def derive_trade_close_qc_labels(
    *,
    err_labels: list[str],
    direction_correct: bool,
    stop_hit: bool,
    tp1_hit: bool,
    take_trade_prob: float | None,
    pnl_net: Decimal,
) -> dict[str, Any]:
    qc: dict[str, Any] = {}
    el = {str(x).upper() for x in err_labels}

    if "STOP_TOO_TIGHT" in el:
        qc["stop_too_tight"] = {"source": "rules_v1", "value": True}
    if "STALE_DATA" in el:
        qc["late_entry_stale_signal"] = {"source": "rules_v1", "value": True}
    if "DATA_QUALITY_GATE_FAILED" in el:
        qc["data_quality_failed"] = {"source": "learning_quality_gate", "value": True}

    ttp = None
    if take_trade_prob is not None:
        try:
            ttp = float(take_trade_prob)
        except (TypeError, ValueError):
            ttp = None
    if ttp is not None and ttp >= 0.58 and not direction_correct:
        qc["false_positive_trade_hypothesis"] = {
            "source": "heuristic",
            "take_trade_prob": ttp,
            "note_de": "Verlust trotz relativ hoher Take-Trade-Wahrscheinlichkeit — manuell pruefen.",
        }

    if stop_hit and not direction_correct:
        qc["stop_invalidation_outcome"] = {
            "source": "trade_path",
            "value": "stopped_out_loss",
        }
    elif stop_hit and direction_correct:
        qc["stop_invalidation_outcome"] = {
            "source": "trade_path",
            "value": "stopped_out_profit",
        }

    if not tp1_hit and not stop_hit and pnl_net < Decimal("0"):
        qc["poor_exit_selection_hypothesis"] = {
            "source": "heuristic",
            "note_de": "Kein TP1/Stop-Event, dennoch Verlust — Exit-Pfad pruefen.",
        }

    return qc


def operator_override_from_meta(meta: dict[str, Any]) -> dict[str, Any] | None:
    """Erkennt rudimentaere Operator-Eingriffe aus Positions-meta (erweiterbar)."""
    if not meta:
        return None
    for key in ("operator_override", "manual_close", "telegram_confirmed_close"):
        if meta.get(key):
            return {"manual_override": True, "hint_key": key}
    return None
