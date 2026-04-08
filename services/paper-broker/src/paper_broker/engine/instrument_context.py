"""Signal- und Katalog-Kontext fuer Multi-Asset Paper-Execution (Bitget-Metadaten)."""

from __future__ import annotations

from typing import Any


def instrument_hints_from_signal(signal: dict[str, Any] | None) -> dict[str, Any]:
    """
    Liest marktbezogene Felder aus Signal/Payload (app.signals_v1 / Event).

    Keine Defaults fuer Familie/Product — leer lassen, dann greift Broker-ENV.
    """
    if not isinstance(signal, dict):
        return {}
    out: dict[str, Any] = {}
    mf = signal.get("market_family")
    if mf not in (None, ""):
        out["market_family"] = str(mf).strip().lower()
    pt = signal.get("product_type")
    if pt not in (None, ""):
        out["product_type"] = str(pt).strip().upper()
    cid = signal.get("canonical_instrument_id")
    if cid not in (None, ""):
        out["canonical_instrument_id"] = str(cid).strip()
    mam = signal.get("margin_account_mode")
    if mam not in (None, ""):
        out["margin_account_mode"] = str(mam).strip().lower()
    return out


def execution_context_for_position(
    hints: dict[str, Any],
    *,
    catalog_entry_dict: dict[str, Any] | None,
) -> dict[str, Any]:
    ctx = {k: v for k, v in hints.items() if v not in (None, "")}
    if isinstance(catalog_entry_dict, dict):
        ctx["catalog_symbol"] = catalog_entry_dict.get("symbol")
        ctx["catalog_trading_status"] = catalog_entry_dict.get("trading_status")
        if not ctx.get("canonical_instrument_id"):
            cid = catalog_entry_dict.get("canonical_instrument_id")
            if cid:
                ctx["canonical_instrument_id"] = str(cid)
        if not ctx.get("market_family") and catalog_entry_dict.get("market_family"):
            ctx["market_family"] = str(catalog_entry_dict.get("market_family")).lower()
        if not ctx.get("product_type") and catalog_entry_dict.get("product_type"):
            ctx["product_type"] = str(catalog_entry_dict.get("product_type")).upper()
    return ctx
