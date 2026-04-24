from __future__ import annotations

import json
import time
from decimal import Decimal
from typing import Any

import psycopg
from psycopg import errors as pg_errors
from psycopg.rows import dict_row


def normalize_tf_for_db(tf: str) -> str:
    x = tf.strip()
    m = {"1h": "1H", "4h": "4H"}
    return m.get(x.lower(), x)


def validate_live_symbol(symbol: str) -> str:
    """
    Bitget v2-Symbole: alphanumerisch, 4..32 Zeichen. Katalog: `assert_symbol_in_instrument_catalog`.
    """
    s = symbol.strip().upper()
    if len(s) < 4 or len(s) > 32:
        raise ValueError(
            "Symbol: 4..32 alphanumerische Zeichen. Oeffentliche Kerzen: keine Account-Keys."
        )
    if not s.isalnum():
        raise ValueError(
            "Symbol: nur Buchstaben/Ziffern, kein Trennzeichen (v2, z. B. ETHUSDT)."
        )
    return s


def assert_symbol_in_instrument_catalog(
    conn: psycopg.Connection[Any],
    *,
    symbol: str,
    market_family: str,
    product_type: str | None = None,
    margin_account_mode: str | None = None,
) -> None:
    """Katalog muss (symbol, Familie, ggf. Futures-Product, ggf. Margin-Modus) kennen."""
    sym = symbol.strip().upper()
    mf = str(market_family or "").strip().lower()
    if mf not in ("spot", "margin", "futures"):
        raise ValueError(f"market_family ungueltig: {market_family}")
    where = "symbol = %s AND market_family = %s"
    args: list[Any] = [sym, mf]
    if mf == "futures":
        if not (product_type and str(product_type).strip()):
            raise ValueError(
                "Futures: product_type erforderlich (Katalog-Disambiguierung)."
            )
        where += " AND UPPER(TRIM(product_type)) = UPPER(TRIM(%s))"
        args.append(str(product_type).strip())
    if mf == "margin":
        mode = (margin_account_mode or "isolated").strip().lower()
        if mode not in ("isolated", "crossed"):
            raise ValueError("margin: margin_account_mode muss isolated oder crossed sein.")
        where += " AND LOWER(TRIM(margin_account_mode)) = %s"
        args.append(mode)
    row = conn.execute(
        f"SELECT 1 AS ok FROM app.instrument_catalog_entries WHERE {where} LIMIT 1",
        args,
    ).fetchone()
    if row is None:
        raise ValueError(
            f"Symbol {sym} nicht im Instrumentenkatalog (family={mf}); Katalog-Refresh pruefen."
        )


LIVE_STATE_CONTRACT_VERSION = 1

# Muss zu market_stream CandleCollector TIMEFRAME_TO_MS passen
_TIMEFRAME_BAR_MS: dict[str, int] = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "1H": 3_600_000,
    "4H": 14_400_000,
}


def compute_market_freshness_payload(
    *,
    server_ts_ms: int,
    timeframe: str,
    candle_meta: dict[str, Any] | None,
    ticker_meta: dict[str, Any] | None,
    stale_warn_ms: int,
) -> dict[str, Any]:
    """
    Bewertet Kerzen- und Ticker-Frische fuer Live-Terminal (keine stillen „live“-Labels bei abgestorbenen Daten).
    """
    tf = normalize_tf_for_db(timeframe)
    tf_ms = _TIMEFRAME_BAR_MS.get(tf)
    warn = max(int(stale_warn_ms), 60_000)
    out: dict[str, Any] = {
        "status": "no_candles",
        "timeframe": tf,
        "stale_warn_ms": warn,
        "candle": None,
        "ticker": None,
    }
    if tf_ms is None:
        out["status"] = "unknown_timeframe"
        return out

    if candle_meta is None:
        return out

    last_start = int(candle_meta["start_ts_ms"])
    last_ingest = int(candle_meta["ingest_ts_ms"])
    aligned = (server_ts_ms // tf_ms) * tf_ms
    bar_lag_ms = max(0, aligned - last_start)
    ingest_age_ms = max(0, server_ts_ms - last_ingest)

    sev = 0
    if bar_lag_ms >= 5 * tf_ms or ingest_age_ms >= 3 * warn:
        sev = 3
    elif bar_lag_ms >= 2 * tf_ms or ingest_age_ms >= warn:
        sev = 2
    elif bar_lag_ms >= tf_ms or ingest_age_ms >= max(warn // 2, 30_000):
        sev = 1

    ticker_block: dict[str, Any] | None = None
    if ticker_meta is not None:
        ex_ts = int(ticker_meta["ts_ms"])
        t_ing = int(ticker_meta["ingest_ts_ms"])
        quote_age_ms = max(0, server_ts_ms - ex_ts)
        t_ing_age = max(0, server_ts_ms - t_ing)
        lp = ticker_meta.get("last_pr")
        ticker_block = {
            "exchange_ts_ms": ex_ts,
            "ingest_ts_ms": t_ing,
            "quote_age_ms": quote_age_ms,
            "ingest_age_ms": t_ing_age,
            "last_pr": float(lp) if lp is not None else None,
        }
        if t_ing_age >= 3 * warn:
            sev = max(sev, 3)
        elif t_ing_age >= warn:
            sev = max(sev, 2)
        elif t_ing_age >= max(warn // 2, 30_000):
            sev = max(sev, 1)

    status_map = ("live", "delayed", "stale", "dead")
    out["status"] = status_map[sev]
    out["candle"] = {
        "last_start_ts_ms": last_start,
        "last_ingest_ts_ms": last_ingest,
        "bar_duration_ms": tf_ms,
        "aligned_bucket_start_ms": aligned,
        "bar_lag_ms": bar_lag_ms,
        "ingest_age_ms": ingest_age_ms,
    }
    out["ticker"] = ticker_block
    return out


def fetch_latest_candle_meta(
    conn: psycopg.Connection[Any], *, symbol: str, timeframe: str
) -> dict[str, Any] | None:
    tf = normalize_tf_for_db(timeframe)
    row = conn.execute(
        """
        SELECT start_ts_ms, ingest_ts_ms
        FROM tsdb.candles
        WHERE symbol = %s AND timeframe = %s
        ORDER BY start_ts_ms DESC
        LIMIT 1
        """,
        (symbol.upper(), tf),
    ).fetchone()
    if row is None:
        return None
    return {
        "start_ts_ms": int(row["start_ts_ms"]),
        "ingest_ts_ms": int(row["ingest_ts_ms"]),
    }


def fetch_latest_ticker_meta(
    conn: psycopg.Connection[Any], *, symbol: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT ts_ms, ingest_ts_ms, last_pr
        FROM tsdb.ticker
        WHERE symbol = %s
        ORDER BY ts_ms DESC
        LIMIT 1
        """,
        (symbol.upper(),),
    ).fetchone()
    if row is None:
        return None
    return {
        "ts_ms": int(row["ts_ms"]),
        "ingest_ts_ms": int(row["ingest_ts_ms"]),
        "last_pr": row["last_pr"],
    }


def fetch_candles(
    conn: psycopg.Connection[Any],
    *,
    symbol: str,
    timeframe: str,
    limit: int,
) -> list[dict[str, Any]]:
    tf = normalize_tf_for_db(timeframe)
    rows = conn.execute(
        """
        SELECT start_ts_ms, open, high, low, close, usdt_vol
        FROM tsdb.candles
        WHERE symbol = %s AND timeframe = %s
        ORDER BY start_ts_ms DESC
        LIMIT %s
        """,
        (symbol.upper(), tf, limit),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in reversed(rows):
        start_ms = int(r["start_ts_ms"])
        out.append(
            {
                "time_s": start_ms // 1000,
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume_usdt": float(r["usdt_vol"]),
            }
        )
    return out


def fetch_latest_signal_bundle(
    conn: psycopg.Connection[Any], *, symbol: str, timeframe: str
) -> dict[str, Any] | None:
    tf = normalize_tf_for_db(timeframe)
    row = conn.execute(
        """
        SELECT s.*, e.explain_short, e.explain_long_md, e.risk_warnings_json,
               e.stop_explain_json, e.targets_explain_json
        FROM app.signals_v1 s
        LEFT JOIN app.signal_explanations e ON e.signal_id = s.signal_id
        WHERE s.symbol = %s AND s.timeframe = %s
        ORDER BY s.analysis_ts_ms DESC
        LIMIT 1
        """,
        (symbol.upper(), tf),
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    rj_raw = d.get("reasons_json")
    if isinstance(rj_raw, str):
        try:
            reasons_parsed: Any = json.loads(rj_raw)
        except json.JSONDecodeError:
            reasons_parsed = {}
    else:
        reasons_parsed = rj_raw
    rj_dict = reasons_parsed if isinstance(reasons_parsed, dict) else {}
    dcf = rj_dict.get("decision_control_flow")
    dcf_dict = dcf if isinstance(dcf, dict) else {}
    return {
        "signal_id": str(d["signal_id"]),
        "symbol": d["symbol"],
        "timeframe": d["timeframe"],
        "direction": d["direction"],
        "strategy_name": d.get("strategy_name"),
        "playbook_id": d.get("playbook_id"),
        "playbook_family": d.get("playbook_family"),
        "playbook_decision_mode": d.get("playbook_decision_mode"),
        "playbook_registry_version": d.get("playbook_registry_version"),
        "canonical_instrument_id": d.get("canonical_instrument_id"),
        "market_family": d.get("market_family"),
        "market_regime": d.get("market_regime"),
        "regime_state": d.get("regime_state"),
        "regime_substate": d.get("regime_substate"),
        "regime_transition_state": d.get("regime_transition_state"),
        "regime_transition_reasons_json": d.get("regime_transition_reasons_json") or [],
        "regime_persistence_bars": int(d["regime_persistence_bars"])
        if d.get("regime_persistence_bars") is not None
        else None,
        "regime_policy_version": d.get("regime_policy_version"),
        "regime_bias": d.get("regime_bias"),
        "regime_confidence_0_1": float(d["regime_confidence_0_1"])
        if d.get("regime_confidence_0_1") is not None
        else None,
        "regime_reasons_json": d.get("regime_reasons_json") or [],
        "signal_strength_0_100": float(d["signal_strength_0_100"]),
        "probability_0_1": float(d["probability_0_1"]),
        "take_trade_prob": float(d["take_trade_prob"])
        if d.get("take_trade_prob") is not None
        else None,
        "take_trade_model_version": d.get("take_trade_model_version"),
        "take_trade_model_run_id": str(d["take_trade_model_run_id"])
        if d.get("take_trade_model_run_id") is not None
        else None,
        "take_trade_calibration_method": d.get("take_trade_calibration_method"),
        "expected_return_bps": float(d["expected_return_bps"])
        if d.get("expected_return_bps") is not None
        else None,
        "expected_mae_bps": float(d["expected_mae_bps"])
        if d.get("expected_mae_bps") is not None
        else None,
        "expected_mfe_bps": float(d["expected_mfe_bps"])
        if d.get("expected_mfe_bps") is not None
        else None,
        "target_projection_models_json": d.get("target_projection_models_json") or [],
        "model_uncertainty_0_1": float(d["model_uncertainty_0_1"])
        if d.get("model_uncertainty_0_1") is not None
        else None,
        "uncertainty_effective_for_leverage_0_1": float(
            d["uncertainty_effective_for_leverage_0_1"]
        )
        if d.get("uncertainty_effective_for_leverage_0_1") is not None
        else None,
        "shadow_divergence_0_1": float(d["shadow_divergence_0_1"])
        if d.get("shadow_divergence_0_1") is not None
        else None,
        "model_ood_score_0_1": float(d["model_ood_score_0_1"])
        if d.get("model_ood_score_0_1") is not None
        else None,
        "model_ood_alert": bool(d.get("model_ood_alert")),
        "uncertainty_reasons_json": d.get("uncertainty_reasons_json") or [],
        "ood_reasons_json": d.get("ood_reasons_json") or [],
        "abstention_reasons_json": d.get("abstention_reasons_json") or [],
        "trade_action": d.get("trade_action"),
        "meta_trade_lane": d.get("meta_trade_lane"),
        "decision_confidence_0_1": float(d["decision_confidence_0_1"])
        if d.get("decision_confidence_0_1") is not None
        else None,
        "decision_policy_version": d.get("decision_policy_version"),
        "allowed_leverage": int(d["allowed_leverage"])
        if d.get("allowed_leverage") is not None
        else None,
        "recommended_leverage": int(d["recommended_leverage"])
        if d.get("recommended_leverage") is not None
        else None,
        "leverage_policy_version": d.get("leverage_policy_version"),
        "leverage_cap_reasons_json": d.get("leverage_cap_reasons_json") or [],
        "signal_class": d["signal_class"],
        "decision_state": d["decision_state"],
        "rejection_state": d["rejection_state"],
        "rejection_reasons_json": d.get("rejection_reasons_json") or [],
        "analysis_ts_ms": int(d["analysis_ts_ms"]),
        "reasons_json": rj_dict if rj_dict else (d.get("reasons_json") or []),
        "decision_pipeline_version": dcf_dict.get("pipeline_version"),
        "decision_control_flow": dcf_dict if dcf_dict else None,
        "explain_short": d.get("explain_short"),
        "explain_long_md": d.get("explain_long_md"),
        "risk_warnings_json": d.get("risk_warnings_json") or [],
        "stop_explain_json": d.get("stop_explain_json") or {},
        "targets_explain_json": d.get("targets_explain_json") or {},
        "reward_risk_ratio": float(d["reward_risk_ratio"])
        if d.get("reward_risk_ratio") is not None
        else None,
        "stop_distance_pct": float(d["stop_distance_pct"])
        if d.get("stop_distance_pct") is not None
        else None,
        "stop_budget_max_pct_allowed": float(d["stop_budget_max_pct_allowed"])
        if d.get("stop_budget_max_pct_allowed") is not None
        else None,
        "stop_min_executable_pct": float(d["stop_min_executable_pct"])
        if d.get("stop_min_executable_pct") is not None
        else None,
        "stop_to_spread_ratio": float(d["stop_to_spread_ratio"])
        if d.get("stop_to_spread_ratio") is not None
        else None,
        "stop_quality_0_1": float(d["stop_quality_0_1"])
        if d.get("stop_quality_0_1") is not None
        else None,
        "stop_executability_0_1": float(d["stop_executability_0_1"])
        if d.get("stop_executability_0_1") is not None
        else None,
        "stop_fragility_0_1": float(d["stop_fragility_0_1"])
        if d.get("stop_fragility_0_1") is not None
        else None,
        "stop_budget_policy_version": d.get("stop_budget_policy_version"),
    }


def fetch_latest_feature_snapshot(
    conn: psycopg.Connection[Any],
    *,
    symbol: str,
    timeframe: str,
) -> dict[str, Any] | None:
    tf = normalize_tf_for_db(timeframe)
    row = conn.execute(
        """
        SELECT canonical_instrument_id, market_family, symbol, timeframe, start_ts_ms, computed_ts_ms,
               spread_bps, bid_depth_usdt_top25, ask_depth_usdt_top25,
               orderbook_imbalance, depth_balance_ratio, depth_to_bar_volume_ratio,
               impact_buy_bps_5000, impact_sell_bps_5000,
               impact_buy_bps_10000, impact_sell_bps_10000,
               execution_cost_bps, volatility_cost_bps,
               funding_rate_bps, funding_cost_bps_window,
               open_interest, open_interest_change_pct,
               data_completeness_0_1, staleness_score_0_1, feature_quality_status,
               orderbook_age_ms, funding_age_ms, open_interest_age_ms,
               liquidity_source, funding_source, open_interest_source
        FROM features.candle_features
        WHERE symbol = %s AND timeframe = %s
        ORDER BY start_ts_ms DESC
        LIMIT 1
        """,
        (symbol.upper(), tf),
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    return {
        "canonical_instrument_id": d.get("canonical_instrument_id"),
        "market_family": d.get("market_family"),
        "symbol": str(d["symbol"]),
        "timeframe": str(d["timeframe"]),
        "start_ts_ms": int(d["start_ts_ms"]),
        "computed_ts_ms": int(d["computed_ts_ms"]),
        "spread_bps": _maybe_float(d.get("spread_bps")),
        "bid_depth_usdt_top25": _maybe_float(d.get("bid_depth_usdt_top25")),
        "ask_depth_usdt_top25": _maybe_float(d.get("ask_depth_usdt_top25")),
        "orderbook_imbalance": _maybe_float(d.get("orderbook_imbalance")),
        "depth_balance_ratio": _maybe_float(d.get("depth_balance_ratio")),
        "depth_to_bar_volume_ratio": _maybe_float(d.get("depth_to_bar_volume_ratio")),
        "impact_buy_bps_5000": _maybe_float(d.get("impact_buy_bps_5000")),
        "impact_sell_bps_5000": _maybe_float(d.get("impact_sell_bps_5000")),
        "impact_buy_bps_10000": _maybe_float(d.get("impact_buy_bps_10000")),
        "impact_sell_bps_10000": _maybe_float(d.get("impact_sell_bps_10000")),
        "execution_cost_bps": _maybe_float(d.get("execution_cost_bps")),
        "volatility_cost_bps": _maybe_float(d.get("volatility_cost_bps")),
        "funding_rate_bps": _maybe_float(d.get("funding_rate_bps")),
        "funding_cost_bps_window": _maybe_float(d.get("funding_cost_bps_window")),
        "open_interest": _maybe_float(d.get("open_interest")),
        "open_interest_change_pct": _maybe_float(d.get("open_interest_change_pct")),
        "data_completeness_0_1": _maybe_float(d.get("data_completeness_0_1")),
        "staleness_score_0_1": _maybe_float(d.get("staleness_score_0_1")),
        "feature_quality_status": d.get("feature_quality_status"),
        "orderbook_age_ms": int(d["orderbook_age_ms"]) if d.get("orderbook_age_ms") is not None else None,
        "funding_age_ms": int(d["funding_age_ms"]) if d.get("funding_age_ms") is not None else None,
        "open_interest_age_ms": int(d["open_interest_age_ms"]) if d.get("open_interest_age_ms") is not None else None,
        "liquidity_source": d.get("liquidity_source"),
        "funding_source": d.get("funding_source"),
        "open_interest_source": d.get("open_interest_source"),
    }


def _parse_geo(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


def normalize_drawing_ui(row: dict[str, Any]) -> dict[str, Any]:
    geo = _parse_geo(row.get("geometry_json"))
    dtype = str(row.get("type", ""))
    style = _parse_geo(row.get("style_json"))
    stroke = style.get("stroke") or "#888888"
    out: dict[str, Any] = {
        "drawing_id": str(row["drawing_id"]),
        "parent_id": str(row.get("parent_id", "")),
        "type": dtype,
        "timeframe": row.get("timeframe"),
        "status": row.get("status"),
        "confidence": float(row["confidence"]) if row.get("confidence") is not None else None,
        "reasons_json": row.get("reasons_json") or [],
        "price_lines": [],
        "trendline": None,
        "updated_ts_ms": int(row["updated_ts"].timestamp() * 1000)
        if row.get("updated_ts")
        else None,
    }
    kind = geo.get("kind")
    if kind == "horizontal_zone":
        try:
            lo = float(geo.get("price_low", 0))
            hi = float(geo.get("price_high", 0))
            label = geo.get("label") or dtype
            out["price_lines"].extend(
                [
                    {"price": lo, "title": f"{label}_low", "color": stroke},
                    {"price": hi, "title": f"{label}_high", "color": stroke},
                ]
            )
        except (TypeError, ValueError):
            pass
    elif kind == "two_point_line":
        try:
            pa = geo.get("point_a") or {}
            pb = geo.get("point_b") or {}
            out["trendline"] = {
                "t0_ms": int(pa.get("t_ms", 0)),
                "p0": float(pa.get("price", 0)),
                "t1_ms": int(pb.get("t_ms", 0)),
                "p1": float(pb.get("price", 0)),
                "color": stroke,
            }
        except (TypeError, ValueError):
            pass
    else:
        for key in ("price", "price_low", "price_high"):
            if key in geo:
                try:
                    out["price_lines"].append(
                        {
                            "price": float(geo[key]),
                            "title": f"{dtype}_{key}",
                            "color": stroke,
                        }
                    )
                except (TypeError, ValueError):
                    pass
    return out


def fetch_latest_drawings(
    conn: psycopg.Connection[Any],
    *,
    symbol: str,
    timeframe: str,
    limit: int,
) -> list[dict[str, Any]]:
    tf = normalize_tf_for_db(timeframe)
    rows = conn.execute(
        """
        SELECT drawing_id, parent_id, type, timeframe, status, geometry_json,
               style_json, reasons_json, confidence, updated_ts
        FROM app.drawings
        WHERE symbol = %s AND timeframe = %s AND status = 'active'
        ORDER BY updated_ts DESC
        LIMIT %s
        """,
        (symbol.upper(), tf, limit),
    ).fetchall()
    return [normalize_drawing_ui(dict(r)) for r in rows]


def fetch_structure_state_summary(
    conn: psycopg.Connection[Any],
    *,
    symbol: str,
    timeframe: str,
) -> dict[str, Any] | None:
    """Letzte Struktur-Zeile fuer Live-State / data_lineage (app.structure_state)."""
    tf = normalize_tf_for_db(timeframe)
    row = conn.execute(
        """
        SELECT last_ts_ms, trend_dir, updated_ts_ms, compression_flag
        FROM app.structure_state
        WHERE symbol = %s AND timeframe = %s
        LIMIT 1
        """,
        (symbol.upper(), tf),
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    return {
        "symbol": symbol.upper(),
        "timeframe": tf,
        "last_ts_ms": int(d["last_ts_ms"]),
        "trend_dir": str(d.get("trend_dir") or ""),
        "updated_ts_ms": int(d["updated_ts_ms"])
        if d.get("updated_ts_ms") is not None
        else None,
        "compression_flag": bool(d.get("compression_flag")),
    }


def fetch_latest_news(
    conn: psycopg.Connection[Any], *, symbol: str, limit: int
) -> list[dict[str, Any]]:
    sym = symbol.upper()
    rows = conn.execute(
        """
        SELECT news_id, source, title, published_ts_ms, relevance_score, sentiment,
               description, ingested_ts_ms
        FROM app.news_items
        WHERE title ILIKE %s OR description ILIKE %s OR content ILIKE %s
        ORDER BY COALESCE(published_ts_ms, ingested_ts_ms, 0) DESC
        LIMIT %s
        """,
        (f"%{sym}%", f"%{sym}%", f"%{sym}%", limit),
    ).fetchall()
    if not rows:
        rows = conn.execute(
            """
            SELECT news_id, source, title, published_ts_ms, relevance_score, sentiment,
                   description, ingested_ts_ms
            FROM app.news_items
            ORDER BY COALESCE(published_ts_ms, ingested_ts_ms, 0) DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        ts_ms = d.get("published_ts_ms") or d.get("ingested_ts_ms") or 0
        rel = d.get("relevance_score")
        out.append(
            {
                "news_id": str(d.get("news_id", "")),
                "source": d.get("source"),
                "title": d.get("title"),
                "published_ts_ms": int(ts_ms) if ts_ms else None,
                "relevance_score": float(rel) if rel is not None else None,
                "sentiment": str(d.get("sentiment", "")),
                "summary": (d.get("description") or "")[:280],
            }
        )
    return out


def fetch_paper_state(
    conn: psycopg.Connection[Any], *, symbol: str
) -> dict[str, Any]:
    sym = symbol.upper()
    open_rows = conn.execute(
        """
        SELECT position_id, account_id, symbol, side, qty_base, entry_price_avg,
               leverage, margin_mode, state, opened_ts_ms, updated_ts_ms, meta
        FROM paper.positions
        WHERE symbol = %s AND state IN ('open', 'partially_closed')
        ORDER BY opened_ts_ms DESC
        """,
        (sym,),
    ).fetchall()
    last_closed = conn.execute(
        """
        SELECT position_id, side, qty_base, entry_price_avg, closed_ts_ms, meta, state
        FROM paper.positions
        WHERE symbol = %s AND state IN ('closed', 'liquidated')
        ORDER BY closed_ts_ms DESC NULLS LAST
        LIMIT 1
        """,
        (sym,),
    ).fetchone()
    mark_row = conn.execute(
        """
        SELECT mark_price, last_pr, ts_ms
        FROM tsdb.ticker
        WHERE symbol = %s
        ORDER BY ts_ms DESC
        LIMIT 1
        """,
        (sym,),
    ).fetchone()
    mark = None
    if mark_row:
        mr = dict(mark_row)
        mp = mr.get("mark_price") or mr.get("last_pr")
        if mp is not None:
            mark = float(mp)

    open_positions: list[dict[str, Any]] = []
    unrealized_sum = Decimal("0")
    for r in open_rows:
        d = dict(r)
        qty = Decimal(str(d["qty_base"]))
        entry = Decimal(str(d["entry_price_avg"]))
        side = str(d["side"]).lower()
        u_pnl = Decimal("0")
        if mark is not None:
            m = Decimal(str(mark))
            if side == "long":
                u_pnl = (m - entry) * qty
            else:
                u_pnl = (entry - m) * qty
        unrealized_sum += u_pnl
        meta = d.get("meta")
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        open_positions.append(
            {
                "position_id": str(d["position_id"]),
                "side": d["side"],
                "qty_base": str(d["qty_base"]),
                "entry_price_avg": str(d["entry_price_avg"]),
                "leverage": str(d["leverage"]),
                "opened_ts_ms": int(d["opened_ts_ms"]),
                "unrealized_pnl_usdt": float(u_pnl),
                "meta": meta if isinstance(meta, dict) else {},
            }
        )

    last_trade = None
    if last_closed:
        lc = dict(last_closed)
        meta = lc.get("meta")
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        last_trade = {
            "position_id": str(lc["position_id"]),
            "side": lc["side"],
            "closed_ts_ms": int(lc["closed_ts_ms"])
            if lc.get("closed_ts_ms")
            else None,
            "state": lc.get("state"),
            "meta": meta if isinstance(meta, dict) else {},
        }

    return {
        "open_positions": open_positions,
        "last_closed_trade": last_trade,
        "unrealized_pnl_usdt": float(unrealized_sum),
        "mark_price": mark,
    }


def fetch_online_drift_state_row(conn: psycopg.Connection[Any]) -> dict[str, Any] | None:
    """Materialisierter Online-Drift (learning-engine); fuer Live-State / Proxy."""
    try:
        row = conn.execute(
            """
            SELECT scope, effective_action, computed_at, lookback_minutes, breakdown_json
            FROM learn.online_drift_state
            WHERE scope = 'global'
            LIMIT 1
            """
        ).fetchone()
    except pg_errors.UndefinedTable:
        return None
    if row is None:
        return None
    r = dict(row)
    return {
        "scope": r["scope"],
        "effective_action": r["effective_action"],
        "computed_at": r["computed_at"].isoformat() if r.get("computed_at") else None,
        "lookback_minutes": r.get("lookback_minutes"),
        "breakdown_json": r.get("breakdown_json") or {},
    }


def fetch_demo_data_notice(
    conn: psycopg.Connection,
    *,
    news_fixture_mode: bool,
    bitget_demo_enabled: bool,
) -> dict[str, Any]:
    """
    Kennzeichnet sichtbare Demo-/Fixture-Pfade fuer das Dashboard (Banner).
    Keine Heuristik fuer einzelne Kerzen ohne Marker — nur ENV + DB-Spuren.
    """
    reasons: list[str] = []
    if news_fixture_mode:
        reasons.append("news_fixture_mode")
    if bitget_demo_enabled:
        reasons.append("bitget_demo_enabled")
    row = conn.execute(
        """
        SELECT
          EXISTS (
            SELECT 1 FROM app.schema_migrations sm
            WHERE sm.filename LIKE '%local_demo%'
               OR sm.filename ~ '^[0-9]+_demo_'
          ) AS sm_demo,
          EXISTS (
            SELECT 1 FROM app.news_items WHERE source = 'local_demo_seed' LIMIT 1
          ) AS news_seed,
          EXISTS (
            SELECT 1 FROM tsdb.ticker WHERE source = 'local_demo_seed' LIMIT 1
          ) AS ticker_seed,
          EXISTS (
            SELECT 1 FROM learn.strategies WHERE name = 'demo_local_seed' LIMIT 1
          ) AS strat_seed,
          EXISTS (
            SELECT 1 FROM app.model_runs WHERE dataset_hash = 'local_demo_dataset_hash' LIMIT 1
          ) AS model_seed
        """
    ).fetchone()
    if row is not None:
        if bool(row["sm_demo"]):
            reasons.append("schema_migration_demo_trace")
        if bool(row["news_seed"]):
            reasons.append("db_row_demo_news")
        if bool(row["ticker_seed"]):
            reasons.append("db_row_demo_ticker")
        if bool(row["strat_seed"]):
            reasons.append("db_row_demo_strategy")
        if bool(row["model_seed"]):
            reasons.append("db_row_demo_model_runs")

    ordered: list[str] = []
    seen: set[str] = set()
    for r in reasons:
        if r not in seen:
            seen.add(r)
            ordered.append(r)

    return {"show_banner": len(ordered) > 0, "reasons": ordered}


def build_data_lineage(
    *,
    symbol: str,
    timeframe: str,
    health_db: str,
    health_redis: str,
    candles: list[Any],
    latest_signal: Any,
    latest_feature: Any,
    latest_structure: dict[str, Any] | None,
    latest_drawings: list[Any],
    latest_news: list[Any],
    paper_state: dict[str, Any],
    online_drift: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """
    Erklaert je Teilstrecke, ob Daten vorliegen und wer sie normalerweise befuellt.
    Fuer Dashboard: keine stillen Luecken ohne Text; differenziert DB-, Redis- und Upstream-Mangel.
    """
    db_ok = health_db == "ok"
    redis_ok = health_redis == "ok"
    _cc = "events:candle_close"
    _su = "events:structure_updated"
    _du = "events:drawing_updated"

    def seg(
        segment_id: str,
        label_de: str,
        label_en: str,
        has_data: bool,
        producer_de: str,
        producer_en: str,
        why_empty_de: str,
        why_empty_en: str,
        next_step_de: str,
        next_step_en: str,
        *,
        diagnostic_tags: list[str] | None = None,
    ) -> dict[str, Any]:
        row: dict[str, Any] = {
            "segment_id": segment_id,
            "label_de": label_de,
            "label_en": label_en,
            "has_data": has_data,
            "producer_de": producer_de,
            "producer_en": producer_en,
            "why_empty_de": "" if has_data else why_empty_de,
            "why_empty_en": "" if has_data else why_empty_en,
            "next_step_de": "" if has_data else next_step_de,
            "next_step_en": "" if has_data else next_step_en,
        }
        if diagnostic_tags:
            row["diagnostic_tags"] = diagnostic_tags
        return row

    has_candles = len(candles) > 0
    has_features = latest_feature is not None
    has_structure = latest_structure is not None
    has_drawings = len(latest_drawings) > 0
    has_signal = latest_signal is not None
    has_news = len(latest_news) > 0
    ps = paper_state or {}
    has_paper = bool(ps.get("open_positions")) or ps.get("last_closed_trade") is not None
    has_drift = online_drift is not None and bool(str(online_drift.get("effective_action") or "").strip())

    feat_tags: list[str] = []
    if not has_features:
        if not db_ok:
            feat_why_de = "Datenbank nicht erreichbar — `features.candle_features` nicht lesbar."
            feat_why_en = "Database unreachable — cannot read `features.candle_features`."
            feat_tags.append("db_unavailable")
        elif not has_candles:
            feat_why_de = (
                "Keine Kerzen in `tsdb.candles` fuer dieses Symbol/TF — feature-engine braucht "
                "persistierte Kerzen und `" + _cc + "` vom market-stream."
            )
            feat_why_en = (
                "No rows in `tsdb.candles` for this symbol/TF — feature-engine needs persisted "
                "candles and `" + _cc + "` from market-stream."
            )
            feat_tags.append("upstream:missing_candles")
        elif not redis_ok:
            feat_why_de = (
                "Redis nicht erreichbar — Consumer-Gruppe `feature-engine` kann `" + _cc + "` "
                "nicht zuverlaessig lesen (Pending/Lag moeglich)."
            )
            feat_why_en = (
                "Redis unreachable — consumer group `feature-engine` may not read `" + _cc + "` "
                "(pending/lag possible)."
            )
            feat_tags.append("redis_unavailable")
        else:
            feat_why_de = (
                "Kerzen sind in der DB, aber kein Feature-Snapshot: `feature-engine` pruefen "
                "(`/health`, `processed_events`, DLQ), Instrument-Katalog und Event-Alter/"
                "Qualitaetsgatter."
            )
            feat_why_en = (
                "Candles exist in DB but no feature snapshot: check `feature-engine` "
                "(`/health`, `processed_events`, DLQ), instrument catalog, event age/quality gates."
            )
            feat_tags.append("producer:feature_engine_or_dlq")
        feat_next_de = (
            "`feature-engine` /ready; Redis `XINFO GROUPS` auf `" + _cc + "`; Logs bei DLQ."
        )
        feat_next_en = (
            "`feature-engine` /ready; Redis `XINFO GROUPS` on `" + _cc + "`; logs if DLQ."
        )
    else:
        feat_why_de = feat_why_en = feat_next_de = feat_next_en = ""

    struct_tags: list[str] = []
    if not has_structure:
        if not db_ok:
            struct_why_de = "Datenbank nicht erreichbar — `app.structure_state` nicht lesbar."
            struct_why_en = "Database unreachable — cannot read `app.structure_state`."
            struct_tags.append("db_unavailable")
        elif not has_candles:
            struct_why_de = (
                "Keine Kerzen — structure-engine verarbeitet `" + _cc + "` und benoetigt "
                "Lookback in `tsdb.candles`."
            )
            struct_why_en = (
                "No candles — structure-engine consumes `" + _cc + "` and needs lookback in "
                "`tsdb.candles`."
            )
            struct_tags.append("upstream:missing_candles")
        elif not redis_ok:
            struct_why_de = (
                "Redis nicht erreichbar — Gruppe `structure-engine` kann `" + _cc + "` nicht lesen."
            )
            struct_why_en = (
                "Redis unreachable — `structure-engine` group cannot read `" + _cc + "`."
            )
            struct_tags.append("redis_unavailable")
        else:
            struct_why_de = (
                "Kerzen da, aber kein `app.structure_state`: `structure-engine` (`/health`), "
                "zu wenig Bars fuer Pivot-Lookback, nicht unterstuetztes TF, oder interne Skips "
                "(Logs). ATR kommt optional aus `features.candle_features` (Fallback moeglich)."
            )
            struct_why_en = (
                "Candles present but no `app.structure_state`: check `structure-engine` (`/health`), "
                "insufficient bars for pivot lookback, unsupported TF, or internal skips (logs). "
                "ATR may use `features.candle_features` but fallback exists."
            )
            struct_tags.append("producer:structure_engine")
        struct_next_de = (
            "`structure-engine` /ready; Logs zu „zu wenig Candles“; Stream `" + _cc + "`."
        )
        struct_next_en = "`structure-engine` /ready; logs for insufficient candles; stream `" + _cc + "`."
    else:
        struct_why_de = struct_why_en = struct_next_de = struct_next_en = ""

    draw_tags: list[str] = []
    if not has_drawings:
        if not db_ok:
            draw_why_de = "Datenbank nicht erreichbar — `app.drawings` nicht lesbar."
            draw_why_en = "Database unreachable — cannot read `app.drawings`."
            draw_tags.append("db_unavailable")
        elif not has_structure:
            draw_why_de = (
                "Kein Eintrag in `app.structure_state` — drawing-engine konsumiert `" + _su + "` "
                "und baut aus Struktur + Orderbuch."
            )
            draw_why_en = (
                "No `app.structure_state` row — drawing-engine consumes `" + _su + "` and builds "
                "from structure + order book."
            )
            draw_tags.append("upstream:missing_structure")
        elif not redis_ok:
            draw_why_de = (
                "Redis nicht erreichbar — Gruppe `drawing-engine` kann `" + _su + "` nicht lesen."
            )
            draw_why_en = (
                "Redis unreachable — `drawing-engine` group cannot read `" + _su + "`."
            )
            draw_tags.append("redis_unavailable")
        else:
            draw_why_de = (
                "Struktur vorhanden, aber keine aktiven Drawings: `drawing-engine` (`/health`, "
                "`last_drawing_skip`), Orderbuch-Frische (`tsdb` Raw), oder keine geometrischen "
                "Kandidaten."
            )
            draw_why_en = (
                "Structure present but no active drawings: check `drawing-engine` (`/health`, "
                "`last_drawing_skip`), order book freshness, or no geometric candidates."
            )
            draw_tags.append("producer:drawing_engine")
        draw_next_de = (
            "`drawing-engine` /ready; `" + _su + "` und Orderbuch-Pfad pruefen; optional Demo siehe Doku 11."
        )
        draw_next_en = (
            "`drawing-engine` /ready; verify `" + _su + "` and order book path; optional demo doc 11."
        )
    else:
        draw_why_de = draw_why_en = draw_next_de = draw_next_en = ""

    sig_tags: list[str] = []
    if not has_signal:
        missing: list[str] = []
        if not has_candles:
            missing.append("candles")
        if not has_features:
            missing.append("features")
        if not has_structure:
            missing.append("structure")
        if not has_drawings:
            missing.append("drawings")
        if not db_ok:
            sig_why_de = "Datenbank nicht erreichbar — `app.signals_v1` nicht lesbar."
            sig_why_en = "Database unreachable — cannot read `app.signals_v1`."
            sig_tags.append("db_unavailable")
        elif missing:
            sig_why_de = (
                "Signal-Pipeline unvollstaendig (fehlt: "
                + ", ".join(missing)
                + "). signal-engine starten, wenn Vorstufen gruen sind."
            )
            sig_why_en = (
                "Signal pipeline incomplete (missing: "
                + ", ".join(missing)
                + "). Start signal-engine once upstream segments are healthy."
            )
            sig_tags.append("upstream:incomplete")
        else:
            sig_why_de = (
                "Kerzen, Features, Struktur und Drawings sind vorhanden — `signal-engine` "
                "liefert noch kein Signal (Regeln, news-engine, Filter)."
            )
            sig_why_en = (
                "Candles, features, structure and drawings present — `signal-engine` has not "
                "emitted a signal yet (rules, news-engine, filters)."
            )
            sig_tags.append("producer:signal_engine")
        sig_next_de = "`signal-engine` /ready; Redis `events:signal_created`; Logs."
        sig_next_en = "`signal-engine` /ready; Redis `events:signal_created`; logs."
    else:
        sig_why_de = sig_why_en = sig_next_de = sig_next_en = ""

    out: list[dict[str, Any]] = [
        seg(
            "candles",
            "Kerzen (Chart)",
            "Candles (chart)",
            has_candles,
            "market-stream → Postgres `tsdb.candles` (+ Redis `events:candle_close` fuer SSE)",
            "market-stream → Postgres `tsdb.candles` (+ Redis `events:candle_close` for SSE)",
            "Keine Kerzenzeilen fuer dieses Symbol/Timeframe in der DB."
            if db_ok
            else "Datenbank nicht erreichbar oder nicht konfiguriert.",
            "No candle rows for this symbol/timeframe in the database."
            if db_ok
            else "Database unreachable or not configured.",
            "Compose: `market-stream` healthy lassen; Watchlist/Symbole pruefen. Optional lokal: "
            "BITGET_ALLOW_DEMO_SCHEMA_SEEDS=true + migrate --demo-seeds (infra/migrations/postgres_demo)."
            if db_ok
            else "Postgres/Migration pruefen (`migrate`-Service, DATABASE_URL).",
            "Keep `market-stream` healthy; check watchlist/symbols. Optional local: "
            "BITGET_ALLOW_DEMO_SCHEMA_SEEDS=true + migrate --demo-seeds (postgres_demo)."
            if db_ok
            else "Check Postgres/migrations (`migrate` service, DATABASE_URL).",
        ),
        seg(
            "features",
            "Microstructure / Features",
            "Microstructure / features",
            has_features,
            "feature-engine → `features.candle_features` (Redis-Consumer `" + _cc + "`, Gruppe `feature-engine`)",
            "feature-engine → `features.candle_features` (Redis consumer `" + _cc + "`, group `feature-engine`)",
            feat_why_de,
            feat_why_en,
            feat_next_de,
            feat_next_en,
            diagnostic_tags=feat_tags if not has_features else None,
        ),
        seg(
            "structure",
            "Marktstruktur (Trend/Swings)",
            "Market structure (trend/swings)",
            has_structure,
            "structure-engine → `app.structure_state` / `app.structure_events` (publiziert `" + _su + "`)",
            "structure-engine → `app.structure_state` / `app.structure_events` (publishes `" + _su + "`)",
            struct_why_de,
            struct_why_en,
            struct_next_de,
            struct_next_en,
            diagnostic_tags=struct_tags if not has_structure else None,
        ),
        seg(
            "drawings",
            "Zeichnungen",
            "Drawings",
            has_drawings,
            "drawing-engine → `app.drawings` (Redis-Consumer `" + _su + "`, SSE `" + _du + "`)",
            "drawing-engine → `app.drawings` (Redis consumer `" + _su + "`, SSE `" + _du + "`)",
            draw_why_de,
            draw_why_en,
            draw_next_de,
            draw_next_en,
            diagnostic_tags=draw_tags if not has_drawings else None,
        ),
        seg(
            "signals",
            "Signale",
            "Signals",
            has_signal,
            "signal-engine → `app.signals_v1` (+ `events:signal_created`)",
            "signal-engine → `app.signals_v1` (+ `events:signal_created`)",
            sig_why_de,
            sig_why_en,
            sig_next_de,
            sig_next_en,
            diagnostic_tags=sig_tags if not has_signal else None,
        ),
        seg(
            "news",
            "News",
            "News",
            has_news,
            "news-engine / LLM-Orchestrator → `app.news_items` (+ `events:news_scored`)",
            "news-engine / LLM orchestrator → `app.news_items` (+ `events:news_scored`)",
            "Keine passenden News (Symbol-Filter im Text) oder Tabelle leer.",
            "No matching news (symbol filter in text) or table empty.",
            "news-engine starten oder optional Demo-News via postgres_demo / NEWS_FIXTURE_MODE. Dashboard faellt auf globale News zurueck.",
            "Start news-engine or optional demo news via postgres_demo / NEWS_FIXTURE_MODE. Dashboard falls back to global news.",
        ),
        seg(
            "paper",
            "Paper-Trading",
            "Paper trading",
            has_paper,
            "paper-broker → `paper.positions` (+ `events:trade_*`); Mark aus `tsdb.ticker`",
            "paper-broker → `paper.positions` (+ `events:trade_*`); mark from `tsdb.ticker`",
            "Keine offene/geschlossene Paper-Position fuer dieses Symbol.",
            "No open/closed paper position for this symbol.",
            "paper-broker an Signale koppeln; bei leerem Ticker optional Demo-Mark via postgres_demo.",
            "Couple paper-broker to signals; if ticker empty optional demo mark via postgres_demo.",
        ),
        seg(
            "drift",
            "Online-Drift (Learning)",
            "Online drift (learning)",
            has_drift,
            "learning-engine schreibt `learn.online_drift_state` (Evaluator/Scheduler)",
            "learning-engine writes `learn.online_drift_state` (evaluator/scheduler)",
            "Kein Drift-State (Tabelle fehlt oder noch nicht befuellt)."
            if db_ok
            else "DB nicht verfuegbar.",
            "No drift state (table missing or not filled yet)."
            if db_ok
            else "Database unavailable.",
            "learning-engine und Migration 400 (`online_drift_state`) pruefen; ggf. `/v1/learning/online-drift/evaluate` triggern."
            if db_ok
            else "Postgres pruefen, Migration-Job ausfuehren; DATABASE_URL auf den Dienst `postgres` zeigen.",
            "Check learning-engine and migration 400 (`online_drift_state`); optionally trigger `/v1/learning/online-drift/evaluate`."
            if db_ok
            else "Check Postgres, run migration job; point DATABASE_URL at the `postgres` service.",
        ),
        seg(
            "live_sse",
            "Echtzeit-Push (SSE)",
            "Real-time push (SSE)",
            redis_ok,
            "api-gateway `/v1/live/stream` liest Redis-Streams (`events:*`)",
            "api-gateway `/v1/live/stream` reads Redis streams (`events:*`)",
            "Redis nicht erreichbar oder REDIS_URL leer — nur HTTP-Polling moeglich.",
            "Redis unreachable or REDIS_URL empty — HTTP polling only.",
            "Redis-Container und REDIS_URL pruefen; LIVE_SSE_ENABLED=true im Gateway.",
            "Check Redis container and REDIS_URL; set LIVE_SSE_ENABLED=true on the gateway.",
        ),
    ]
    return out


def build_live_state(
    dsn: str,
    *,
    symbol: str,
    timeframe: str,
    limit: int,
    stale_warn_ms: int = 900_000,
    news_fixture_mode: bool = False,
    bitget_demo_enabled: bool = False,
) -> dict[str, Any]:
    server_ts_ms = int(time.time() * 1000)
    health_db = "error"
    health_redis = "skipped"
    candles: list[dict[str, Any]] = []
    latest_signal = None
    latest_feature = None
    latest_drawings: list[dict[str, Any]] = []
    latest_news: list[dict[str, Any]] = []
    paper_state: dict[str, Any] = {
        "open_positions": [],
        "last_closed_trade": None,
        "unrealized_pnl_usdt": 0.0,
        "mark_price": None,
    }
    online_drift: dict[str, Any] | None = None
    candle_meta: dict[str, Any] | None = None
    ticker_meta: dict[str, Any] | None = None
    latest_structure: dict[str, Any] | None = None
    demo_data_notice: dict[str, Any] = {"show_banner": False, "reasons": []}
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            health_db = "ok"
            demo_data_notice = fetch_demo_data_notice(
                conn,
                news_fixture_mode=news_fixture_mode,
                bitget_demo_enabled=bitget_demo_enabled,
            )
            candles = fetch_candles(conn, symbol=symbol, timeframe=timeframe, limit=limit)
            latest_signal = fetch_latest_signal_bundle(
                conn, symbol=symbol, timeframe=timeframe
            )
            latest_feature = fetch_latest_feature_snapshot(
                conn, symbol=symbol, timeframe=timeframe
            )
            latest_structure = fetch_structure_state_summary(
                conn, symbol=symbol, timeframe=timeframe
            )
            latest_drawings = fetch_latest_drawings(
                conn, symbol=symbol, timeframe=timeframe, limit=80
            )
            latest_news = fetch_latest_news(conn, symbol=symbol, limit=15)
            paper_state = fetch_paper_state(conn, symbol=symbol)
            online_drift = fetch_online_drift_state_row(conn)
            candle_meta = fetch_latest_candle_meta(
                conn, symbol=symbol, timeframe=timeframe
            )
            ticker_meta = fetch_latest_ticker_meta(conn, symbol=symbol)
    except psycopg.Error:
        health_db = "error"
        env_only: list[str] = []
        if news_fixture_mode:
            env_only.append("news_fixture_mode")
        if bitget_demo_enabled:
            env_only.append("bitget_demo_enabled")
        demo_data_notice = {"show_banner": len(env_only) > 0, "reasons": env_only}

    market_freshness = compute_market_freshness_payload(
        server_ts_ms=server_ts_ms,
        timeframe=timeframe,
        candle_meta=candle_meta,
        ticker_meta=ticker_meta,
        stale_warn_ms=stale_warn_ms,
    )
    if health_db != "ok":
        prev_status = market_freshness.get("status")
        market_freshness = {**market_freshness, "candle": None, "ticker": None}
        if prev_status != "unknown_timeframe":
            market_freshness["status"] = "no_candles"

    try:
        rurl = __import__("os").environ.get("REDIS_URL", "").strip()
        if rurl:
            from shared_py.redis_client import get_or_create_sync_pooled_client

            r = get_or_create_sync_pooled_client(
                rurl,
                role="gateway_db_live_state",
                decode_responses=True,
                max_connections=8,
            )
            if r.ping():
                health_redis = "ok"
            else:
                health_redis = "error"
    except Exception:
        health_redis = "error"

    data_lineage = build_data_lineage(
        symbol=symbol,
        timeframe=timeframe,
        health_db=health_db,
        health_redis=health_redis,
        candles=candles,
        latest_signal=latest_signal,
        latest_feature=latest_feature,
        latest_structure=latest_structure,
        latest_drawings=latest_drawings,
        latest_news=latest_news,
        paper_state=paper_state,
        online_drift=online_drift,
    )

    return {
        "live_state_contract_version": LIVE_STATE_CONTRACT_VERSION,
        "symbol": symbol.upper(),
        "timeframe": normalize_tf_for_db(timeframe),
        "server_ts_ms": server_ts_ms,
        "candles": candles,
        "latest_signal": latest_signal,
        "latest_feature": latest_feature,
        "structure_state": latest_structure,
        "latest_drawings": latest_drawings,
        "latest_news": latest_news,
        "paper_state": paper_state,
        "online_drift": online_drift,
        "data_lineage": data_lineage,
        "health": {"db": health_db, "redis": health_redis},
        "market_freshness": market_freshness,
        "demo_data_notice": demo_data_notice,
    }


def _maybe_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
