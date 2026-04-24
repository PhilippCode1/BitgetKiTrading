from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from typing import Annotated, Any, AsyncIterator

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg.rows import dict_row

from api_gateway.auth import GatewayAuthContext, require_live_stream_access, require_sensitive_auth
from api_gateway.config import get_gateway_settings
from api_gateway.db import DatabaseHealthError, get_database_url
from api_gateway.db_live_queries import (
    assert_symbol_in_instrument_catalog,
    build_live_state,
    normalize_tf_for_db,
    validate_live_symbol,
)
from api_gateway.gateway_read_envelope import NEXT_STEP_DB, merge_read_envelope
from shared_py.eventbus import LIVE_SSE_STREAMS

logger = logging.getLogger("api_gateway.live")

router = APIRouter(prefix="/v1/live", tags=["live"])

# Live-SSE: Teilmenge der Pflicht-Streams (UI/Chart); kanonisch in shared/contracts/catalog/event_streams.json
STREAMS = LIVE_SSE_STREAMS


def _coalesce_allow(ts_deque: deque[float], max_per_sec: int) -> bool:
    now = time.monotonic()
    while ts_deque and now - ts_deque[0] > 1.0:
        ts_deque.popleft()
    if len(ts_deque) >= max_per_sec:
        return False
    ts_deque.append(now)
    return True


def _map_envelope_to_sse(
    env: dict[str, Any], *, symbol: str, timeframe: str
) -> tuple[str, str] | None:
    et = str(env.get("event_type", ""))
    esym = str(env.get("symbol", "")).upper()
    if esym and esym != symbol.upper():
        return None
    tf_env = env.get("timeframe")
    pl = env.get("payload") or {}
    nft = normalize_tf_for_db(timeframe)

    if et == "candle_close":
        if tf_env and normalize_tf_for_db(str(tf_env)) != nft:
            return None
        try:
            start_ms = int(pl.get("start_ts_ms", 0))
            bar = {
                "time_s": start_ms // 1000,
                "open": float(pl.get("open", 0)),
                "high": float(pl.get("high", 0)),
                "low": float(pl.get("low", 0)),
                "close": float(pl.get("close", 0)),
                "volume_usdt": float(pl.get("usdt_vol", pl.get("quote_vol", 0))),
            }
        except (TypeError, ValueError):
            return None
        return "candle", json.dumps(bar, separators=(",", ":"))

    if et == "signal_created":
        ui = {
            "signal_id": str(pl.get("signal_id", env.get("dedupe_key", ""))),
            "direction": pl.get("direction"),
            "canonical_instrument_id": pl.get("canonical_instrument_id"),
            "market_family": pl.get("market_family"),
            "market_regime": pl.get("market_regime"),
            "regime_state": pl.get("regime_state"),
            "regime_substate": pl.get("regime_substate"),
            "regime_transition_state": pl.get("regime_transition_state"),
            "regime_transition_reasons_json": pl.get("regime_transition_reasons_json"),
            "regime_persistence_bars": pl.get("regime_persistence_bars"),
            "regime_policy_version": pl.get("regime_policy_version"),
            "regime_bias": pl.get("regime_bias"),
            "regime_confidence_0_1": pl.get("regime_confidence_0_1"),
            "regime_reasons_json": pl.get("regime_reasons_json"),
            "signal_strength_0_100": pl.get("signal_strength_0_100"),
            "probability_0_1": pl.get("probability_0_1"),
            "take_trade_prob": pl.get("take_trade_prob"),
            "take_trade_model_version": pl.get("take_trade_model_version"),
            "take_trade_model_run_id": pl.get("take_trade_model_run_id"),
            "take_trade_calibration_method": pl.get("take_trade_calibration_method"),
            "expected_return_bps": pl.get("expected_return_bps"),
            "expected_mae_bps": pl.get("expected_mae_bps"),
            "expected_mfe_bps": pl.get("expected_mfe_bps"),
            "model_uncertainty_0_1": pl.get("model_uncertainty_0_1"),
            "uncertainty_effective_for_leverage_0_1": pl.get("uncertainty_effective_for_leverage_0_1"),
            "shadow_divergence_0_1": pl.get("shadow_divergence_0_1"),
            "model_ood_score_0_1": pl.get("model_ood_score_0_1"),
            "model_ood_alert": pl.get("model_ood_alert"),
            "strategy_name": pl.get("strategy_name"),
            "playbook_id": pl.get("playbook_id"),
            "playbook_family": pl.get("playbook_family"),
            "playbook_decision_mode": pl.get("playbook_decision_mode"),
            "abstention_reasons_json": pl.get("abstention_reasons_json"),
            "trade_action": pl.get("trade_action"),
            "decision_confidence_0_1": pl.get("decision_confidence_0_1"),
            "decision_policy_version": pl.get("decision_policy_version"),
            "allowed_leverage": pl.get("allowed_leverage"),
            "recommended_leverage": pl.get("recommended_leverage"),
            "leverage_policy_version": pl.get("leverage_policy_version"),
            "leverage_cap_reasons_json": pl.get("leverage_cap_reasons_json"),
            "signal_class": pl.get("signal_class"),
            "timeframe": pl.get("timeframe", tf_env),
            "decision_pipeline_version": pl.get("decision_pipeline_version"),
            "decision_control_flow": pl.get("decision_control_flow"),
            "stop_budget_outcome": pl.get("stop_budget_outcome"),
            "stop_distance_pct": pl.get("stop_distance_pct"),
            "stop_budget_max_pct_allowed": pl.get("stop_budget_max_pct_allowed"),
            "stop_min_executable_pct": pl.get("stop_min_executable_pct"),
            "stop_to_spread_ratio": pl.get("stop_to_spread_ratio"),
            "stop_quality_0_1": pl.get("stop_quality_0_1"),
            "stop_executability_0_1": pl.get("stop_executability_0_1"),
            "stop_fragility_0_1": pl.get("stop_fragility_0_1"),
            "stop_budget_policy_version": pl.get("stop_budget_policy_version"),
            "raw": pl,
        }
        return "signal", json.dumps(ui, default=str, separators=(",", ":"))

    if et == "drawing_updated":
        return "drawing", json.dumps({"payload": pl, "timeframe": tf_env}, default=str)

    if et == "news_scored":
        return "news", json.dumps({"payload": pl}, default=str)

    if et in ("trade_opened", "trade_updated", "trade_closed"):
        return "paper", json.dumps({"event_type": et, "payload": pl}, default=str)

    if et == "market_feed_health":
        out = {
            "event_type": et,
            "symbol": str(env.get("symbol", "") or pl.get("symbol") or ""),
            "exchange_ts_ms": pl.get("exchange_ts_ms"),
            "processed_ts_ms": pl.get("processed_ts_ms"),
            "pipeline_lag_ms": pl.get("pipeline_lag_ms"),
            "age_ticker_ms": pl.get("age_ticker_ms"),
            "vpin_toxicity_0_1": pl.get("vpin_toxicity_0_1"),
            "ok": pl.get("ok"),
            "payload": pl,
        }
        return "feed_health", json.dumps(out, default=str, separators=(",", ":"))

    return None


@router.get("/state", response_model=None)
def live_state(
    _auth: Annotated[GatewayAuthContext, Depends(require_sensitive_auth)],
    symbol: str | None = Query(default=None),
    market_family: str | None = Query(
        default=None,
        description="spot | margin | futures — Default aus DASHBOARD_DEFAULT_MARKET_FAMILY",
    ),
    product_type: str | None = Query(
        default=None,
        description="Futures: USDT-FUTURES etc.; Default aus BITGET_FUTURES_DEFAULT_PRODUCT_TYPE",
    ),
    margin_account_mode: str | None = Query(
        default=None,
        description="margin: isolated | crossed (Default isolated)",
    ),
    timeframe: str = Query("1m"),
    limit: Annotated[int | None, Query()] = None,
) -> dict[str, Any]:
    g = get_gateway_settings()
    max_c = g.live_state_max_candles
    def_c = min(g.live_state_default_candles, max_c)
    lim = def_c if limit is None else limit
    if lim < 1:
        raise HTTPException(status_code=400, detail="limit min 1")
    if lim > max_c:
        raise HTTPException(status_code=400, detail=f"limit max {max_c}")
    watchlist = g.dashboard_watchlist_symbols_list()
    resolved_symbol = (
        str(symbol or g.dashboard_default_symbol or g.next_public_default_symbol or (watchlist[0] if watchlist else "")).strip().upper()
    )
    if not resolved_symbol:
        raise HTTPException(status_code=400, detail="symbol erforderlich oder ueber Watchlist/Default konfigurieren")
    try:
        resolved_symbol = validate_live_symbol(resolved_symbol)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    res_mf = str(
        market_family
        or g.dashboard_default_market_family
        or g.next_public_default_market_family
        or "futures"
    ).strip().lower()
    res_pt: str | None = None
    if res_mf == "futures":
        res_pt = (product_type or g.default_futures_product_type() or "").strip().upper() or None
    res_margin_mode: str | None = None
    if res_mf == "margin":
        res_margin_mode = (margin_account_mode or "isolated").strip().lower()
    stale_ms = int(g.data_stale_warn_ms)
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            try:
                assert_symbol_in_instrument_catalog(
                    conn,
                    symbol=resolved_symbol,
                    market_family=res_mf,
                    product_type=res_pt,
                    margin_account_mode=res_margin_mode,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        payload = build_live_state(
            dsn,
            symbol=resolved_symbol,
            timeframe=timeframe,
            limit=lim,
            stale_warn_ms=stale_ms,
            news_fixture_mode=bool(g.news_fixture_mode),
            bitget_demo_enabled=bool(g.bitget_demo_enabled),
        )
    except HTTPException:
        raise
    except DatabaseHealthError as exc:
        logger.warning("live_state database_url: %s", exc)
        payload = build_live_state(
            "",
            symbol=resolved_symbol,
            timeframe=timeframe,
            limit=lim,
            stale_warn_ms=stale_ms,
            news_fixture_mode=bool(g.news_fixture_mode),
            bitget_demo_enabled=bool(g.bitget_demo_enabled),
        )
        return merge_read_envelope(
            payload,
            status="degraded",
            message="Datenbank-URL fehlt; Live-State nur mit Platzhaltern.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except Exception as exc:
        logger.warning("live_state failed: %s", exc)
        payload = build_live_state(
            "",
            symbol=resolved_symbol,
            timeframe=timeframe,
            limit=lim,
            stale_warn_ms=stale_ms,
            news_fixture_mode=bool(g.news_fixture_mode),
            bitget_demo_enabled=bool(g.bitget_demo_enabled),
        )
        return merge_read_envelope(
            payload,
            status="degraded",
            message="Live-State voruebergehend eingeschraenkt (DB/Redis).",
            empty_state=True,
            degradation_reason="live_state_partial",
            next_step="Postgres/Redis und Logs pruefen.",
        )

    candles = payload.get("candles") or []
    sig = payload.get("latest_signal")
    empty = len(candles) == 0 and sig is None
    db_h = (payload.get("health") or {}).get("db")
    degraded_db = db_h == "error"
    if degraded_db:
        st = "degraded"
    elif empty:
        st = "empty"
    else:
        st = "ok"
    return merge_read_envelope(
        payload,
        status=st,
        message="Keine Kerzen und kein letztes Signal fuer dieses Symbol/Timeframe." if empty else None,
        empty_state=empty,
        degradation_reason="no_candles_and_signal" if empty else ("database_unhealthy" if degraded_db else None),
        next_step=(
            "Market-Stream und Signal-Pipeline pruefen; Feld `data_lineage` nennt je Teilstrecke Ursache und naechsten Schritt."
            if empty or degraded_db
            else None
        ),
    )


@router.get("/stream")
async def live_stream(
    _auth: Annotated[GatewayAuthContext, Depends(require_live_stream_access)],
    symbol: str | None = Query(default=None),
    timeframe: str = Query("1m"),
) -> Any:
    g = get_gateway_settings()
    if not g.live_sse_enabled:
        raise HTTPException(status_code=503, detail="SSE disabled (LIVE_SSE_ENABLED=false)")

    try:
        from sse_starlette.sse import EventSourceResponse
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="sse-starlette fehlt") from exc

    redis_url = g.redis_url.strip()
    if not redis_url:
        raise HTTPException(status_code=503, detail="REDIS_URL fehlt")

    watchlist = g.dashboard_watchlist_symbols_list()
    sym = str(
        symbol or g.dashboard_default_symbol or g.next_public_default_symbol or (watchlist[0] if watchlist else "")
    ).strip().upper()
    if not sym:
        raise HTTPException(status_code=400, detail="symbol erforderlich oder ueber Watchlist/Default konfigurieren")
    nft = normalize_tf_for_db(timeframe)
    ping_sec = g.live_sse_ping_sec
    max_eps = 10

    async def gen() -> AsyncIterator[dict[str, Any]]:
        from shared_py.redis_client import get_or_create_async_pooled_client

        ts_deque: deque[float] = deque()
        r = get_or_create_async_pooled_client(
            redis_url,
            role="gateway_live_sse",
            decode_responses=True,
            max_connections=32,
        )
        streams = {s: "$" for s in STREAMS}
        last_ping = time.monotonic()
        yield {"event": "ping", "data": json.dumps({"ts_ms": int(time.time() * 1000)})}
        while True:
            now_m = time.monotonic()
            if now_m - last_ping >= ping_sec:
                yield {
                    "event": "ping",
                    "data": json.dumps({"ts_ms": int(time.time() * 1000)}),
                }
                last_ping = now_m
            try:
                resp = await r.xread(streams=streams, count=20, block=1000)
            except Exception as exc:
                logger.warning("xread: %s", exc)
                await asyncio.sleep(1)
                continue
            if not resp:
                await asyncio.sleep(0)
                continue
            for stream_name, messages in resp:
                for msg_id, fields in messages:
                    streams[stream_name] = msg_id
                    raw = fields.get("data", "{}")
                    try:
                        env = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    mapped = _map_envelope_to_sse(
                        env, symbol=sym, timeframe=nft
                    )
                    if mapped is None:
                        continue
                    ev_name, data = mapped
                    if not _coalesce_allow(ts_deque, max_eps):
                        continue
                    yield {"event": ev_name, "data": data}

    return EventSourceResponse(gen())
