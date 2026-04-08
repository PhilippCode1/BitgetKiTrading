"""Quality-Gates und Pipeline-Modi (ok / analytics_only / do_not_trade)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Literal, Sequence

from shared_py.bitget.instruments import (
    BitgetInstrumentCatalogEntry,
    BitgetInstrumentIdentity,
)

PipelineTradeMode = Literal["ok", "analytics_only", "do_not_trade"]


def validate_event_vs_resolved_metadata(
    event_instrument: BitgetInstrumentIdentity,
    entry: BitgetInstrumentCatalogEntry,
) -> list[str]:
    """Pflicht: Event-Identity und Katalogzeile duerfen nicht widerspruechlich sein."""
    issues: list[str] = []
    if event_instrument.symbol.upper() != entry.symbol.upper():
        issues.append("metadata_symbol_mismatch")
    if event_instrument.market_family != entry.market_family:
        issues.append("metadata_market_family_mismatch")
    if event_instrument.market_family == "futures":
        et = event_instrument.product_type or ""
        pt = entry.product_type or ""
        if et and pt and et.upper() != pt.upper():
            issues.append("metadata_product_type_mismatch")
    if event_instrument.market_family == "margin":
        em = event_instrument.margin_account_mode
        cm = entry.margin_account_mode
        if em != cm:
            issues.append("metadata_margin_mode_mismatch")
    return issues


def gate_tick_lot_vs_metadata(
    *,
    open_: float,
    high: float,
    low: float,
    close: float,
    base_vol: float,
    price_tick_size: str | None,
    quantity_step: str | None,
) -> list[str]:
    """
    Grobe Konsistenzpruefung Tick/Lot vs. Candle-Feldern (keine stillen Fixes).
    """
    issues: list[str] = []

    def _check_price_grid(label: str, value: float, tick: str | None) -> None:
        if tick is None or not str(tick).strip():
            return
        try:
            t = Decimal(str(tick).strip())
            v = Decimal(str(value))
        except (InvalidOperation, ValueError):
            issues.append(f"{label}_tick_parse_error")
            return
        if t <= 0:
            return
        # Rest muss Vielfaches des Ticks sein (mit kleiner Toleranz fuer Float-Noise)
        steps = (v / t).quantize(Decimal("1."))
        residual = abs(v - steps * t)
        if residual > t * Decimal("0.02"):
            issues.append(f"{label}_tick_grid_conflict")

    _check_price_grid("open", open_, price_tick_size)
    _check_price_grid("high", high, price_tick_size)
    _check_price_grid("low", low, price_tick_size)
    _check_price_grid("close", close, price_tick_size)

    if quantity_step and str(quantity_step).strip() and base_vol >= 0:
        try:
            step = Decimal(str(quantity_step).strip())
            bv = Decimal(str(base_vol))
        except (InvalidOperation, ValueError):
            issues.append("base_vol_step_parse_error")
        else:
            if step > 0 and bv > 0:
                steps = (bv / step).quantize(Decimal("1."))
                residual = abs(bv - steps * step)
                if residual > step * Decimal("0.02"):
                    issues.append("base_vol_lot_step_conflict")

    return sorted(set(issues))


def gate_cross_family_derivative_leak(
    *,
    market_family: str,
    ticker_mark: float | None,
    ticker_index: float | None,
    ticker_funding_rate: float | None,
    funding_snapshot_present: bool,
    open_interest_snapshot_present: bool,
) -> list[str]:
    """
    Spot/Margin duerfen keine Futures-Derivat-Signale aus dem kombinierten Pfad tragen.
    """
    issues: list[str] = []
    fam = market_family.lower()
    if fam in ("spot", "margin"):
        if ticker_mark is not None or ticker_index is not None:
            issues.append("cross_family:ticker_mark_index_on_spot_margin")
        if ticker_funding_rate is not None:
            issues.append("cross_family:ticker_funding_on_spot_margin")
        if funding_snapshot_present:
            issues.append("cross_family:funding_row_on_spot_margin")
        if open_interest_snapshot_present:
            issues.append("cross_family:open_interest_row_on_spot_margin")
    return issues


def sanitize_ticker_snapshot_for_family(
    snapshot: object | None,
    *,
    market_family: str,
    supports_funding: bool,
    supports_open_interest: bool,
) -> object | None:
    """Entfernt Derivat-Felder aus Ticker-Snapshots je nach Family/Capability."""
    if snapshot is None:
        return None
    fam = market_family.lower()
    from dataclasses import fields

    snap_type = type(snapshot)
    if not hasattr(snapshot, "__dataclass_fields__"):
        return snapshot

    data = {f.name: getattr(snapshot, f.name) for f in fields(snapshot)}
    if fam != "futures":
        for key in (
            "mark_price",
            "index_price",
        ):
            if key in data:
                data[key] = None
    if fam != "futures" or not supports_funding:
        for key in ("funding_rate", "next_funding_time_ms"):
            if key in data:
                data[key] = None
    if fam != "futures" or not supports_open_interest:
        if "holding_amount" in data:
            data["holding_amount"] = None
    return snap_type(**{k: data[k] for k in (f.name for f in fields(snapshot))})


def compute_data_completeness_0_1(
    *,
    market_family: str,
    market_context: object,
    realized_vol_20: float | None,
    session_drift_bps: float | None,
    supports_funding: bool,
    supports_open_interest: bool,
) -> float:
    """Completeness nur gegen das, was fuer Family+Capabilities erwartet wird."""
    checks: list[bool] = [
        True,
        realized_vol_20 is not None,
        session_drift_bps is not None,
        getattr(market_context, "spread_bps", None) is not None,
        getattr(market_context, "execution_cost_bps", None) is not None,
    ]
    fam = market_family.lower()
    if fam == "futures":
        if supports_funding:
            checks.append(getattr(market_context, "funding_rate_bps", None) is not None)
        if supports_open_interest:
            checks.append(getattr(market_context, "open_interest", None) is not None)
        checks.append(
            getattr(market_context, "mark_index_spread_bps", None) is not None
            or getattr(market_context, "basis_bps", None) is not None
        )
    return sum(1 for c in checks if c) / len(checks)


def compute_staleness_score_0_1(
    *,
    market_family: str,
    market_context: object,
    timeframe_ms: int,
    supports_funding: bool,
    supports_open_interest: bool,
) -> float:
    ratios: list[float] = []
    orderbook_age_ms = getattr(market_context, "orderbook_age_ms", None)
    if orderbook_age_ms is not None:
        threshold = max(30_000, min(timeframe_ms // 2, 300_000))
        ratios.append(min(1.0, orderbook_age_ms / threshold))
    fam = market_family.lower()
    if fam == "futures":
        if supports_funding:
            funding_age_ms = getattr(market_context, "funding_age_ms", None)
            if funding_age_ms is not None:
                ratios.append(
                    min(1.0, funding_age_ms / max(7_200_000, timeframe_ms * 4))
                )
        if supports_open_interest:
            open_interest_age_ms = getattr(market_context, "open_interest_age_ms", None)
            if open_interest_age_ms is not None:
                ratios.append(
                    min(1.0, open_interest_age_ms / max(300_000, timeframe_ms * 4))
                )
    return max(ratios or [0.0])


def compute_pipeline_trade_mode(
    *,
    hard_issues: Sequence[str],
    metadata_health_status: str,
    data_completeness: float,
    staleness_score: float,
    analytics_eligible: bool,
    live_execution_enabled: bool,
    execution_disabled: bool,
) -> PipelineTradeMode:
    """
    Handelskern-orientierter Modus:
    - do_not_trade: harte Identitaets-/Leak-Verletzungen oder kein Analytics-Pfad
    - analytics_only: Live aus oder abgeschwaechte Datenqualitaet
    - ok: fuer Live-Execution geeignet (wenn nicht execution_disabled)
    """
    if hard_issues:
        return "do_not_trade"
    if not analytics_eligible and metadata_health_status != "ok":
        return "do_not_trade"
    if metadata_health_status != "ok":
        return "analytics_only"
    quality_soft_fail = data_completeness < 0.85 or staleness_score > 0.5
    if quality_soft_fail:
        return "analytics_only"
    if execution_disabled or not live_execution_enabled:
        return "analytics_only"
    return "ok"
