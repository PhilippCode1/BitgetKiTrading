"""Explizite Feature-Namensraeume / Versionen (oeffentlich + family-spezifisch)."""

from __future__ import annotations

from shared_py.bitget.instruments import BitgetInstrumentIdentity

# BUNDLE: gemeinsame Release-Zeile fuer alle Namespaces dieses Pakets
FEATURE_NAMESPACE_BUNDLE_VERSION = "2026.03.30"

# Oeffentliche Marktdaten (Candles, Trades, generische Ticker-Bid/Ask)
NS_PUBLIC_MARKET_V1 = "feat.bitget.public_market.v1"

# Orderbuch / Slippage / Spread — family-neutral, sofern Daten vorliegen
NS_PUBLIC_MICROSTRUCTURE_V1 = "feat.bitget.public_microstructure.v1"

# Futures: Funding, Open Interest, Mark/Index/Basis (nur mit echten Capabilities)
NS_FUTURES_DERIVATIVES_V1 = "feat.bitget.futures_derivatives.v1"

# Margin: Hebel-/Kontext-Metadaten (keine Futures-Felder)
NS_MARGIN_CONTEXT_V1 = "feat.bitget.margin_context.v1"


def feature_namespaces_for_identity(identity: BitgetInstrumentIdentity) -> list[str]:
    """Aktive Namensraeume pro Instrument (Audit, Mischungs-Checks, Router)."""
    ns: list[str] = [NS_PUBLIC_MARKET_V1, NS_PUBLIC_MICROSTRUCTURE_V1]
    fam = identity.market_family
    if fam == "futures":
        if identity.supports_funding or identity.supports_open_interest:
            ns.append(NS_FUTURES_DERIVATIVES_V1)
    elif fam == "margin":
        ns.append(NS_MARGIN_CONTEXT_V1)
    return ns


def family_foreign_namespace_violations(
    *,
    market_family: str,
    active_namespaces: list[str],
) -> list[str]:
    """Family-fremde Namespace-Kombinationen (z. B. Futures-Derivate auf Spot)."""
    issues: list[str] = []
    fam = market_family.lower()
    has_fut = NS_FUTURES_DERIVATIVES_V1 in active_namespaces
    has_margin = NS_MARGIN_CONTEXT_V1 in active_namespaces
    if fam in ("spot", "margin") and has_fut:
        issues.append("namespace_mix:futures_derivatives_on_non_futures")
    if fam == "spot" and has_margin:
        issues.append("namespace_mix:margin_context_on_spot")
    if fam == "futures" and has_margin:
        issues.append("namespace_mix:margin_context_on_futures")
    return issues
