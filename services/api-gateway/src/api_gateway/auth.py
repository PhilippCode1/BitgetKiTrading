"""Gateway-Authentifizierung: JWT (HS256), X-Gateway-Internal-Key, optional Legacy-Admin-Token.

X-Gateway-Internal-Key nutzt GATEWAY_INTERNAL_API_KEY (auth_method=gateway_internal_key) — nur serverseitig (BFF/Operator),
niemals im Browser-Bundle.

INTERNAL_API_KEY (Header X-Internal-Service-Key) ist ausschliesslich Service-zu-Service (shared_py.service_auth),
z. B. Gateway → Worker; gehoert nicht in Next.js-Client-Code und ersetzt kein Kunden- oder Admin-JWT.

401-Details: strukturiertes JSON mit code/message/hint (z. B. GATEWAY_JWT_EXPIRED, GATEWAY_INTERNAL_KEY_MISMATCH).
Kunden-Portal-Bearer auf /v1/admin: 403 GATEWAY_FORBIDDEN_CUSTOMER_SESSION.
Ohne role=admin in JWT-Claim (Hauptrolle): 403 GATEWAY_FORBIDDEN_JWT_ROLE.
S2S-Header/Legacy-Admin: keine JWT-Claim-Pruefung.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, cast

import jwt
from fastapi import Header, HTTPException, Request
from shared_py.portal_access_contract import (
    PORTAL_ROLE_CUSTOMER,
    PORTAL_ROLE_SUPER_ADMIN,
    merge_portal_roles_from_payload,
)

from api_gateway.audit import record_gateway_auth_failure
from api_gateway.config import get_gateway_settings
from api_gateway.manual_action import EMERGENCY_ROUTE_KEYS, OPERATOR_ROUTE_KEYS
from api_gateway.sse_ticket import resolve_sse_signing_secret, verify_sse_ticket

_HEADER_INTERNAL = "X-Gateway-Internal-Key"
_HEADER_LEGACY_ADMIN = "X-Admin-Token"

# Kurztexte fuer strukturierte 401/403 (Operator/BFF); keine Secrets.
_HINT_BFF_JWT = (
    "Dashboard-BFF: DASHBOARD_GATEWAY_AUTHORIZATION = Bearer <JWT> (Next-Server-ENV). "
    "Das ist nicht INTERNAL_API_KEY und kein X-Internal-Service-Key."
)
_HINT_GATEWAY_INTERNAL = (
    f"Gateway-intern: Header {_HEADER_INTERNAL} mit GATEWAY_INTERNAL_API_KEY — "
    "eigenes Secret, nicht INTERNAL_API_KEY (letzteres: X-Internal-Service-Key zu Workern)."
)


def _internal_key_default_roles() -> frozenset[str]:
    return frozenset(
        {
            "gateway:read",
            "admin:read",
            "admin:write",
            "operator:mutate",
            "emergency:mutate",
        }
    )


def _empty_frozenset() -> frozenset[str]:
    return frozenset()


def _parse_internal_key_roles_csv(raw: str) -> frozenset[str]:
    if not (raw or "").strip():
        return _internal_key_default_roles()
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return frozenset(parts)


@dataclass(frozen=True)
class GatewayAuthContext:
    actor: str
    auth_method: str
    roles: frozenset[str]
    # Mandanten-ID (JWT, Portal); Grundlage fuer u. a. verify_live_trading_capability
    tenant_id: str | None = None
    portal_roles: frozenset[str] = field(default_factory=_empty_frozenset)
    # Claim \"role\" (Hauptrolle) aus HS256; None = S2S, Legacy, oder alter Flow
    jwt_role: str | None = None

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def can_sensitive_read(self) -> bool:
        return self.has_role("gateway:read") or self.has_role("admin:read")

    def can_admin_read(self) -> bool:
        return self.has_role("admin:read") or self.has_role("admin:write")

    def can_admin_write(self) -> bool:
        return self.has_role("admin:write")

    def can_billing_read(self) -> bool:
        return (
            self.has_role("billing:read")
            or self.has_role("admin:read")
            or self.has_role("admin:write")
        )

    def can_billing_admin(self) -> bool:
        return self.has_role("billing:admin") or self.has_role("admin:write")

    def effective_tenant(self, *, default_tenant_id: str) -> str:
        tid = (self.tenant_id or "").strip()
        return tid if tid else default_tenant_id

    def is_pure_customer_billing_scope(self) -> bool:
        """
        True wenn nur Kunden-Commerce-Rolle ohne Admin-Gateway-Rollen.

        Wird fuer Mandantenisolation genutzt (tenant_id-Pflicht bei COMMERCIAL_ENABLED).
        """
        if self.has_role("admin:read") or self.has_role("admin:write"):
            return False
        return self.has_role("billing:read")

    def super_admin_portal_effective(self) -> bool:
        """UI-Flag: Portal markiert Super-Admin und Gateway hat Subject validiert."""
        return PORTAL_ROLE_SUPER_ADMIN in self.portal_roles

    def access_matrix(self) -> dict[str, bool]:
        """Sichere Kennzeichnung fuer Kunden-UI / BFF (keine Rollennamen als Geheimnis)."""
        return {
            "billing_read": self.can_billing_read(),
            "sensitive_read": self.can_sensitive_read(),
            "admin_write": self.can_admin_write(),
            "billing_admin": self.can_billing_admin(),
            "portal_customer": bool(self.portal_roles & {"customer"})
            or self.can_billing_read(),
            "super_admin_portal": self.super_admin_portal_effective(),
        }

    def can_execute_live_broker_route(self, route_key: str) -> bool:
        """Live-Broker-Mutation: admin:write, oder operator/emergency je Route."""
        if self.has_role("admin:write"):
            return True
        if route_key in OPERATOR_ROUTE_KEYS:
            return self.has_role("operator:mutate")
        if route_key in EMERGENCY_ROUTE_KEYS:
            return self.has_role("emergency:mutate")
        return False

    def is_customer_portal_jwt(self) -> bool:
        """
        Kunden-Portal-Sitzung (JWT): portal_roles enthaelt 'customer' ohne Super-Admin-Portal.
        S2S (X-Gateway-Internal-Key, Legacy-Admin) ist kein Kunden-Portal.
        """
        if self.auth_method != "jwt":
            return False
        if PORTAL_ROLE_SUPER_ADMIN in self.portal_roles:
            return False
        return PORTAL_ROLE_CUSTOMER in self.portal_roles


def _auth_diag(code: str, message: str, hint: str) -> dict[str, str]:
    return {"code": code, "message": message, "hint": hint}


def _role_hint_sensitive_read() -> str:
    return (
        "Fuer sensible Lese-Pfade: JWT-Claim gateway_roles muss gateway:read oder admin:read enthalten "
        "(Mint: scripts/mint_dashboard_gateway_jwt.py)."
    )


def _role_hint_admin_read() -> str:
    return "admin:read oder admin:write in gateway_roles erforderlich."


def _role_hint_admin_write() -> str:
    return "admin:write in gateway_roles erforderlich (oder gueltiger X-Gateway-Internal-Key mit Rolle)."


def _role_hint_billing_read() -> str:
    return "billing:read, admin:read oder admin:write erforderlich."


def _role_hint_billing_admin() -> str:
    return "billing:admin oder admin:write erforderlich."


def _insufficient_roles_detail(
    ctx: GatewayAuthContext,
    *,
    capability: str,
    message: str,
    hint: str,
) -> dict[str, str | bool]:
    return {
        "code": "GATEWAY_INSUFFICIENT_ROLES",
        "message": message,
        "hint": hint,
        "required_capability": capability,
        "auth_method": ctx.auth_method,
        "sensitive_read_ok": ctx.can_sensitive_read(),
        "admin_read_ok": ctx.can_admin_read(),
        "admin_write_ok": ctx.can_admin_write(),
    }


def _parse_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split(maxsplit=1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def _jwt_tenant_id(payload: dict[str, Any]) -> str | None:
    tid = payload.get("tenant_id")
    if tid is None:
        return None
    s = str(tid).strip()
    return s or None


def _jwt_main_role_from_payload(payload: dict[str, Any]) -> str | None:
    """Hauptrollen-Claim role (lowercase). Fehlt oder leer: None."""
    raw = payload.get("role")
    if raw is None:
        return None
    s = str(raw).strip().lower()
    return s or None


def _jwt_roles(payload: dict[str, Any]) -> frozenset[str]:
    raw = payload.get("gateway_roles")
    if isinstance(raw, list):
        return frozenset(str(x) for x in raw if x is not None)
    if isinstance(raw, str) and raw.strip():
        return frozenset(raw.split())
    # Fallback: scope-Claim (OAuth2-artig)
    scp = payload.get("scope")
    if isinstance(scp, str) and scp.strip():
        return frozenset(scp.split())
    return frozenset()


def _strip_unauthorized_super_admin_portal(
    ctx: GatewayAuthContext,
    settings: Any,
) -> GatewayAuthContext:
    """
    Nur GATEWAY_SUPER_ADMIN_SUBJECT darf super_admin in portal_roles behalten.
    Sonst UI-Leak ohne technische admin:write-Aenderung.
    """
    if PORTAL_ROLE_SUPER_ADMIN not in ctx.portal_roles:
        return ctx
    allowed = (settings.gateway_super_admin_subject or "").strip()
    if allowed and ctx.actor == allowed:
        return ctx
    new_pr = frozenset(r for r in ctx.portal_roles if r != PORTAL_ROLE_SUPER_ADMIN)
    return replace(ctx, portal_roles=new_pr)


def _enforce_commercial_customer_tenant_for_jwt(
    ctx: GatewayAuthContext,
    settings: Any,
) -> None:
    if not settings.commercial_enabled:
        return
    if not settings.sensitive_auth_enforced():
        return
    if ctx.auth_method != "jwt":
        return
    if not ctx.is_pure_customer_billing_scope():
        return
    if (ctx.tenant_id or "").strip():
        return
    raise HTTPException(
        status_code=403,
        detail={
            "code": "TENANT_ID_REQUIRED",
            "message": (
                "Fuer Kunden-Commerce ist der JWT-Claim tenant_id erforderlich "
                "(Mandantenisolation)."
            ),
        },
    )


def resolve_gateway_auth_with_diagnostic(
    *,
    request: Request,
    authorization: str | None = None,
    x_gateway_internal_key: str | None = None,
    x_admin_token: str | None = None,
) -> tuple[GatewayAuthContext | None, dict[str, str] | None]:
    """
    Liefert (ctx, None) bei Erfolg, sonst (None, diag) mit code/message/hint
    oder (None, None) wenn gar keine verwertbaren Credentials gesendet wurden.
    """
    settings = get_gateway_settings()
    internal = (x_gateway_internal_key or "").strip()
    expected_internal = settings.gateway_internal_api_key.strip()
    auth_header_raw = (authorization or "").strip()

    if expected_internal:
        if internal:
            if internal == expected_internal:
                roles = _parse_internal_key_roles_csv(settings.gateway_internal_key_roles)
                return (
                    GatewayAuthContext(
                        actor="gateway_internal",
                        auth_method="gateway_internal_key",
                        roles=roles,
                        tenant_id=None,
                        portal_roles=frozenset(),
                        jwt_role=None,
                    ),
                    None,
                )
            return (
                None,
                _auth_diag(
                    "GATEWAY_INTERNAL_KEY_MISMATCH",
                    f"Header {_HEADER_INTERNAL} stimmt nicht mit GATEWAY_INTERNAL_API_KEY ueberein.",
                    _HINT_GATEWAY_INTERNAL,
                ),
            )

    secret = settings.gateway_jwt_secret.strip()
    bearer = _parse_bearer(authorization)
    if auth_header_raw and not bearer and secret:
        return (
            None,
            _auth_diag(
                "GATEWAY_AUTHORIZATION_MALFORMED",
                "Authorization muss die Form 'Bearer <jwt>' haben.",
                _HINT_BFF_JWT,
            ),
        )

    if secret and bearer:
        try:
            payload = jwt.decode(
                bearer,
                secret,
                algorithms=["HS256"],
                audience=settings.gateway_jwt_audience,
                issuer=settings.gateway_jwt_issuer,
            )
        except jwt.ExpiredSignatureError:
            return (
                None,
                _auth_diag(
                    "GATEWAY_JWT_EXPIRED",
                    "JWT ist abgelaufen.",
                    "Neu minten: python scripts/mint_dashboard_gateway_jwt.py --env-file .env.local --update-env-file; "
                    "GATEWAY_JWT_SECRET unveraendert lassen.",
                ),
            )
        except jwt.PyJWTError:
            return (
                None,
                _auth_diag(
                    "GATEWAY_JWT_INVALID",
                    "JWT-Signatur oder Claims ungueltig (aud/iss).",
                    "GATEWAY_JWT_SECRET, GATEWAY_JWT_AUDIENCE und GATEWAY_JWT_ISSUER mit Mint-Skript abgleichen.",
                ),
            )
        if not isinstance(payload, dict):
            return (
                None,
                _auth_diag(
                    "GATEWAY_JWT_INVALID",
                    "JWT-Payload hat unerwartetes Format.",
                    _HINT_BFF_JWT,
                ),
            )
        sub = str(payload.get("sub") or "jwt_subject")
        roles = _jwt_roles(payload)
        if not roles:
            roles = frozenset({"gateway:read"})
        portal_roles = merge_portal_roles_from_payload(payload)
        ctx = GatewayAuthContext(
            actor=sub,
            auth_method="jwt",
            roles=roles,
            tenant_id=_jwt_tenant_id(payload),
            portal_roles=portal_roles,
            jwt_role=_jwt_main_role_from_payload(payload),
        )
        return (_strip_unauthorized_super_admin_portal(ctx, settings), None)

    if bearer and not secret:
        return (
            None,
            _auth_diag(
                "GATEWAY_JWT_SECRET_MISSING",
                "Bearer-JWT gesendet, aber GATEWAY_JWT_SECRET ist leer.",
                "Gateway startet mit GATEWAY_JWT_SECRET (gleicher Wert wie beim Mint).",
            ),
        )

    if settings.legacy_admin_token_allowed():
        token = (x_admin_token or "").strip()
        expected_adm = settings.admin_token.strip()
        if expected_adm and token and token == expected_adm:
            return (
                GatewayAuthContext(
                    actor="legacy_admin_token",
                    auth_method="legacy_admin_token",
                    roles=frozenset(
                        {
                            "admin:read",
                            "admin:write",
                            "gateway:read",
                            "operator:mutate",
                            "emergency:mutate",
                        }
                    ),
                    tenant_id=None,
                    portal_roles=frozenset(),
                    jwt_role=None,
                ),
                None,
            )

    return (None, None)


def _merge_capability(
    diag: dict[str, str] | None,
    capability: str,
) -> dict[str, str]:
    base = dict(diag) if diag else {}
    base["required_capability"] = capability
    return base


def _sensitive_read_problem_detail(
    ctx: GatewayAuthContext | None,
    diag: dict[str, str] | None,
) -> dict[str, str | bool]:
    if diag:
        return cast(dict[str, str | bool], _merge_capability(diag, "sensitive_read"))
    if ctx is not None:
        return _insufficient_roles_detail(
            ctx,
            capability="sensitive_read",
            message="Authentifiziert, aber Rolle fuer sensible Lese-Pfade fehlt.",
            hint=_role_hint_sensitive_read(),
        )
    return {
        "code": "GATEWAY_AUTH_MISSING",
        "message": "Kein gueltiges Bearer-JWT und kein gueltiger X-Gateway-Internal-Key.",
        "hint": _HINT_BFF_JWT + " " + _HINT_GATEWAY_INTERNAL,
        "required_capability": "sensitive_read",
    }


def _admin_read_problem_detail(
    ctx: GatewayAuthContext | None,
    diag: dict[str, str] | None,
) -> dict[str, str | bool]:
    if diag:
        return cast(dict[str, str | bool], _merge_capability(diag, "admin_read"))
    if ctx is not None:
        return _insufficient_roles_detail(
            ctx,
            capability="admin_read",
            message="Authentifiziert, aber admin:read/admin:write fehlt.",
            hint=_role_hint_admin_read(),
        )
    return {
        "code": "GATEWAY_AUTH_MISSING",
        "message": "Kein gueltiges Bearer-JWT / X-Gateway-Internal-Key / Legacy-Admin-Token.",
        "hint": _HINT_BFF_JWT + " Legacy: X-Admin-Token nur wenn GATEWAY_ALLOW_LEGACY_ADMIN_TOKEN=true.",
        "required_capability": "admin_read",
    }


def _admin_write_problem_detail(
    ctx: GatewayAuthContext | None,
    diag: dict[str, str] | None,
) -> dict[str, str | bool]:
    if diag:
        return cast(dict[str, str | bool], _merge_capability(diag, "admin_write"))
    if ctx is not None:
        return _insufficient_roles_detail(
            ctx,
            capability="admin_write",
            message="Authentifiziert, aber admin:write fehlt.",
            hint=_role_hint_admin_write(),
        )
    return {
        "code": "GATEWAY_AUTH_MISSING",
        "message": "Kein gueltiges Bearer-JWT oder X-Gateway-Internal-Key mit Schreibrechten.",
        "hint": _HINT_BFF_JWT + " " + _HINT_GATEWAY_INTERNAL,
        "required_capability": "admin_write",
    }


def _billing_read_problem_detail(
    ctx: GatewayAuthContext | None,
    diag: dict[str, str] | None,
) -> dict[str, str | bool]:
    if diag:
        return cast(dict[str, str | bool], _merge_capability(diag, "billing_read"))
    if ctx is not None:
        return _insufficient_roles_detail(
            ctx,
            capability="billing_read",
            message="Authentifiziert, aber billing:read oder Admin-Rolle fehlt.",
            hint=_role_hint_billing_read(),
        )
    return {
        "code": "GATEWAY_AUTH_MISSING",
        "message": "Kein gueltiges Bearer-JWT oder X-Gateway-Internal-Key fuer Billing-Lesezugriff.",
        "hint": _HINT_BFF_JWT,
        "required_capability": "billing_read",
    }


def _billing_admin_problem_detail(
    ctx: GatewayAuthContext | None,
    diag: dict[str, str] | None,
) -> dict[str, str | bool]:
    if diag:
        return cast(dict[str, str | bool], _merge_capability(diag, "billing_admin"))
    if ctx is not None:
        return _insufficient_roles_detail(
            ctx,
            capability="billing_admin",
            message="Authentifiziert, aber billing:admin oder admin:write fehlt.",
            hint=_role_hint_billing_admin(),
        )
    return {
        "code": "GATEWAY_AUTH_MISSING",
        "message": "Kein gueltiges Bearer-JWT oder X-Gateway-Internal-Key fuer Billing-Admin.",
        "hint": _HINT_BFF_JWT,
        "required_capability": "billing_admin",
    }


def _admin_forbidden_customer_session_detail() -> dict[str, str | bool]:
    return {
        "code": "GATEWAY_FORBIDDEN_CUSTOMER_SESSION",
        "message": "Kundenportal-Token: Zugriff auf Admin-APIs ist nicht erlaubt.",
        "hint": (
            "Admin-APIs verlangen ein Operator-JWT (ohne customer in portal_roles) und "
            "gateway_roles admin:read bzw. admin:write, oder X-Gateway-Internal-Key (BFF, nur serverseitig). "
            "INTERNAL_API_KEY (X-Internal-Service-Key) ist kein Kunden-Token und gehoert niemals ins Frontend."
        ),
    }


def _forbid_admin_if_customer_jwt(
    request: Request,
    ctx: GatewayAuthContext | None,
    *, event: str
) -> None:
    if ctx is None or not ctx.is_customer_portal_jwt():
        return
    record_gateway_auth_failure(
        request,
        event,
        actor=ctx.actor,
        auth_method=ctx.auth_method,
        extra={"failure_code": "GATEWAY_FORBIDDEN_CUSTOMER_SESSION"},
    )
    raise HTTPException(
        status_code=403,
        detail=_admin_forbidden_customer_session_detail(),
    )


def _admin_forbidden_jwt_not_admin_role_detail() -> dict[str, str | bool]:
    return {
        "code": "GATEWAY_FORBIDDEN_JWT_ROLE",
        "message": (
            "Admin-APIs: Claim role muss admin sein (Hauptrolle, neben portal_roles)."
        ),
        "hint": (
            "Mint: scripts/mint_dashboard_gateway_jwt.py setzt role: admin. "
            "Fehlender/ falscher Wert: abgelehnt. S2S: X-Gateway-Internal-Key."
        ),
    }


def _forbid_admin_if_jwt_main_role_not_admin(
    request: Request,
    ctx: GatewayAuthContext | None,
    *, event: str
) -> None:
    if ctx is None or ctx.auth_method != "jwt":
        return
    r = (ctx.jwt_role or "").strip().lower()
    if r == "admin":
        return
    record_gateway_auth_failure(
        request,
        event,
        actor=ctx.actor,
        auth_method=ctx.auth_method,
        extra={"failure_code": "GATEWAY_FORBIDDEN_JWT_ROLE", "jwt_role": r or None},
    )
    raise HTTPException(
        status_code=403,
        detail=_admin_forbidden_jwt_not_admin_role_detail(),
    )


def resolve_gateway_auth(
    *,
    request: Request,
    authorization: str | None = None,
    x_gateway_internal_key: str | None = None,
    x_admin_token: str | None = None,
) -> GatewayAuthContext | None:
    ctx, _diag = resolve_gateway_auth_with_diagnostic(
        request=request,
        authorization=authorization,
        x_gateway_internal_key=x_gateway_internal_key,
        x_admin_token=x_admin_token,
    )
    return ctx


async def require_sensitive_auth(
    request: Request,
    authorization: str | None = Header(None),
    x_gateway_internal_key: str | None = Header(None, alias=_HEADER_INTERNAL),
) -> GatewayAuthContext:
    settings = get_gateway_settings()
    if not settings.sensitive_auth_enforced():
        return GatewayAuthContext(
            actor="anonymous",
            auth_method="none",
            roles=frozenset({"gateway:read", "admin:read"}),
            tenant_id=None,
        )
    ctx, diag = resolve_gateway_auth_with_diagnostic(
        request=request,
        authorization=authorization,
        x_gateway_internal_key=x_gateway_internal_key,
        x_admin_token=None,
    )
    if ctx is not None and ctx.can_sensitive_read():
        return ctx
    fc = (diag or {}).get("code") if diag else None
    if fc is None and ctx is not None:
        fc = "GATEWAY_INSUFFICIENT_ROLES"
    elif fc is None:
        fc = "GATEWAY_AUTH_MISSING"
    record_gateway_auth_failure(
        request,
        "auth_failure_sensitive_read",
        actor=ctx.actor if ctx is not None else "anonymous",
        auth_method=ctx.auth_method if ctx is not None else "none",
        extra={"failure_code": fc},
    )
    raise HTTPException(
        status_code=401,
        detail=_sensitive_read_problem_detail(ctx, diag),
    )


async def require_admin_read(
    request: Request,
    authorization: str | None = Header(None),
    x_gateway_internal_key: str | None = Header(None, alias=_HEADER_INTERNAL),
    x_admin_token: str | None = Header(None, alias=_HEADER_LEGACY_ADMIN),
) -> GatewayAuthContext:
    """
    Admin-Lese-Autorisierung. Kein anonymes admin:read mehr, wenn SENSITIVE_AUTH deaktiviert:
    lokal nur mit echtem JWT, X-Gateway-Internal-Key (BFF) oder Legacy-Admin-Token.
    Kunden-Portal-Bearer: immer 403 auf Admin-Routen.
    Bearer-JWT: Claim role=admin (siehe require_admin_role).
    """
    settings = get_gateway_settings()
    ctx, diag = resolve_gateway_auth_with_diagnostic(
        request=request,
        authorization=authorization,
        x_gateway_internal_key=x_gateway_internal_key,
        x_admin_token=x_admin_token if settings.legacy_admin_token_allowed() else None,
    )
    _forbid_admin_if_customer_jwt(
        request, ctx, event="auth_forbidden_customer_admin_read"
    )
    _forbid_admin_if_jwt_main_role_not_admin(
        request, ctx, event="auth_forbidden_jwt_role_admin_read"
    )
    if ctx is not None and ctx.can_admin_read():
        return ctx
    fc = (diag or {}).get("code") if diag else None
    if fc is None and ctx is not None:
        fc = "GATEWAY_INSUFFICIENT_ROLES"
    elif fc is None:
        fc = "GATEWAY_AUTH_MISSING"
    record_gateway_auth_failure(
        request,
        "auth_failure_admin_read",
        actor=ctx.actor if ctx is not None else "anonymous",
        auth_method=ctx.auth_method if ctx is not None else "none",
        extra={"failure_code": fc},
    )
    raise HTTPException(status_code=401, detail=_admin_read_problem_detail(ctx, diag))


async def require_admin_write(
    request: Request,
    authorization: str | None = Header(None),
    x_gateway_internal_key: str | None = Header(None, alias=_HEADER_INTERNAL),
    x_admin_token: str | None = Header(None, alias=_HEADER_LEGACY_ADMIN),
) -> GatewayAuthContext:
    settings = get_gateway_settings()
    ctx, diag = resolve_gateway_auth_with_diagnostic(
        request=request,
        authorization=authorization,
        x_gateway_internal_key=x_gateway_internal_key,
        x_admin_token=x_admin_token if settings.legacy_admin_token_allowed() else None,
    )
    _forbid_admin_if_customer_jwt(
        request, ctx, event="auth_forbidden_customer_admin_write"
    )
    _forbid_admin_if_jwt_main_role_not_admin(
        request, ctx, event="auth_forbidden_jwt_role_admin_write"
    )
    if ctx is not None and ctx.can_admin_write():
        return ctx
    fc = (diag or {}).get("code") if diag else None
    if fc is None and ctx is not None:
        fc = "GATEWAY_INSUFFICIENT_ROLES"
    elif fc is None:
        fc = "GATEWAY_AUTH_MISSING"
    record_gateway_auth_failure(
        request,
        "auth_failure_admin_write",
        actor=ctx.actor if ctx is not None else "anonymous",
        auth_method=ctx.auth_method if ctx is not None else "none",
        extra={"failure_code": fc},
    )
    raise HTTPException(status_code=401, detail=_admin_write_problem_detail(ctx, diag))


async def require_live_stream_access(
    request: Request,
    authorization: str | None = Header(None),
    x_gateway_internal_key: str | None = Header(None, alias=_HEADER_INTERNAL),
) -> GatewayAuthContext:
    """Live-SSE: bei erzwungenem Auth JWT/Internal-Key oder signiertes HttpOnly-Cookie."""
    settings = get_gateway_settings()
    if not settings.sensitive_auth_enforced():
        return GatewayAuthContext(
            actor="anonymous",
            auth_method="none",
            roles=frozenset({"gateway:read"}),
            tenant_id=None,
        )
    ctx, diag = resolve_gateway_auth_with_diagnostic(
        request=request,
        authorization=authorization,
        x_gateway_internal_key=x_gateway_internal_key,
        x_admin_token=None,
    )
    if ctx is not None and ctx.can_sensitive_read():
        return ctx
    fail_ctx, fail_diag = ctx, diag
    secret = resolve_sse_signing_secret(settings)
    if secret:
        raw = request.cookies.get(settings.gateway_sse_cookie_name)
        if raw and verify_sse_ticket(raw, secret=secret):
            return GatewayAuthContext(
                actor="sse_cookie",
                auth_method="sse_cookie",
                roles=frozenset({"gateway:read"}),
                tenant_id=None,
            )
    record_gateway_auth_failure(
        request,
        "auth_failure_live_stream",
        extra={"failure_code": (fail_diag or {}).get("code") or "live_stream_auth_failed"},
    )
    d = _sensitive_read_problem_detail(fail_ctx, fail_diag)
    d = dict(d)
    d["code"] = "LIVE_STREAM_AUTH_REQUIRED"
    d["message"] = (
        "Live-Stream: Bearer/X-Gateway-Internal-Key fehlgeschlagen oder SSE-Cookie ungueltig — "
        + str(d.get("message", ""))
    )
    d["hint"] = (
        str(d.get("hint", ""))
        + " Zusaetzlich: gueltiges SSE-Session-Cookie (Dashboard) pruefen."
    )
    raise HTTPException(status_code=401, detail=d)


async def require_billing_read(
    request: Request,
    authorization: str | None = Header(None),
    x_gateway_internal_key: str | None = Header(None, alias=_HEADER_INTERNAL),
) -> GatewayAuthContext:
    """Usage-/Ledger-Lesepfade: billing:read oder Admin."""
    settings = get_gateway_settings()
    if not settings.sensitive_auth_enforced():
        return GatewayAuthContext(
            actor="anonymous",
            auth_method="none",
            roles=frozenset({"billing:read", "admin:read", "admin:write"}),
            tenant_id=None,
        )
    ctx, diag = resolve_gateway_auth_with_diagnostic(
        request=request,
        authorization=authorization,
        x_gateway_internal_key=x_gateway_internal_key,
        x_admin_token=None,
    )
    if ctx is not None and ctx.can_billing_read():
        _enforce_commercial_customer_tenant_for_jwt(ctx, settings)
        return ctx
    fc = (diag or {}).get("code") if diag else None
    if fc is None and ctx is not None:
        fc = "GATEWAY_INSUFFICIENT_ROLES"
    elif fc is None:
        fc = "GATEWAY_AUTH_MISSING"
    record_gateway_auth_failure(
        request,
        "auth_failure_billing_read",
        actor=ctx.actor if ctx is not None else "anonymous",
        auth_method=ctx.auth_method if ctx is not None else "none",
        extra={"failure_code": fc},
    )
    raise HTTPException(status_code=401, detail=_billing_read_problem_detail(ctx, diag))


async def require_billing_admin(
    request: Request,
    authorization: str | None = Header(None),
    x_gateway_internal_key: str | None = Header(None, alias=_HEADER_INTERNAL),
) -> GatewayAuthContext:
    """Commerce-Admin: billing:admin oder admin:write (Zahlungen, Wallet, Integrations-Hinweise)."""
    settings = get_gateway_settings()
    if not settings.sensitive_auth_enforced():
        return GatewayAuthContext(
            actor="anonymous",
            auth_method="none",
            roles=frozenset({"billing:admin", "admin:write"}),
            tenant_id=None,
        )
    ctx, diag = resolve_gateway_auth_with_diagnostic(
        request=request,
        authorization=authorization,
        x_gateway_internal_key=x_gateway_internal_key,
        x_admin_token=None,
    )
    if ctx is not None and ctx.can_billing_admin():
        return ctx
    fc = (diag or {}).get("code") if diag else None
    if fc is None and ctx is not None:
        fc = "GATEWAY_INSUFFICIENT_ROLES"
    elif fc is None:
        fc = "GATEWAY_AUTH_MISSING"
    record_gateway_auth_failure(
        request,
        "auth_failure_billing_admin",
        actor=ctx.actor if ctx is not None else "anonymous",
        auth_method=ctx.auth_method if ctx is not None else "none",
        extra={"failure_code": fc},
    )
    raise HTTPException(status_code=401, detail=_billing_admin_problem_detail(ctx, diag))


async def require_operator_aggregate_auth(
    request: Request,
    authorization: str | None = Header(None),
    x_gateway_internal_key: str | None = Header(None, alias=_HEADER_INTERNAL),
) -> GatewayAuthContext:
    """Aggregierte System-/Ops-Sicht: bei erzwungenem Auth wie sensible Reads."""
    settings = get_gateway_settings()
    if not settings.sensitive_auth_enforced():
        return GatewayAuthContext(
            actor="anonymous",
            auth_method="none",
            roles=frozenset({"gateway:read"}),
            tenant_id=None,
        )
    ctx, diag = resolve_gateway_auth_with_diagnostic(
        request=request,
        authorization=authorization,
        x_gateway_internal_key=x_gateway_internal_key,
        x_admin_token=None,
    )
    if ctx is not None and ctx.can_sensitive_read():
        return ctx
    fc = (diag or {}).get("code") if diag else None
    if fc is None and ctx is not None:
        fc = "GATEWAY_INSUFFICIENT_ROLES"
    elif fc is None:
        fc = "GATEWAY_AUTH_MISSING"
    record_gateway_auth_failure(
        request,
        "auth_failure_operator_aggregate",
        actor=ctx.actor if ctx is not None else "anonymous",
        auth_method=ctx.auth_method if ctx is not None else "none",
        extra={"failure_code": fc},
    )
    d = _sensitive_read_problem_detail(ctx, diag)
    d = dict(d)
    d["code"] = "OPERATOR_AGGREGATE_AUTH_REQUIRED"
    d["message"] = "Operator-Systempfad: " + str(d.get("message", ""))
    raise HTTPException(status_code=401, detail=d)


async def require_customer_role(
    request: Request,
    authorization: str | None = Header(None),
    x_gateway_internal_key: str | None = Header(None, alias=_HEADER_INTERNAL),
) -> GatewayAuthContext:
    """
    Kunden- und Abo-Scope: delegiert an require_billing_read (identische technische Pruefung).
    Gegenstueck zu require_admin_read / require_admin_write auf /v1/admin/... .
    """
    return await require_billing_read(
        request, authorization, x_gateway_internal_key
    )


# --- RBAC: /v1/admin bevorzugt explizit benannte Dependencies ---
require_admin_read_role = require_admin_read
require_admin_write_role = require_admin_write
# /v1/admin: Kunden-Portal 403, JWT muss role=admin; Schreiben: require_admin_write_role
require_admin_role = require_admin_read
