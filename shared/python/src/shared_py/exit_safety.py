from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReduceOnlyExitRequest:
    symbol: str
    requested_qty: float
    position_qty: float
    reduce_only: bool
    tp_splits_pct: list[float]
    price_step: float
    owner_context_present: bool
    safety_reason: str | None
    emergency: bool = False


def validate_reduce_only_exit(req: ReduceOnlyExitRequest) -> list[str]:
    reasons: list[str] = []
    if req.requested_qty <= 0:
        reasons.append("exit_menge_ungueltig")
    if req.requested_qty > req.position_qty:
        reasons.append("exit_menge_ueber_position")
    if not req.reduce_only:
        reasons.append("reduce_only_fehlt")
    split_sum = sum(req.tp_splits_pct)
    if split_sum > 100.0 + 1e-9:
        reasons.append("tp_split_ueber_100_prozent")
    if req.price_step <= 0:
        reasons.append("precision_step_ungueltig")
    return reasons


def validate_emergency_flatten_request(req: ReduceOnlyExitRequest) -> list[str]:
    reasons = validate_reduce_only_exit(req)
    if req.position_qty <= 0:
        reasons.append("keine_exchange_position_fuer_exit")
    if not req.owner_context_present and not req.safety_reason:
        reasons.append("owner_oder_harter_safety_grund_fehlt")
    # emergency flatten darf keine neue Position aufbauen
    if req.requested_qty > req.position_qty:
        reasons.append("emergency_flatten_wuerde_position_eroeffnen")
    return list(dict.fromkeys(reasons))


def build_exit_block_reasons_de(reasons: list[str]) -> list[str]:
    mapping = {
        "exit_menge_ungueltig": "Exit-Menge ist ungueltig.",
        "exit_menge_ueber_position": "Exit-Menge ueberschreitet die Position.",
        "reduce_only_fehlt": "Reduce-only fehlt fuer schliessende Order.",
        "tp_split_ueber_100_prozent": "TP-Splits ueberschreiten 100 Prozent.",
        "precision_step_ungueltig": "Instrument-Precision ist ungueltig.",
        "keine_exchange_position_fuer_exit": "Keine Exchange-Position fuer Exit gefunden.",
        "owner_oder_harter_safety_grund_fehlt": "Owner-Kontext oder harter Safety-Grund fehlt.",
        "emergency_flatten_wuerde_position_eroeffnen": "Emergency-Flatten wuerde neue Position eroeffnen.",
        "cancel_replace_duplicate": "Cancel/Replace erzeugt eine Duplikatorder.",
    }
    if not reasons:
        return ["Exit-Safety OK."]
    return [mapping.get(code, f"Unbekannter Exit-Blockgrund: {code}") for code in reasons]
