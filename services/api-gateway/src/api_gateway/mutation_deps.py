"""Dependencies fuer live-broker Mutationen: Rollen + manuelle Aktions-Tokens + Audit."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import Body, Header, HTTPException, Request

from api_gateway.audit import record_gateway_audit_line, record_gateway_auth_failure
from api_gateway.deps import verify_live_trading_capability
from api_gateway.auth import (
    GatewayAuthContext,
    _HEADER_INTERNAL,
    _HEADER_LEGACY_ADMIN,
    _internal_key_default_roles,
    resolve_gateway_auth,
)
from api_gateway.config import get_gateway_settings
from api_gateway.manual_action import (
    fingerprint_payload_for_operator_release,
    verify_manual_action_token,
)
from api_gateway.rate_limit import get_rate_limit_redis

logger = logging.getLogger("api_gateway.mutation_deps")


class LiveBrokerSafetyMutationGuard:
    def __init__(self, route_key: str, *, audit_action: str) -> None:
        self.route_key = route_key
        self.audit_action = audit_action

    async def __call__(
        self,
        request: Request,
        body: dict[str, Any] = Body(default_factory=dict),
        authorization: str | None = Header(None),
        x_gateway_internal_key: str | None = Header(None, alias=_HEADER_INTERNAL),
        x_admin_token: str | None = Header(None, alias=_HEADER_LEGACY_ADMIN),
        x_manual_action_token: str | None = Header(None, alias="X-Manual-Action-Token"),
    ) -> tuple[GatewayAuthContext, dict[str, Any]]:
        settings = get_gateway_settings()
        auth = _resolve_live_broker_mutation_context_impl(
            request=request,
            authorization=authorization,
            x_gateway_internal_key=x_gateway_internal_key,
            x_admin_token=x_admin_token,
            route_key=self.route_key,
        )
        extra: dict[str, Any] = {"route_key": self.route_key}
        if settings.manual_action_required():
            tok = (x_manual_action_token or "").strip()
            if not tok:
                record_gateway_auth_failure(
                    request,
                    "auth_failure_manual_action_token",
                    actor=auth.actor,
                    auth_method=auth.auth_method,
                    extra={"route_key": self.route_key},
                )
                raise HTTPException(
                    status_code=401,
                    detail={
                        "code": "MANUAL_ACTION_TOKEN_REQUIRED",
                        "message": "X-Manual-Action-Token fehlt (POST /v1/auth/manual-action/mint).",
                    },
                )
            claims = verify_manual_action_token(
                token=tok,
                settings=settings,
                route_key=self.route_key,
                payload=body,
                redis_client=get_rate_limit_redis(),
            )
            extra["manual_action_jti"] = claims.get("jti")
        verify_live_trading_capability(auth)
        record_gateway_audit_line(request, auth, self.audit_action, extra=extra)
        return auth, body


class LiveBrokerOperatorReleaseGuard:
    async def __call__(
        self,
        request: Request,
        execution_id: UUID,
        body: dict[str, Any] = Body(default_factory=dict),
        authorization: str | None = Header(None),
        x_gateway_internal_key: str | None = Header(None, alias=_HEADER_INTERNAL),
        x_admin_token: str | None = Header(None, alias=_HEADER_LEGACY_ADMIN),
        x_manual_action_token: str | None = Header(None, alias="X-Manual-Action-Token"),
    ) -> tuple[GatewayAuthContext, dict[str, Any]]:
        from api_gateway.manual_action import ROUTE_KEY_OPERATOR_RELEASE

        settings = get_gateway_settings()
        route_key = ROUTE_KEY_OPERATOR_RELEASE
        auth = _resolve_live_broker_mutation_context_impl(
            request=request,
            authorization=authorization,
            x_gateway_internal_key=x_gateway_internal_key,
            x_admin_token=x_admin_token,
            route_key=route_key,
        )
        fp_payload = fingerprint_payload_for_operator_release(str(execution_id), body)
        extra: dict[str, Any] = {
            "route_key": route_key,
            "execution_id": str(execution_id),
        }
        if settings.manual_action_required():
            tok = (x_manual_action_token or "").strip()
            if not tok:
                record_gateway_auth_failure(
                    request,
                    "auth_failure_manual_action_token",
                    actor=auth.actor,
                    auth_method=auth.auth_method,
                    extra={"route_key": route_key, "execution_id": str(execution_id)},
                )
                raise HTTPException(
                    status_code=401,
                    detail={
                        "code": "MANUAL_ACTION_TOKEN_REQUIRED",
                        "message": "X-Manual-Action-Token fehlt.",
                    },
                )
            claims = verify_manual_action_token(
                token=tok,
                settings=settings,
                route_key=route_key,
                payload=fp_payload,
                redis_client=get_rate_limit_redis(),
            )
            extra["manual_action_jti"] = claims.get("jti")
        verify_live_trading_capability(auth)
        record_gateway_audit_line(
            request,
            auth,
            "live_broker_operator_release_mutate",
            extra=extra,
        )
        return auth, body


def _resolve_live_broker_mutation_context_impl(
    *,
    request: Request,
    authorization: str | None,
    x_gateway_internal_key: str | None,
    x_admin_token: str | None,
    route_key: str,
) -> GatewayAuthContext:
    settings = get_gateway_settings()
    ctx = resolve_gateway_auth(
        request=request,
        authorization=authorization,
        x_gateway_internal_key=x_gateway_internal_key,
        x_admin_token=x_admin_token if settings.legacy_admin_token_allowed() else None,
    )
    if ctx is not None:
        if ctx.can_execute_live_broker_route(route_key):
            return ctx
        record_gateway_auth_failure(
            request,
            "auth_failure_live_broker_mutation_role",
            actor=ctx.actor,
            auth_method=ctx.auth_method,
            extra={"route_key": route_key},
        )
        raise HTTPException(
            status_code=403,
            detail={
                "code": "FORBIDDEN_MUTATION_ROLE",
                "message": "Rolle reicht fuer diese Mutation nicht (operator:mutate / emergency:mutate / admin:write).",
            },
        )
    if settings.allow_anonymous_safety_mutations_effective():
        logger.warning(
            "anonymous safety mutation allowed (dev): route_key=%s path=%s",
            route_key,
            request.url.path,
        )
        return GatewayAuthContext(
            actor="anonymous_unauthenticated_mutation",
            auth_method="dev_anonymous",
            roles=_internal_key_default_roles(),
            tenant_id=None,
            portal_roles=frozenset(),
        )
    record_gateway_auth_failure(
        request,
        "auth_failure_live_broker_mutation",
        extra={"route_key": route_key},
    )
    raise HTTPException(
        status_code=401,
        detail={"code": "AUTHENTICATION_REQUIRED", "message": "Authentifizierung fuer Mutation erforderlich."},
    )
