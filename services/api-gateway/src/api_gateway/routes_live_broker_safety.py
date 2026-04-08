"""Gateway-Proxys fuer live-broker Safety-/Notfall-Endpunkte (POST-Forward)."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from api_gateway.auth import GatewayAuthContext
from api_gateway.config import get_gateway_settings
from api_gateway.live_broker_forward import LiveBrokerForwardHttpError, post_live_broker_json
from api_gateway.manual_action import (
    ROUTE_KEY_SAFETY_CANCEL_ALL,
    ROUTE_KEY_SAFETY_EMERGENCY_FLATTEN,
    ROUTE_KEY_SAFETY_KILL_SWITCH_ARM,
    ROUTE_KEY_SAFETY_KILL_SWITCH_RELEASE,
    ROUTE_KEY_SAFETY_LATCH_RELEASE,
)
from api_gateway.mutation_deps import LiveBrokerSafetyMutationGuard

logger = logging.getLogger("api_gateway.live_broker_safety")

router = APIRouter(prefix="/v1/live-broker/safety", tags=["live-broker-safety"])

_guard_kill_arm = LiveBrokerSafetyMutationGuard(
    ROUTE_KEY_SAFETY_KILL_SWITCH_ARM,
    audit_action="live_broker_safety_kill_switch_arm",
)
_guard_kill_release = LiveBrokerSafetyMutationGuard(
    ROUTE_KEY_SAFETY_KILL_SWITCH_RELEASE,
    audit_action="live_broker_safety_kill_switch_release",
)
_guard_cancel_all = LiveBrokerSafetyMutationGuard(
    ROUTE_KEY_SAFETY_CANCEL_ALL,
    audit_action="live_broker_safety_orders_cancel_all",
)
_guard_emergency_flatten = LiveBrokerSafetyMutationGuard(
    ROUTE_KEY_SAFETY_EMERGENCY_FLATTEN,
    audit_action="live_broker_safety_emergency_flatten",
)
_guard_latch = LiveBrokerSafetyMutationGuard(
    ROUTE_KEY_SAFETY_LATCH_RELEASE,
    audit_action="live_broker_safety_safety_latch_release",
)


def _forward(subpath: str, body: dict[str, Any]) -> Any:
    g = get_gateway_settings()
    try:
        return post_live_broker_json(g, subpath, body)
    except LiveBrokerForwardHttpError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.payload) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/kill-switch/arm")
def safety_kill_switch_arm(
    _ctx: Annotated[tuple[GatewayAuthContext, dict[str, Any]], Depends(_guard_kill_arm)],
) -> Any:
    _, body = _ctx
    return _forward("/live-broker/kill-switch/arm", body)


@router.post("/kill-switch/release")
def safety_kill_switch_release(
    _ctx: Annotated[tuple[GatewayAuthContext, dict[str, Any]], Depends(_guard_kill_release)],
) -> Any:
    _, body = _ctx
    return _forward("/live-broker/kill-switch/release", body)


@router.post("/orders/cancel-all")
def safety_orders_cancel_all(
    _ctx: Annotated[tuple[GatewayAuthContext, dict[str, Any]], Depends(_guard_cancel_all)],
) -> Any:
    _, body = _ctx
    return _forward("/live-broker/safety/orders/cancel-all", body)


@router.post("/orders/emergency-flatten")
def safety_emergency_flatten(
    _ctx: Annotated[tuple[GatewayAuthContext, dict[str, Any]], Depends(_guard_emergency_flatten)],
) -> Any:
    _, body = _ctx
    return _forward("/live-broker/orders/emergency-flatten", body)


@router.post("/safety-latch/release")
def safety_latch_release(
    _ctx: Annotated[tuple[GatewayAuthContext, dict[str, Any]], Depends(_guard_latch)],
) -> Any:
    _, body = _ctx
    return _forward("/live-broker/safety/safety-latch/release", body)
