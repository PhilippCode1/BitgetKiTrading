"""
Family-neutraler Kern: Zeichnungen aus Struktur + Orderbuch.
Spezifika (z. B. Futures-Liquiditaets-Cluster) nur ueber diesen Adapter.
"""

from __future__ import annotations

from typing import Any, Mapping


def structure_gates_for_family(
    market_family: str | None,
    *,
    analytics_eligible: bool | None = None,
) -> dict[str, Any]:
    """Optionale Gate-Hinweise fuer Downstream (keine Secrets, keine Rohdaten)."""
    fam = (market_family or "").lower()
    out: dict[str, Any] = {
        "market_family": fam or None,
        "bos_choch_family_neutral": True,
        "liquidity_overlay": "public_orderbook",
    }
    if fam == "futures":
        out["optional_overlays"] = ("liquidation_proxy",)
    elif fam == "margin":
        out["optional_overlays"] = ("leverage_aware_zones",)
    else:
        out["optional_overlays"] = ()
    if analytics_eligible is not None:
        out["analytics_only_context"] = bool(analytics_eligible)
    return out


def apply_family_drawing_hints(
    records: list[dict[str, Any]],
    *,
    market_family: str | None,
    instrument_context: Mapping[str, Any] | None = None,
) -> None:
    """In-place: nur Begruendungen/Metadaten anreichern — keine Preislogik aendern."""
    _ = instrument_context
    fam = (market_family or "").lower()
    if not fam:
        return
    for rec in records:
        reasons = list(rec.get("reasons") or [])
        tag = f"family:{fam}"
        if tag not in reasons:
            reasons.append(tag)
        rec["reasons"] = reasons
