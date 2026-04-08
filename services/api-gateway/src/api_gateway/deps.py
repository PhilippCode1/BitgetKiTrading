"""Zusammengesetzte FastAPI-Dependencies."""

from __future__ import annotations

from fastapi import Depends, Request

from api_gateway.audit import record_gateway_audit_line
from api_gateway.auth import GatewayAuthContext, require_sensitive_auth


def audited_sensitive(action: str):
    async def _dep(
        request: Request,
        auth: GatewayAuthContext = Depends(require_sensitive_auth),
    ) -> GatewayAuthContext:
        record_gateway_audit_line(request, auth, action)
        return auth

    return _dep
