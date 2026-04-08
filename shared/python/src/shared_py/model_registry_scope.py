"""
Scoped Champion/Challenger-Slots: Typen und Normalisierung (Learning + Signal-Engine).
"""

from __future__ import annotations

REGISTRY_SCOPE_TYPES: tuple[str, ...] = (
    "global",
    "market_family",
    "market_cluster",
    "market_regime",
    "playbook",
    "router_slot",
    "symbol",
)


def normalize_registry_scope(*, scope_type: str, scope_key: str) -> tuple[str, str]:
    st = (scope_type or "global").strip().lower()
    if st not in REGISTRY_SCOPE_TYPES:
        raise ValueError(f"scope_type ungueltig: {scope_type!r}")
    sk = (scope_key or "").strip()
    if st == "global":
        return "global", ""
    if not sk:
        raise ValueError(f"scope_key erforderlich fuer scope_type={st}")
    if st in ("market_family", "market_regime", "market_cluster"):
        return st, sk.lower()
    if st == "symbol":
        return st, sk.upper()
    return st, sk
