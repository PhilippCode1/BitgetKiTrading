"""
Laufzeit-Dispatcher nach market_family (Spot / Margin / Futures).

- Spot: 1:1, keine RISK_ALLOWED_LEVERAGE_*-Untergrenze; Wallet statt Hebel-Minimum.
- Margin: maintenance_margin_rate_0_1 (Bitget-Metadaten) im Sign-Off.
- Futures: unveraendert Hebel-Governor 7..75 bzw. Ramp.
"""

from __future__ import annotations

from typing import Any, Literal

ProductFamily = Literal["spot", "margin", "futures"]


def _as_dict(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}

RiskDispatchLane = Literal["spot_cash", "margin_maint", "futures_leveraged"]


def market_family_from_signal_row(signal_row: dict[str, Any]) -> ProductFamily:
    """Kanonisch: db_row.market_family, sonst source_snapshot.instrument, Default futures."""
    mf = str(signal_row.get("market_family") or "").strip().lower()
    if mf in ("spot", "margin", "futures"):
        return mf  # type: ignore[return-value]
    src = _as_dict(signal_row.get("source_snapshot_json"))
    inst = _as_dict(src.get("instrument"))
    mf2 = str(inst.get("market_family") or "").strip().lower()
    if mf2 in ("spot", "margin", "futures"):
        return mf2  # type: ignore[return-value]
    return "futures"


def risk_dispatch_lane(market_family: str) -> RiskDispatchLane:
    m = (market_family or "futures").strip().lower()
    if m == "spot":
        return "spot_cash"
    if m == "margin":
        return "margin_maint"
    return "futures_leveraged"


def effective_min_leverage(mf: str, config_min: int) -> int:
    return 1 if (mf or "").lower() == "spot" else int(config_min)


def max_config_risk_leverage(mf: str, risk_max: int) -> int:
    return 1 if (mf or "").lower() == "spot" else int(risk_max)


def maintenance_margin_rate_from_instrument(instrument: dict[str, Any] | None) -> float | None:
    if not instrument:
        return None
    raw = instrument.get("maintenance_margin_rate_0_1")
    if raw in (None, ""):
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if v > 1.0:
        v = v / 100.0
    return v if v >= 0.0 else None
