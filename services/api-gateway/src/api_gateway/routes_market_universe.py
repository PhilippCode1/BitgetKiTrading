from __future__ import annotations

import logging
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg.rows import dict_row

from api_gateway.auth import GatewayAuthContext, require_operator_aggregate_auth
from api_gateway.config import get_gateway_settings
from api_gateway.db import DatabaseHealthError, get_database_url
from api_gateway.db_live_queries import (
    assert_symbol_in_instrument_catalog,
    fetch_candles,
    normalize_tf_for_db,
    validate_live_symbol,
)
from api_gateway.db_market_universe_queries import fetch_market_universe_status
from api_gateway.gateway_read_envelope import NEXT_STEP_DB, merge_read_envelope
from shared_py.bitget.instruments import MARKET_UNIVERSE_SCHEMA_VERSION

logger = logging.getLogger("api_gateway.market_universe")

_EMPTY_UNIVERSE_SUMMARY: dict[str, int] = {
    "category_count": 0,
    "instrument_count": 0,
    "inventory_visible_category_count": 0,
    "analytics_eligible_category_count": 0,
    "paper_shadow_eligible_category_count": 0,
    "live_execution_enabled_category_count": 0,
    "execution_disabled_category_count": 0,
    "inventory_visible_instrument_count": 0,
    "analytics_eligible_instrument_count": 0,
    "paper_shadow_eligible_instrument_count": 0,
    "live_execution_enabled_instrument_count": 0,
    "execution_disabled_instrument_count": 0,
}


def _degraded_universe_payload(configuration: dict[str, Any]) -> dict[str, Any]:
    empty_families: dict[str, Any] = {
        fam: {"product_family": fam, "instrument_count": 0, "instruments": []}
        for fam in ("spot", "margin", "futures")
    }
    return {
        "schema_version": MARKET_UNIVERSE_SCHEMA_VERSION,
        "configuration": configuration,
        "snapshot": None,
        "summary": dict(_EMPTY_UNIVERSE_SUMMARY),
        "by_product_family": empty_families,
        "categories": [],
        "instruments": [],
    }

router = APIRouter(prefix="/v1/market-universe", tags=["market-universe"])


@router.get("/status", response_model=None)
def market_universe_status(
    _auth: Annotated[GatewayAuthContext, Depends(require_operator_aggregate_auth)],
) -> dict[str, Any]:
    configuration = get_gateway_settings().market_universe_snapshot()
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            payload = fetch_market_universe_status(conn, configuration_snapshot=configuration)
        return merge_read_envelope(
            payload,
            status="ok",
            message=None,
            empty_state=False,
            degradation_reason=None,
            next_step=None,
        )
    except DatabaseHealthError as exc:
        logger.warning("market_universe status: %s", exc)
        return merge_read_envelope(
            _degraded_universe_payload(configuration),
            status="degraded",
            message="Datenbank ist nicht konfiguriert.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except Exception as exc:
        logger.warning("market_universe status: %s", exc)
        return merge_read_envelope(
            _degraded_universe_payload(configuration),
            status="degraded",
            message="Market-Universe-Status nicht ladbar.",
            empty_state=True,
            degradation_reason="database_error",
            next_step=NEXT_STEP_DB,
        )


@router.get("/candles", response_model=None)
def market_universe_candles(
    _auth: Annotated[GatewayAuthContext, Depends(require_operator_aggregate_auth)],
    symbol: str = Query(
        ...,
        min_length=1,
        description="Kanonisches Bitget-Symbol (z. B. ETHUSDT); kein Server-Default — aus URL/Client setzen.",
    ),
    timeframe: str = Query("5m"),
    limit: Annotated[int, Query()] = 500,
    market_family: str | None = Query(default=None),
    product_type: str | None = Query(default=None),
    margin_account_mode: str | None = Query(default=None),
) -> dict[str, Any]:
    """
    Kerzen-Historie aus `tsdb.candles` (Hydration neben SSE) — `symbol` ist verpflichtend
    (kein BTCUSDT-Implizit-Default in dieser Route).
    """
    g = get_gateway_settings()
    max_c = g.live_state_max_candles
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit min 1")
    if limit > max_c:
        raise HTTPException(status_code=400, detail=f"limit max {max_c}")
    try:
        resolved_symbol = validate_live_symbol(symbol)
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
    tf = timeframe.strip() or "5m"
    tf_resolved = normalize_tf_for_db(tf)
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
            candles = fetch_candles(
                conn, symbol=resolved_symbol, timeframe=tf, limit=limit
            )
    except HTTPException:
        raise
    except DatabaseHealthError as exc:
        logger.warning("market_universe /candles database: %s", exc)
        return merge_read_envelope(
            {
                "candles": [],
                "symbol": resolved_symbol,
                "timeframe": tf_resolved,
            },
            status="degraded",
            message="Datenbank-URL fehlt; keine Kerzen.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("market_universe /candles: %s", exc)
        return merge_read_envelope(
            {
                "candles": [],
                "symbol": resolved_symbol,
                "timeframe": tf_resolved,
            },
            status="degraded",
            message="Kerzen-Historie nicht ladbar.",
            empty_state=True,
            degradation_reason="database_error",
            next_step=NEXT_STEP_DB,
        )
    empty = len(candles) == 0
    return merge_read_envelope(
        {
            "candles": candles,
            "symbol": resolved_symbol,
            "timeframe": tf_resolved,
        },
        status="empty" if empty else "ok",
        message="Keine Zeilen in tsdb.candles fuer dieses Symbol/TF."
        if empty
        else None,
        empty_state=empty,
        degradation_reason="no_candles" if empty else None,
        next_step="Market-Stream/Feature-Engine; tsdb.candles pruefen."
        if empty
        else None,
    )
