"""
Kanonicaler Vertrag fuer Spezialisten-Vorschlaege im hierarchischen Ensemble.

Zweck:
- Einheitliches, maschinenlesbares Schema fuer Basismodell, Family-, Regime- und
  Playbook-Spezialisten (und spaetere zusaetzliche Experten).
- Keine LLM-Felder: alles deterministisch aus Scores, Features und Policy.

Training vs. Inferenz:
- **Basismodell**: siehe `FEATURE_FIELD_GROUPS` / `FEATURE_GROUP_SPECIALIST_SCOPE`
  in `shared_py.model_contracts` (core + quality + Teile von microstructure).
- **Family**: `FEATURE_FIELD_GROUPS["family"]` + identity; nur fuer
  `market_family in {spot, margin, futures}` sinnvoll trainierbar.
- **Regime**: Structure/News/Regime-Labels aus Signal-Pipeline (kein separates
  Feature-Vector-Training in diesem Repo-Pfad; Kalibrierung ueber gespeicherte
  Regime-Snapshots).
- **Playbook**: Playbook-Registry + Primary-Features (Kompression, MR, Range, Funding).

Versionierung: Minor-Bump bei hinzugefuegten Pflichtfeldern oder Semantik-Aenderung.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

MappingLike = dict[str, Any]

SPECIALIST_PROPOSAL_VERSION = "1.1"
ENSEMBLE_ROUTER_VERSION = "ensemble-router-v3"
ENSEMBLE_ADVERSARY_VERSION = "ensemble-adversary-v2"

# Erweiterungspunkt: neue Rollen hier und in specialist_proposals/run_adversary_check eintragen.
REGISTERED_SPECIALIST_ROLES: tuple[str, ...] = (
    "base",
    "family",
    "product_margin",
    "liquidity_vol_cluster",
    "regime",
    "playbook",
    "symbol",
)

SpecialistRole = Literal[
    "base",
    "family",
    "product_margin",
    "liquidity_vol_cluster",
    "regime",
    "playbook",
    "symbol",
]
Direction3 = Literal["long", "short", "neutral"]


class LeverageBand(TypedDict, total=False):
    """Relative Hebelspanne 0..1 (Anteil der Engine-`allowed_leverage`); nur Hinweis fuer Risk."""

    min_fraction_0_1: float
    max_fraction_0_1: float


class SpecialistProposalV1(TypedDict, total=False):
    proposal_version: str
    specialist_role: SpecialistRole
    specialist_id: str
    direction: Direction3
    no_trade_probability_0_1: float
    expected_edge_bps: float | None
    expected_mae_bps: float | None
    expected_mfe_bps: float | None
    exit_family_primary: str | None
    exit_families_ranked: list[str]
    stop_budget_0_1: float
    stop_budget_hint_0_1: float
    leverage_band: LeverageBand
    leverage_band_hint: LeverageBand
    uncertainty_0_1: float
    reasons: list[str]


def empty_proposal(
    *,
    role: SpecialistRole,
    specialist_id: str,
    reasons: list[str] | None = None,
) -> SpecialistProposalV1:
    lb: LeverageBand = {"min_fraction_0_1": 0.0, "max_fraction_0_1": 1.0}
    return {
        "proposal_version": SPECIALIST_PROPOSAL_VERSION,
        "specialist_role": role,
        "specialist_id": specialist_id,
        "direction": "neutral",
        "no_trade_probability_0_1": 1.0,
        "expected_edge_bps": None,
        "expected_mae_bps": None,
        "expected_mfe_bps": None,
        "exit_family_primary": None,
        "exit_families_ranked": [],
        "stop_budget_0_1": 0.5,
        "stop_budget_hint_0_1": 0.5,
        "leverage_band": dict(lb),
        "leverage_band_hint": dict(lb),
        "uncertainty_0_1": 1.0,
        "reasons": list(reasons or []),
    }


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


_VALID_ROLES = frozenset(REGISTERED_SPECIALIST_ROLES)


def normalize_proposal(raw: MappingLike) -> SpecialistProposalV1:
    """Minimal normalisieren (defensiv fuer Snapshots)."""
    if not isinstance(raw, dict):
        return empty_proposal(role="base", specialist_id="invalid", reasons=["proposal_not_a_dict"])
    role = raw.get("specialist_role")
    if role not in _VALID_ROLES:
        role = "base"
    sid = str(raw.get("specialist_id") or "").strip() or "unknown"
    out = empty_proposal(role=role, specialist_id=sid)  # type: ignore[arg-type]
    d = str(raw.get("direction") or "neutral").strip().lower()
    out["direction"] = d if d in ("long", "short", "neutral") else "neutral"
    out["no_trade_probability_0_1"] = clamp01(float(raw.get("no_trade_probability_0_1") or 1.0))
    ee = raw.get("expected_edge_bps")
    out["expected_edge_bps"] = float(ee) if ee is not None and ee != "" else None
    for key in ("expected_mae_bps", "expected_mfe_bps"):
        v = raw.get(key)
        out[key] = float(v) if v is not None and v != "" else None  # type: ignore[literal-required]
    out["exit_family_primary"] = (
        str(raw["exit_family_primary"]).strip() if raw.get("exit_family_primary") else None
    )
    ef = raw.get("exit_families_ranked")
    out["exit_families_ranked"] = [str(x).strip() for x in ef] if isinstance(ef, list) else []
    out["stop_budget_0_1"] = clamp01(float(raw.get("stop_budget_0_1") or 0.5))
    sbh = raw.get("stop_budget_hint_0_1")
    out["stop_budget_hint_0_1"] = (
        clamp01(float(sbh)) if sbh is not None and sbh != "" else out["stop_budget_0_1"]
    )
    lb = raw.get("leverage_band")
    if isinstance(lb, dict):
        out["leverage_band"] = {
            "min_fraction_0_1": clamp01(float(lb.get("min_fraction_0_1") or 0.0)),
            "max_fraction_0_1": clamp01(float(lb.get("max_fraction_0_1") or 1.0)),
        }
    lbh = raw.get("leverage_band_hint")
    if isinstance(lbh, dict):
        out["leverage_band_hint"] = {
            "min_fraction_0_1": clamp01(float(lbh.get("min_fraction_0_1") or 0.0)),
            "max_fraction_0_1": clamp01(float(lbh.get("max_fraction_0_1") or 1.0)),
        }
    elif "leverage_band" in out:
        out["leverage_band_hint"] = dict(out["leverage_band"])
    out["uncertainty_0_1"] = clamp01(float(raw.get("uncertainty_0_1") or 1.0))
    rs = raw.get("reasons")
    out["reasons"] = [str(x) for x in rs] if isinstance(rs, list) else []
    return out
