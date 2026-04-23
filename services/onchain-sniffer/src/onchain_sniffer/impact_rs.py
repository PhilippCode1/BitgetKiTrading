"""Rust `onchain_impact` (FFI) oder Python-Fallback — Slippage-Schaetzung (Heuristik / optional CPMM)."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from onchain_sniffer.config import OnchainSnifferSettings

_lib: ctypes.CDLL | None = None


def _load_lib(path: str | None) -> ctypes.CDLL | None:
    global _lib
    if _lib is not None:
        return _lib
    p = (path or os.environ.get("ONCHAIN_IMPACT_LIB_PATH") or "").strip()
    if not p:
        return None
    fp = Path(p)
    if not fp.is_file():
        return None
    try:
        _lib = ctypes.CDLL(str(fp))
        _lib.onchain_impact_cpmm_slippage_bps.argtypes = [
            ctypes.c_double,
            ctypes.c_double,
            ctypes.c_double,
        ]
        _lib.onchain_impact_cpmm_slippage_bps.restype = ctypes.c_double
        _lib.onchain_impact_heuristic_slippage_bps.argtypes = [ctypes.c_double, ctypes.c_double]
        _lib.onchain_impact_heuristic_slippage_bps.restype = ctypes.c_double
        return _lib
    except OSError:
        return None


def cpmm_slippage_bps_py(reserve_in: float, reserve_out: float, amount_in: float) -> float:
    if reserve_in <= 0 or reserve_out <= 0 or amount_in <= 0:
        return float("nan")
    mid = reserve_out / reserve_in
    amount_out = amount_in * reserve_out / (reserve_in + amount_in)
    exec_price = amount_out / amount_in
    return (1.0 - exec_price / mid) * 10_000.0


def heuristic_slippage_bps_py(notional_usd: float, pool_tvl_usd: float) -> float:
    tvl = max(pool_tvl_usd, 1.0)
    r = min(notional_usd / tvl, 1.0)
    return 10_000.0 * r * 0.55


def estimate_slippage_bps(settings: "OnchainSnifferSettings", notional_usd: float) -> float:
    lib = _load_lib(settings.onchain_impact_lib_path)
    rin = settings.reserve_in_hint
    rout = settings.reserve_out_hint
    if rin is not None and rout is not None and rin > 0 and rout > 0:
        amt_in = max(float(notional_usd), 1.0)
        if lib is not None:
            v = float(lib.onchain_impact_cpmm_slippage_bps(float(rin), float(rout), amt_in))
            if v == v:
                return v
        v = cpmm_slippage_bps_py(float(rin), float(rout), amt_in)
        if v == v:
            return v
    if lib is not None:
        return float(
            lib.onchain_impact_heuristic_slippage_bps(
                float(notional_usd),
                float(settings.pool_tvl_usd_hint),
            )
        )
    return heuristic_slippage_bps_py(float(notional_usd), float(settings.pool_tvl_usd_hint))
