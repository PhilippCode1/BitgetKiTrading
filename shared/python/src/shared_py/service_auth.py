"""
Interne Dienst-zu-Dienst-Authentifizierung.

`INTERNAL_API_KEY` / optional `SERVICE_INTERNAL_API_KEY` (Settings-Feld `service_internal_api_key`)
wird im Header `X-Internal-Service-Key` (INTERNAL_SERVICE_HEADER) gesendet — z. B. Gateway→Orchestrator,
Gateway→live-broker. Nicht verwechseln mit `GATEWAY_INTERNAL_API_KEY` / `X-Gateway-Internal-Key`
(Gateway-Admin/interne Dashboard-API).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Header, HTTPException

INTERNAL_SERVICE_HEADER = "X-Internal-Service-Key"


@dataclass(frozen=True)
class InternalServiceAuthContext:
    actor: str
    auth_method: str
    direct_access_allowed: bool


def _normalized_internal_key(settings: Any) -> str:
    return str(getattr(settings, "service_internal_api_key", "") or "").strip()


def internal_service_auth_required(settings: Any) -> bool:
    configured = bool(_normalized_internal_key(settings))
    return configured or bool(getattr(settings, "production", False))


def assert_internal_service_auth(
    settings: Any,
    x_internal_service_key: str | None,
) -> InternalServiceAuthContext:
    expected = _normalized_internal_key(settings)
    presented = str(x_internal_service_key or "").strip()
    if not expected:
        if bool(getattr(settings, "production", False)):
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "INTERNAL_AUTH_MISCONFIGURED",
                    "message": "Interner Service-Key fehlt im Produktionsprofil.",
                },
            )
        return InternalServiceAuthContext(
            actor="anonymous_local",
            auth_method="none",
            direct_access_allowed=True,
        )
    if presented != expected:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "INTERNAL_AUTH_REQUIRED",
                "message": (
                    "Direkter Servicezugriff erfordert den internen Service-Key "
                    f"im Header `{INTERNAL_SERVICE_HEADER}` (ENV INTERNAL_API_KEY)."
                ),
                "hint": (
                    "Nicht verwechseln mit X-Gateway-Internal-Key / GATEWAY_INTERNAL_API_KEY "
                    "(Gateway-Operator-Pfad). Der Service-Key ist fuer Gateway→Worker (z. B. llm-orchestrator)."
                ),
            },
        )
    return InternalServiceAuthContext(
        actor="internal_service",
        auth_method="internal_api_key",
        direct_access_allowed=True,
    )


def build_internal_service_dependency(settings: Any):
    def _require(
        x_internal_service_key: str | None = Header(
            default=None,
            alias=INTERNAL_SERVICE_HEADER,
        ),
    ) -> InternalServiceAuthContext:
        return assert_internal_service_auth(settings, x_internal_service_key)

    return _require
