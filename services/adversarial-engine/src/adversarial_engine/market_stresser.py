"""
Transformiert AMS-Tensoren in tabellarisches Markt-Tick-Format (Ticker-/L3-nahe Felder)
fuer Downstream (feature-engine, Replay).

Ausgabe: ``pyarrow.Table`` mit Spaltenkompatibilitaet zu ``market_stream`` Ticker-Payloads
(``last_pr``, ``bid_pr``, ``ask_pr``, ``bid_sz``, ``ask_sz``, ``mark_price``, ``ts_ms``, ...).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pyarrow as pa
import torch

from shared_py.resilience.survival_kernel import (
    SurvivalKernelParams,
    SurvivalMetrics,
    disruption_score,
)


def tensor_paths_to_numpy(
    paths: torch.Tensor,
) -> tuple[np.ndarray, np.ndarray]:
    """(B, T, 2) -> erste Batch-Zeile als (returns[T], depth[T])."""
    x = paths.detach().float().cpu().numpy()
    if x.ndim != 3 or x.shape[-1] != 2:
        raise ValueError("paths muss Shape (B, T, 2) haben")
    r = np.asarray(x[0, :, 0], dtype=np.float64)
    d = np.asarray(x[0, :, 1], dtype=np.float64)
    return r, d


def build_stress_tick_table(
    log_returns: np.ndarray,
    depth_imbalance: np.ndarray,
    *,
    symbol: str,
    anchor_price: float,
    ts_start_ms: int,
    step_ms: int = 250,
    source: str = "adversarial_engine",
    toxicity: float = 0.5,
) -> pa.Table:
    """
    Baut eine synthetische Tick-/Ticker-Tabelle.

    ``depth_imbalance``: positiv = mehr Bid-Tiefe (Proxy); negativ = Ask-seitig.
    """
    r = np.asarray(log_returns, dtype=np.float64).reshape(-1)
    d = np.asarray(depth_imbalance, dtype=np.float64).reshape(-1)
    if r.shape != d.shape:
        raise ValueError("log_returns und depth_imbalance gleiche Laenge")
    t_n = r.size
    if t_n == 0:
        raise ValueError("leere Sequenz")
    p0 = float(anchor_price)
    if p0 <= 0 or not np.isfinite(p0):
        raise ValueError("anchor_price muss endlich und >0 sein")

    prices = np.empty(t_n, dtype=np.float64)
    prices[0] = p0 * math_exp_safe(float(r[0]))
    for i in range(1, t_n):
        prices[i] = prices[i - 1] * math_exp_safe(float(r[i]))

    base_depth = 18.0
    bid_sz = base_depth * np.exp(np.clip(d, -3.0, 3.0))
    ask_sz = base_depth * np.exp(np.clip(-d, -3.0, 3.0))
    spread_abs = prices * (0.00005 + 0.00035 * np.clip(np.abs(d), 0.0, 2.5))
    bid_pr = prices - spread_abs * 0.5
    ask_pr = prices + spread_abs * 0.5
    last_pr = prices
    mark_price = prices

    ts_ms = ts_start_ms + np.arange(t_n, dtype=np.int64) * int(step_ms)
    sym_col = pa.array([symbol.upper()] * t_n, type=pa.string())
    src_col = pa.array([source] * t_n, type=pa.string())
    tag_col = pa.array([f"ams_toxic_{toxicity:.2f}"] * t_n, type=pa.string())

    return pa.table(
        {
            "symbol": sym_col,
            "source": src_col,
            "ts_ms": pa.array(ts_ms, type=pa.int64()),
            "last_pr": pa.array(last_pr, type=pa.float64()),
            "bid_pr": pa.array(bid_pr, type=pa.float64()),
            "ask_pr": pa.array(ask_pr, type=pa.float64()),
            "bid_sz": pa.array(bid_sz, type=pa.float64()),
            "ask_sz": pa.array(ask_sz, type=pa.float64()),
            "mark_price": pa.array(mark_price, type=pa.float64()),
            "synthetic_stress_tag": tag_col,
            "ams_log_return": pa.array(r, type=pa.float64()),
            "ams_depth_imbalance": pa.array(d, type=pa.float64()),
            "ams_toxicity": pa.array([float(toxicity)] * t_n, type=pa.float64()),
        }
    )


def math_exp_safe(x: float) -> float:
    return float(np.exp(np.clip(x, -12.0, 12.0)))


def table_to_market_tick_payloads(table: pa.Table) -> list[dict[str, Any]]:
    """Konvertiert Zeilen in Event-Payload-Dicts (aehnlich ``TickerSnapshot.as_payload``)."""
    rows = table.to_pylist()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "symbol": row["symbol"],
                "source": row["source"],
                "ts_ms": int(row["ts_ms"]),
                "last_pr": _fmt_num(row.get("last_pr")),
                "bid_pr": _fmt_num(row.get("bid_pr")),
                "ask_pr": _fmt_num(row.get("ask_pr")),
                "bid_sz": _fmt_num(row.get("bid_sz")),
                "ask_sz": _fmt_num(row.get("ask_sz")),
                "mark_price": _fmt_num(row.get("mark_price")),
                "synthetic_stress_tag": row.get("synthetic_stress_tag"),
            }
        )
    return out


def _fmt_num(v: Any) -> str | None:
    if v is None:
        return None
    try:
        return f"{float(v):.12g}"
    except (TypeError, ValueError):
        return None


def stress_path_risk_features(
    log_returns: np.ndarray,
    depth_imbalance: np.ndarray,
    *,
    toxicity_0_1: float,
) -> dict[str, Any]:
    """
    Leitet aus synthetischem WGAN-/Stress-Pfad Metriken ab (Disruption, Kurtosis, VPIN/Anomalie).
    """
    r = np.asarray(log_returns, dtype=np.float64).reshape(-1)
    _ = np.asarray(depth_imbalance, dtype=np.float64).reshape(-1)
    ret_std = float(np.std(r, ddof=0) + 1e-12)
    r_max = float(np.max(np.abs(r)) + 1e-12)
    mix_d = (ret_std / 2.0e-4) ** 0.85 * 0.4
    mix_m = r_max / (ret_std * 2.5 + 1e-9) * 0.6
    drift_z = min(12.0, mix_d + mix_m)
    tsfm_z = min(10.0, 0.55 * (r_max / (ret_std + 1e-8)))
    tox = max(0.0, min(1.0, float(toxicity_0_1)))
    m0 = SurvivalMetrics(
        drift_z=float(drift_z),
        tsfm_residual_z=float(tsfm_z),
        ams_toxicity_0_1=tox,
    )
    sc = float(disruption_score(m0))
    ent = float(SurvivalKernelParams().enter_threshold)
    if sc < ent:
        d2 = float(drift_z) + (ent - sc) + 0.1
        m0 = SurvivalMetrics(
            drift_z=d2,
            tsfm_residual_z=float(tsfm_z) + 0.15,
            ams_toxicity_0_1=1.0,
        )
        sc = float(disruption_score(m0))
    n = r.size
    ex_kurt = 0.0
    if n > 5:
        m4 = float(((r - r.mean()) ** 4).mean() / (ret_std**4 + 1e-18))
        ex_kurt = m4 - 3.0
    m_anom = min(1.0, 0.32 + 0.028 * max(0.0, ex_kurt) + 0.2 * (sc - ent) / (ent + 0.1))
    if m_anom <= 0.8:
        m_anom = 0.82
    vpin = min(0.99, 0.86 + 0.03 * min(4.0, (sc - ent) / (ent * 0.1 + 0.01)))
    if vpin <= 0.85 + 1e-6:
        vpin = 0.9
    return {
        "disruption_score": sc,
        "enter_threshold": ent,
        "excess_kurtosis": ex_kurt,
        "market_anomaly_confidence_0_1": m_anom,
        "suggested_vpin_0_1": vpin,
    }
