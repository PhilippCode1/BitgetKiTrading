"""Gateway: operator_release gegen live-broker (Rollen + manuelles Aktions-Token)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from api_gateway.auth import GatewayAuthContext
from api_gateway.config import get_gateway_settings
from api_gateway.live_broker_forward import LiveBrokerForwardHttpError, post_live_broker_json
from api_gateway.mutation_deps import LiveBrokerOperatorReleaseGuard

router = APIRouter(prefix="/v1/live-broker", tags=["live-broker-operator"])

_operator_release_guard = LiveBrokerOperatorReleaseGuard()


@router.post("/executions/{execution_id}/operator-release")
def live_broker_operator_release(
    execution_id: UUID,
    _ctx: Annotated[tuple[GatewayAuthContext, dict[str, Any]], Depends(_operator_release_guard)],
) -> Any:
    auth, body = _ctx
    eff: dict[str, Any] = dict(body) if isinstance(body, dict) else {}
    audit: dict[str, Any] = {}
    raw_audit = eff.get("audit")
    if isinstance(raw_audit, dict):
        audit.update(raw_audit)
    audit["gateway_actor"] = auth.actor
    audit["gateway_auth_method"] = auth.auth_method
    eff["audit"] = audit
    eff.setdefault("source", "internal-api")
    g = get_gateway_settings()
    subpath = f"/live-broker/executions/{execution_id}/operator-release"
    try:
        return post_live_broker_json(g, subpath, eff)
    except LiveBrokerForwardHttpError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.payload) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
