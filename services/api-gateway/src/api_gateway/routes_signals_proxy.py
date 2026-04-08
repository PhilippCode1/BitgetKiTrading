from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, HTTPException, Query
from psycopg import errors as pg_errors
from psycopg.rows import dict_row

from api_gateway.config import get_gateway_settings
from api_gateway.db import DatabaseHealthError, get_database_url
from api_gateway.db_dashboard_queries import (
    fetch_signal_by_id,
    fetch_signal_explain,
    fetch_signal_facets,
    fetch_signals_recent,
)
from api_gateway.gateway_read_envelope import NEXT_STEP_DB, merge_read_envelope
from api_gateway.signal_contract import SIGNAL_API_CONTRACT_VERSION

logger = logging.getLogger("api_gateway.signals_proxy")

router = APIRouter(prefix="/v1/signals", tags=["signals"])

_SIGNAL_FACET_ARRAY_KEYS: tuple[str, ...] = (
    "market_families",
    "playbook_families",
    "meta_trade_lanes",
    "regime_states",
    "specialist_routers",
    "exit_families",
    "symbols",
    "timeframes",
    "directions",
    "decision_states",
    "trade_actions",
    "strategy_names",
    "playbook_ids",
    "signal_classes",
)


def _page_limit() -> int:
    try:
        return max(1, min(500, int(get_gateway_settings().dashboard_page_size)))
    except ValueError:
        return 50


def _empty_facets(lookback_rows: int) -> dict[str, Any]:
    return {
        "lookback_rows": lookback_rows,
        "market_families": [],
        "playbook_families": [],
        "meta_trade_lanes": [],
        "regime_states": [],
        "specialist_routers": [],
        "exit_families": [],
        "symbols": [],
        "timeframes": [],
        "directions": [],
        "decision_states": [],
        "trade_actions": [],
        "strategy_names": [],
        "playbook_ids": [],
        "signal_classes": [],
    }


def _blank_q(v: str | None) -> bool:
    return v is None or not str(v).strip()


def _recent_has_active_filters(
    *,
    symbol: str | None,
    timeframe: str | None,
    direction: str | None,
    min_strength: float | None,
    market_family: str | None,
    playbook_id: str | None,
    playbook_family: str | None,
    trade_action: str | None,
    meta_trade_lane: str | None,
    regime_state: str | None,
    specialist_router_id: str | None,
    exit_family: str | None,
    decision_state: str | None,
    strategy_name: str | None,
    signal_class: str | None,
    signal_registry_key: str | None,
) -> bool:
    if min_strength is not None:
        return True
    strs = (
        symbol,
        timeframe,
        direction,
        market_family,
        playbook_id,
        playbook_family,
        trade_action,
        meta_trade_lane,
        regime_state,
        specialist_router_id,
        exit_family,
        decision_state,
        strategy_name,
        signal_class,
        signal_registry_key,
    )
    return any(not _blank_q(s) for s in strs)


@router.get("/facets", response_model=None)
def signals_facets(
    lookback_rows: Annotated[int | None, Query()] = None,
) -> dict[str, Any]:
    lb = lookback_rows if lookback_rows is not None else 3000
    lb = max(100, min(20_000, lb))
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            data = fetch_signal_facets(conn, lookback_rows=lb)
        empty = all(len(data.get(k, []) or []) == 0 for k in _SIGNAL_FACET_ARRAY_KEYS)
        return merge_read_envelope(
            data,
            status="ok",
            message="Keine Signal-Facetten im Lookback (keine Daten)." if empty else None,
            empty_state=empty,
            degradation_reason="no_signal_facets" if empty else None,
            next_step="Signal-Engine und app.signals_v1 pruefen." if empty else None,
        )
    except DatabaseHealthError as exc:
        logger.warning("signals facets: %s", exc)
        return merge_read_envelope(
            _empty_facets(lb),
            status="degraded",
            message="Datenbank ist nicht konfiguriert.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except (pg_errors.Error, OSError) as exc:
        logger.warning("signals facets: %s", exc)
        return merge_read_envelope(
            _empty_facets(lb),
            status="degraded",
            message="Facetten konnten nicht geladen werden.",
            empty_state=True,
            degradation_reason="database_error",
            next_step=NEXT_STEP_DB,
        )


@router.get("/recent", response_model=None)
def signals_recent(
    symbol: str | None = Query(None),
    timeframe: str | None = Query(None),
    direction: str | None = Query(None),
    min_strength: Annotated[float | None, Query()] = None,
    market_family: str | None = Query(None),
    playbook_id: str | None = Query(None),
    playbook_family: str | None = Query(None),
    trade_action: str | None = Query(None),
    meta_trade_lane: str | None = Query(None),
    regime_state: str | None = Query(None),
    specialist_router_id: str | None = Query(None),
    exit_family: str | None = Query(None),
    decision_state: str | None = Query(
        None,
        description="Filter: Spalte decision_state (Engine-Status), exakt wie in app.signals_v1.",
    ),
    strategy_name: str | None = Query(
        None,
        description="Filter: Spalte strategy_name, exakter Match.",
    ),
    signal_class: str | None = Query(
        None,
        description="Filter: Spalte signal_class, exakter Match.",
    ),
    signal_registry_key: str | None = Query(
        None,
        description=(
            "Filter: Zeilen, bei denen playbook_id ODER strategy_name (trim) diesem Wert entspricht — "
            "abgestimmt mit Registry learn.strategies.name und Signalpfad-Zaehlung."
        ),
    ),
    limit: Annotated[int | None, Query()] = None,
) -> dict[str, Any]:
    lim = limit if limit is not None else _page_limit()
    lim = max(1, min(500, lim))
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            items = fetch_signals_recent(
                conn,
                symbol=symbol,
                timeframe=timeframe,
                direction=direction,
                min_strength=min_strength,
                market_family=market_family,
                playbook_id=playbook_id,
                playbook_family=playbook_family,
                trade_action=trade_action,
                meta_trade_lane=meta_trade_lane,
                regime_state=regime_state,
                specialist_router_id=specialist_router_id,
                exit_family=exit_family,
                decision_state=decision_state,
                strategy_name=strategy_name,
                signal_class=signal_class,
                signal_registry_key=signal_registry_key,
                limit=lim,
            )
        es = len(items) == 0
        filtered = _recent_has_active_filters(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            min_strength=min_strength,
            market_family=market_family,
            playbook_id=playbook_id,
            playbook_family=playbook_family,
            trade_action=trade_action,
            meta_trade_lane=meta_trade_lane,
            regime_state=regime_state,
            specialist_router_id=specialist_router_id,
            exit_family=exit_family,
            decision_state=decision_state,
            strategy_name=strategy_name,
            signal_class=signal_class,
            signal_registry_key=signal_registry_key,
        )
        if es:
            msg = (
                "Keine Signale fuer die aktiven Filter — URL-Parameter lockern oder zuruecksetzen."
                if filtered
                else "Keine Signale in den zuletzt betrachteten Zeilen (ohne aktive URL-Filter)."
            )
            nxt = (
                "Mehrere Filter gleichzeitig verschärfen das Ergebnis. Einzelne Filter per Link "
                "deaktivieren oder alle Filter ueber die Signalseite ohne Query-Parameter oeffnen."
                if filtered
                else "Signal-Engine und app.signals_v1 pruefen."
            )
            deg = "no_signals_filtered" if filtered else "no_signals"
        else:
            msg = None
            nxt = None
            deg = None
        return merge_read_envelope(
            {"items": items, "limit": lim, "filters_active": filtered},
            status="ok",
            message=msg,
            empty_state=es,
            degradation_reason=deg,
            next_step=nxt,
        )
    except DatabaseHealthError as exc:
        logger.warning("signals recent: %s", exc)
        return merge_read_envelope(
            {"items": [], "limit": lim, "filters_active": False},
            status="degraded",
            message="Datenbank ist nicht konfiguriert.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except (pg_errors.Error, OSError) as exc:
        logger.warning("signals recent: %s", exc)
        return merge_read_envelope(
            {"items": [], "limit": lim, "filters_active": False},
            status="degraded",
            message="Signale konnten nicht geladen werden.",
            empty_state=True,
            degradation_reason="database_error",
            next_step=NEXT_STEP_DB,
        )


@router.get("/{signal_id}/explain", response_model=None)
def signal_explain(signal_id: UUID) -> dict[str, Any]:
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            row = fetch_signal_explain(conn, signal_id)
    except DatabaseHealthError as exc:
        logger.warning("signal explain: %s", exc)
        return merge_read_envelope(
            {
                "signal_id": str(signal_id),
                "signal_contract_version": SIGNAL_API_CONTRACT_VERSION,
                "explain_short": None,
                "explain_long_md": None,
                "risk_warnings_json": [],
                "stop_explain_json": {},
                "targets_explain_json": {},
                "reasons_json": [],
                "explanation_layers": None,
            },
            status="degraded",
            message="Datenbank ist nicht konfiguriert.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except (pg_errors.Error, OSError) as exc:
        logger.warning("signal explain: %s", exc)
        return merge_read_envelope(
            {
                "signal_id": str(signal_id),
                "signal_contract_version": SIGNAL_API_CONTRACT_VERSION,
                "explain_short": None,
                "explain_long_md": None,
                "risk_warnings_json": [],
                "stop_explain_json": {},
                "targets_explain_json": {},
                "reasons_json": [],
                "explanation_layers": None,
            },
            status="degraded",
            message="Erklaerung nicht ladbar.",
            empty_state=True,
            degradation_reason="database_error",
            next_step=NEXT_STEP_DB,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="signal not found")
    return merge_read_envelope(
        row,
        status="ok",
        message=None,
        empty_state=False,
        degradation_reason=None,
        next_step=None,
    )


@router.get("/{signal_id}", response_model=None)
def signal_detail(signal_id: UUID) -> dict[str, Any]:
    try:
        dsn = get_database_url()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            row = fetch_signal_by_id(conn, signal_id)
    except DatabaseHealthError as exc:
        logger.warning("signal detail: %s", exc)
        return merge_read_envelope(
            {"signal_id": str(signal_id)},
            status="degraded",
            message="Datenbank ist nicht konfiguriert.",
            empty_state=True,
            degradation_reason="database_url_missing",
            next_step=NEXT_STEP_DB,
        )
    except (pg_errors.Error, OSError) as exc:
        logger.warning("signal detail: %s", exc)
        return merge_read_envelope(
            {"signal_id": str(signal_id)},
            status="degraded",
            message="Signal nicht ladbar.",
            empty_state=True,
            degradation_reason="database_error",
            next_step=NEXT_STEP_DB,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="signal not found")
    return merge_read_envelope(
        row,
        status="ok",
        message=None,
        empty_state=False,
        degradation_reason=None,
        next_step=None,
    )
