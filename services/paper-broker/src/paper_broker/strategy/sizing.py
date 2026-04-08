from __future__ import annotations

from decimal import Decimal
from typing import Any

from shared_py.exit_engine import leverage_indexed_stop_budget_bps
from shared_py.unified_leverage_allocator import (
    extract_execution_leverage_cap_from_signal_row,
)

from paper_broker.config import PaperBrokerSettings


def qty_with_stop_budget(
    settings: PaperBrokerSettings,
    signal: dict[str, Any],
    signal_class: str,
    *,
    context: dict[str, Any],
) -> Decimal:
    """
    Skaliert Basis-Qty anhand Hebel-indexiertem Stop-Budget und Referenzpreis.

    Ohne account_equity oder reference_price im context: Fallback auf qty_for_signal_class.
    """
    base = qty_for_signal_class(settings, signal_class)
    if not settings.paper_stop_budget_sizing_enabled:
        return base
    eq_raw = context.get("account_equity")
    px_raw = context.get("reference_price")
    if eq_raw in (None, "") or px_raw in (None, ""):
        return base
    try:
        eq = Decimal(str(eq_raw))
        px = Decimal(str(px_raw))
    except Exception:
        return base
    if eq <= 0 or px <= 0:
        return base
    lev = leverage_for_signal(settings, signal)
    budget = leverage_indexed_stop_budget_bps(lev)
    if budget is None or budget <= 0:
        return base
    try:
        risk_frac = Decimal(str(settings.paper_stop_budget_equity_risk_fraction))
        cap_m = Decimal(str(settings.paper_stop_budget_qty_cap_mult))
    except Exception:
        return base
    if risk_frac <= 0 or cap_m <= 0:
        return base
    stop_frac = budget / Decimal("10000")
    if stop_frac <= 0:
        return base
    risk_usdt = eq * risk_frac
    denom = px * stop_frac
    if denom <= 0:
        return base
    q = risk_usdt / denom
    capped = base * cap_m
    if capped > 0:
        q = min(q, capped)
    if q <= 0:
        return base
    return q


def qty_for_signal_class(settings: PaperBrokerSettings, signal_class: str) -> Decimal:
    base = Decimal(str(settings.strat_base_qty_btc))
    s = signal_class.strip().lower()
    if s == "mikro":
        return base * Decimal(str(settings.micro_size_mult))
    if s == "gross":
        return base * Decimal(str(settings.gross_size_mult))
    return base


def leverage_for_signal(settings: PaperBrokerSettings, signal: dict[str, Any]) -> Decimal:
    base = max(7, min(int(settings.paper_default_leverage), int(settings.paper_max_leverage)))
    preferred = _preferred_leverage(signal)
    if preferred is not None:
        return Decimal(str(max(7, min(int(settings.paper_max_leverage), preferred))))
    if base <= 7:
        return Decimal("7")
    expected_return = _coerce_float(signal.get("expected_return_bps"))
    expected_mae = _coerce_float(signal.get("expected_mae_bps"))
    expected_mfe = _coerce_float(signal.get("expected_mfe_bps"))
    if expected_return is None or expected_mae is None or expected_mfe is None:
        return Decimal("7")
    projected_rr = expected_mfe / max(expected_mae, 1.0)
    if expected_return < float(settings.strat_min_expected_return_bps):
        return Decimal("7")
    if expected_mae > float(settings.strat_max_expected_mae_bps):
        return Decimal("7")
    if projected_rr < float(settings.strat_min_projected_rr):
        return Decimal("7")
    return Decimal(str(base))


def _preferred_leverage(signal: dict[str, Any]) -> int | None:
    cap = extract_execution_leverage_cap_from_signal_row(signal)
    if cap is not None and cap > 0:
        return cap
    for field in ("recommended_leverage", "allowed_leverage"):
        value = signal.get(field)
        if value in (None, ""):
            continue
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            return parsed
    return None


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
