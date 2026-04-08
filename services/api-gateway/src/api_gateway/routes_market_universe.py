from __future__ import annotations

import logging
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends
from psycopg.rows import dict_row

from api_gateway.auth import GatewayAuthContext, require_operator_aggregate_auth
from api_gateway.config import get_gateway_settings
from api_gateway.db import DatabaseHealthError, get_database_url
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
    return {
        "schema_version": MARKET_UNIVERSE_SCHEMA_VERSION,
        "configuration": configuration,
        "snapshot": None,
        "summary": dict(_EMPTY_UNIVERSE_SUMMARY),
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
