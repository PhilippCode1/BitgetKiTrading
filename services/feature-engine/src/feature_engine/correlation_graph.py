"""
Apex Correlation Engine: TradFi (SPY, GLD, UUP) vs Krypto (BTC, ETH).

- Yahoo-Chart-API (query1.finance.yahoo.com) fuer OHLCV-Closes
- Rollierende Pearson-Korrelation (pandas) je Fenster 5m / 1h / 1d
- Volatilitaets-Spillover: C^{-1} * impulse ueber apex_core (Rust) mit NumPy-Fallback
- Stale-Fallback: letzte gueltige Matrix aus Redis + in-memory State
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np
import pandas as pd
from scipy.stats import zscore

logger = logging.getLogger("feature_engine.correlation_graph")

ASSET_ORDER: tuple[str, ...] = ("BTC", "ETH", "SPY", "GLD", "UUP")
YAHOO_SYMBOLS: dict[str, str] = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SPY": "SPY",
    "GLD": "GLD",
    "UUP": "UUP",
}

REDIS_LAST_SNAPSHOT_KEY = "apex:correlation:last_snapshot_v1"

HORIZONS: tuple[dict[str, Any], ...] = (
    {"id": "5m", "interval": "5m", "range": "7d", "window": 72},
    {"id": "1h", "interval": "1h", "range": "60d", "window": 48},
    {"id": "1d", "interval": "1d", "range": "730d", "window": 60},
)


@dataclass
class CorrelationEngineState:
    """Letzte gueltige Matrizen pro Horizont (RAM-Fallback neben Redis)."""

    matrices: dict[str, list[list[float]]] = field(default_factory=dict)
    spillovers: dict[str, list[float]] = field(default_factory=dict)
    updated_ts_ms: int = 0


def _fetch_yahoo_closes_sync(
    symbol_yahoo: str,
    *,
    interval: str,
    range_: str,
    timeout_sec: float = 25.0,
) -> pd.Series:
    import httpx

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol_yahoo}"
    params = {"interval": interval, "range": range_}
    with httpx.Client(timeout=timeout_sec) as client:
        r = client.get(url, params=params, headers={"User-Agent": "bitget-btc-ai-correlation/1.0"})
        r.raise_for_status()
        body = r.json()
    chart = body.get("chart") or {}
    results = chart.get("result")
    if not results:
        raise ValueError(f"yahoo: leeres chart result fuer {symbol_yahoo}")
    res0 = results[0]
    ts = res0.get("timestamp") or []
    quote = (res0.get("indicators") or {}).get("quote") or [{}]
    closes = (quote[0] or {}).get("close") or []
    if not ts or not closes or len(ts) != len(closes):
        raise ValueError(f"yahoo: ungueltige serie {symbol_yahoo}")
    idx = pd.to_datetime(ts, unit="s", utc=True)
    s = pd.Series(closes, index=idx, dtype="float64").dropna()
    s = s[~s.index.duplicated(keep="last")]
    return s.sort_index()


def _log_returns(closes: pd.Series) -> pd.Series:
    x = np.log(closes.astype(float))
    return x.diff().dropna()


def _shrink_correlation(corr: np.ndarray, eps: float = 0.06) -> np.ndarray:
    n = corr.shape[0]
    eye = np.eye(n, dtype=np.float64)
    m = (1.0 - eps) * corr + eps * eye
    # Symmetrisieren (Numerik)
    return (m + m.T) / 2.0


def _spillover_scores(corr: np.ndarray, impulse: np.ndarray) -> list[float]:
    n = corr.shape[0]
    flat = corr.astype(np.float64).ravel(order="C")
    imp = impulse.astype(np.float64).ravel()
    if imp.shape[0] != n:
        return [0.0] * n
    try:
        import apex_core  # type: ignore[import-not-found]

        out = np.array(
            apex_core.compute_corr_inv_impulse(np.ascontiguousarray(flat), int(n), np.ascontiguousarray(imp)),
            dtype=np.float64,
        )
        return [float(x) for x in out.tolist()]
    except Exception as exc:
        logger.debug("apex_core spillover fallback numpy: %s", exc)
        try:
            inv = np.linalg.inv(corr)
            y = inv @ imp
            return [float(v) for v in y.tolist()]
        except np.linalg.LinAlgError:
            return [0.0] * n


def _rolling_corr_matrix(returns: pd.DataFrame, window: int) -> tuple[np.ndarray, list[str]]:
    cols = [c for c in ASSET_ORDER if c in returns.columns]
    if not cols:
        raise ValueError("returns ohne bekannte Spalten")
    sub = returns[cols].dropna(how="any")
    if len(sub) < max(5, window // 4):
        raise ValueError("zu wenig Zeilen fuer Korrelation")
    tail = sub.tail(int(window))
    cmat = tail.corr(method="pearson").reindex(index=cols, columns=cols)
    cmat = cmat.fillna(0.0)
    for i, a in enumerate(cols):
        cmat.loc[a, a] = 1.0
    return cmat.values.astype(np.float64), cols


def detect_regime_divergence(returns_1h: pd.DataFrame) -> tuple[bool, float, dict[str, float]]:
    """
    UUP (Dollar-Staerke-Proxy) vs BTC: starke Dollar-Bewegung, BTC kaum Reaktion -> Decoupling-Hinweis.
    Nutzt summierte Log-Returns ueber ca. 12h.
    """
    need = ("UUP", "BTC")
    if not all(k in returns_1h.columns for k in need):
        return False, 0.0, {}
    tail = returns_1h[list(need)].dropna(how="any").tail(12)
    if len(tail) < 6:
        return False, 0.0, {}
    u = float(tail["UUP"].sum())
    b = float(tail["BTC"].sum())
    ab = abs(b)
    # UUP steigt (Risk-Off USD) waehrend BTC nicht mitzieht
    triggered = bool(u > 0.0045 and ab < 0.0018)
    score = min(1.0, max(0.0, (u - 0.0045) * 120.0) * (1.0 - min(1.0, ab / 0.0025)))
    return triggered, float(score), {"uup_sum_logret_12h": u, "btc_sum_logret_12h": b}


def build_horizon_bundle(
    *,
    horizon: Mapping[str, Any],
    series_by_asset: dict[str, pd.Series],
    state: CorrelationEngineState,
) -> dict[str, Any]:
    hid = str(horizon["id"])
    window = int(horizon["window"])
    frames = []
    stale_assets: list[str] = []
    for a in ASSET_ORDER:
        s = series_by_asset.get(a)
        if s is None or s.empty:
            stale_assets.append(a)
            continue
        r = _log_returns(s)
        r.name = a
        frames.append(r)
    if not frames:
        raise RuntimeError("keine TradFi/Krypto-Serien")
    merged = pd.concat(frames, axis=1, join="inner").dropna(how="any")
    if merged.shape[0] < 8:
        raise RuntimeError("merge zu kurz")
    raw_mat, cols = _rolling_corr_matrix(merged, window)
    order_idx = [ASSET_ORDER.index(c) for c in cols]
    # volle 5x5 mit Identitaet wo Spalte fehlt
    n_full = len(ASSET_ORDER)
    full = np.eye(n_full, dtype=np.float64)
    for i, ci in enumerate(cols):
        ii = ASSET_ORDER.index(ci)
        for j, cj in enumerate(cols):
            jj = ASSET_ORDER.index(cj)
            full[ii, jj] = raw_mat[i, j]
    shrunk = _shrink_correlation(full)
    last_ret = merged[list(cols)].tail(1).values.flatten()
    imp = np.zeros(n_full, dtype=np.float64)
    for i, c in enumerate(cols):
        imp[ASSET_ORDER.index(c)] = float(last_ret[i])
    try:
        imp_z = zscore(imp, nan_policy="omit")
        imp_z = np.nan_to_num(imp_z, nan=0.0, posinf=0.0, neginf=0.0)
    except Exception:
        imp_z = imp
    spill = _spillover_scores(shrunk, imp_z)
    state.matrices[hid] = [list(map(float, row)) for row in shrunk.tolist()]
    state.spillovers[hid] = spill
    return {
        "horizon": hid,
        "window_bars": window,
        "labels": list(ASSET_ORDER),
        "correlation_matrix": [list(map(float, row)) for row in shrunk.tolist()],
        "spillover_impulse": [float(x) for x in imp_z.tolist()],
        "spillover_scores": spill,
        "stale_assets": stale_assets,
        "sample_rows": int(merged.shape[0]),
    }


def load_cached_snapshot(redis: Any | None) -> dict[str, Any] | None:
    if redis is None:
        return None
    try:
        raw = redis.get(REDIS_LAST_SNAPSHOT_KEY)
        if not raw:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.debug("redis get snapshot: %s", exc)
        return None


def persist_snapshot(redis: Any | None, snapshot: dict[str, Any]) -> None:
    if redis is None:
        return
    try:
        redis.setex(REDIS_LAST_SNAPSHOT_KEY, 86_400, json.dumps(snapshot, separators=(",", ":")))
    except Exception as exc:
        logger.debug("redis set snapshot: %s", exc)


def compute_correlation_snapshot(
    *,
    redis: Any | None,
    state: CorrelationEngineState | None,
) -> tuple[dict[str, Any], CorrelationEngineState]:
    st = state or CorrelationEngineState()
    series_5m: dict[str, pd.Series] = {}
    series_1h: dict[str, pd.Series] = {}
    series_1d: dict[str, pd.Series] = {}
    per_ticker_stale: dict[str, bool] = {a: False for a in ASSET_ORDER}

    for a in ASSET_ORDER:
        y = YAHOO_SYMBOLS[a]
        try:
            series_5m[a] = _fetch_yahoo_closes_sync(y, interval="5m", range_="7d")
            series_1h[a] = _fetch_yahoo_closes_sync(y, interval="1h", range_="60d")
            series_1d[a] = _fetch_yahoo_closes_sync(y, interval="1d", range_="730d")
        except Exception as exc:
            logger.warning("yahoo fetch fehlgeschlagen asset=%s: %s", a, exc)
            per_ticker_stale[a] = True
            # Versuche Redis-Zwischenspeicher (einfacher JSON pro Asset)
            if redis is not None:
                try:
                    raw = redis.get(f"apex:corr:series:{y}")
                    if raw:
                        obj = json.loads(raw)
                        idx = pd.to_datetime(obj["ts"], utc=True)
                        series_5m[a] = pd.Series(obj["c"], index=idx, dtype="float64")
                        series_1h[a] = series_5m[a].copy()
                        series_1d[a] = series_5m[a].copy()
                except Exception:
                    pass

    # erfolgreiche Serien cachen
    if redis is not None:
        for a in ASSET_ORDER:
            s = series_5m.get(a)
            if s is None or s.empty or per_ticker_stale.get(a):
                continue
            try:
                tail = s.tail(400)
                payload = {
                    "ts": [int(ts.timestamp()) for ts in tail.index],
                    "c": [float(x) for x in tail.values.tolist()],
                }
                redis.setex(f"apex:corr:series:{YAHOO_SYMBOLS[a]}", 3600, json.dumps(payload))
            except Exception:
                pass

    horizons_out: dict[str, Any] = {}
    used_fallback = False
    for h in HORIZONS:
        hid = str(h["id"])
        src = series_5m if hid == "5m" else series_1h if hid == "1h" else series_1d
        try:
            horizons_out[hid] = build_horizon_bundle(horizon=h, series_by_asset=src, state=st)
        except Exception as exc:
            logger.warning("horizon %s bundle failed: %s", hid, exc)
            prev = st.matrices.get(hid)
            prev_sp = st.spillovers.get(hid)
            if prev is not None:
                used_fallback = True
                horizons_out[hid] = {
                    "horizon": hid,
                    "window_bars": int(h["window"]),
                    "labels": list(ASSET_ORDER),
                    "correlation_matrix": prev,
                    "spillover_scores": prev_sp or [0.0] * len(ASSET_ORDER),
                    "stale_fallback": True,
                }
            else:
                horizons_out[hid] = {
                    "horizon": hid,
                    "error": str(exc)[:200],
                    "stale_fallback": True,
                }

    merged_1h = pd.concat(
        [_log_returns(series_1h[a]).rename(a) for a in ASSET_ORDER if a in series_1h and not series_1h[a].empty],
        axis=1,
        join="inner",
    ).dropna(how="any")
    div_ok, div_score, div_dbg = detect_regime_divergence(merged_1h)

    ts_ms = int(time.time() * 1000)
    snapshot = {
        "schema_version": "apex_correlation_v1",
        "computed_ts_ms": ts_ms,
        "event_name": "INTERMARKET_CORRELATION_UPDATE",
        "assets": list(ASSET_ORDER),
        "per_asset_stale": per_ticker_stale,
        "horizons": horizons_out,
        "regime_divergence": {
            "triggered": div_ok,
            "score_0_1": div_score,
            "debug": div_dbg,
        },
        "engine_meta": {
            "yahoo_intervals": {h["id"]: {"interval": h["interval"], "range": h["range"]} for h in HORIZONS},
            "used_matrix_fallback": used_fallback,
        },
    }
    st.updated_ts_ms = ts_ms
    persist_snapshot(redis, snapshot)
    return snapshot, st


def correlation_dedupe_key(snapshot: Mapping[str, Any]) -> str:
    h = snapshot.get("horizons") or {}
    m5 = json.dumps(h.get("5m", {}).get("correlation_matrix") or [], separators=(",", ":"))[:2000]
    raw = f"{snapshot.get('computed_ts_ms')}|{m5}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:48]
