from __future__ import annotations

from decimal import Decimal
from typing import Any

import psycopg

from paper_broker.config import PaperBrokerSettings
from paper_broker.risk.liquidity import escape_stop_from_liquidity
from paper_broker.risk.market_data import (
    fetch_last_candle_hl,
    fetch_latest_atr,
    fetch_last_swing,
    fetch_orderbook_top_raw,
    fetch_stop_zone_drawing,
)
from shared_py.exit_engine import EXIT_POLICY_VERSION, build_execution_context


def _atr_mult_for_tf(settings: PaperBrokerSettings, tf: str) -> Decimal:
    m = {
        "1m": settings.atr_mult_1m,
        "5m": settings.atr_mult_5m,
        "15m": settings.atr_mult_15m,
        "1h": settings.atr_mult_1h,
        "4h": settings.atr_mult_4h,
    }
    return Decimal(str(m.get(tf.strip(), settings.atr_mult_5m)))


def resolve_atr(
    conn: psycopg.Connection[Any],
    symbol: str,
    timeframe: str,
    entry: Decimal,
    settings: PaperBrokerSettings,
) -> tuple[Decimal, dict[str, Any]]:
    atr, _atrp = fetch_latest_atr(conn, symbol, timeframe)
    basis: dict[str, Any] = {"atr_window": 14, "atr_value": None, "atr_mult": str(_atr_mult_for_tf(settings, timeframe))}
    if atr is not None and atr > 0:
        basis["atr_value"] = str(atr)
        return atr, basis
    hi, lo = fetch_last_candle_hl(conn, symbol, timeframe)
    if hi is not None and lo is not None and hi > lo:
        atr = hi - lo
        basis["atr_value"] = str(atr)
        basis["source"] = "candle_hl"
        return atr, basis
    fb = Decimal(str(settings.default_atr_fallback_bps)) / Decimal("10000") * entry
    basis["atr_value"] = str(fb)
    basis["source"] = "default_bps"
    return fb, basis


def build_stop_plan(
    conn: psycopg.Connection[Any],
    *,
    symbol: str,
    timeframe: str,
    side: str,
    entry: Decimal,
    settings: PaperBrokerSettings,
    trigger_type: str,
    method_mix: dict[str, bool] | None = None,
) -> tuple[dict[str, Any], Decimal]:
    mix = method_mix or {"volatility": True, "invalidation": True, "liquidity": True}
    atr, vol_basis = resolve_atr(conn, symbol, timeframe, entry, settings)
    mult = _atr_mult_for_tf(settings, timeframe)
    s = side.lower()
    candidates: list[Decimal] = []
    if mix.get("volatility", True):
        if s == "long":
            candidates.append(entry - atr * mult)
        else:
            candidates.append(entry + atr * mult)

    inv_basis: dict[str, Any] = {"swing_ts_ms": None, "swing_price": None, "drawing_id": None}
    if mix.get("invalidation", True):
        if s == "long":
            sp, stm = fetch_last_swing(conn, symbol, timeframe, "low")
            if sp is not None:
                pad = entry * Decimal(str(settings.stop_pad_bps)) / Decimal("10000")
                candidates.append(sp - pad)
                inv_basis["swing_price"] = str(sp)
                inv_basis["swing_ts_ms"] = stm
        else:
            sp, stm = fetch_last_swing(conn, symbol, timeframe, "high")
            if sp is not None:
                pad = entry * Decimal(str(settings.stop_pad_bps)) / Decimal("10000")
                candidates.append(sp + pad)
                inv_basis["swing_price"] = str(sp)
                inv_basis["swing_ts_ms"] = stm
        dz = fetch_stop_zone_drawing(conn, symbol, timeframe)
        if dz is not None:
            geo = dz["geometry"]
            try:
                lo = Decimal(str(geo["price_low"]))
                hi = Decimal(str(geo["price_high"]))
                mid = (lo + hi) / Decimal("2")
                inv_basis["drawing_id"] = dz["drawing_id"]
                if s == "long":
                    candidates.append(lo - entry * Decimal(str(settings.stop_pad_bps)) / Decimal("10000"))
                else:
                    candidates.append(hi + entry * Decimal(str(settings.stop_pad_bps)) / Decimal("10000"))
                inv_basis["zone_mid"] = str(mid)
            except Exception:
                pass

    liq_basis: dict[str, Any] = {
        "nearest_liq_zone": None,
        "distance_bps": None,
        "adjusted_by_bps": "0",
    }
    cand0 = candidates[0] if candidates else (entry * (Decimal("1") - Decimal("0.01")) if s == "long" else entry * Decimal("1.01"))
    if s == "long":
        combined = max(candidates) if candidates else cand0
    else:
        combined = min(candidates) if candidates else cand0

    raw_ob = fetch_orderbook_top_raw(conn, symbol)
    final = combined
    if mix.get("liquidity", True) and raw_ob is not None:
        bids_r, asks_r = raw_ob
        final, liq_basis = escape_stop_from_liquidity(
            candidate=combined,
            side=side,
            entry=entry,
            bids_raw=bids_r,
            asks_raw=asks_r,
            scan_bps=Decimal(str(settings.liq_stop_scan_bps)),
            escape_bps=Decimal(str(settings.liq_stop_escape_bps)),
            avoid_bps=Decimal(str(settings.liq_stop_avoid_bps)),
        )

    plan = {
        "policy_version": EXIT_POLICY_VERSION,
        "trigger_type": trigger_type,
        "stop_price": str(final),
        "execution": build_execution_context(),
        "method_mix": {k: bool(v) for k, v in mix.items()},
        "volatility_basis": vol_basis,
        "invalidation_basis": inv_basis,
        "liquidity_basis": liq_basis,
        "quality": {"stop_quality_score": None, "risk_warnings": []},
    }
    return plan, atr
