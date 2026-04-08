"""
Portal- und JWT-Konventionen fuer Mandanten-UI vs. Super-Admin (Modul Mate).

Bezug: docs/ROLES_AND_LIFECYCLE_MODUL_MATE.md, PlatformRole in customer_lifecycle.

Technische AuthZ bleibt in gateway_roles (z. B. billing:read, admin:write).
portal_roles / platform_role dienen der UI-Kennzeichnung und duerfen nicht
die technische admin:write-Pruefung ersetzen.
"""

from __future__ import annotations

from typing import Any

from shared_py.customer_lifecycle import PlatformRole

PORTAL_ACCESS_MODULE_VERSION = "1.0.0"

# JWT / introspection: Liste oder Leerzeichen-String (analog gateway_roles).
JWT_CLAIM_PORTAL_ROLES = "portal_roles"
# Optionaler Einzelwert, semantisch deckungsgleich mit PlatformRole (string).
JWT_CLAIM_PLATFORM_ROLE = "platform_role"

# portal_roles / platform_role Wert fuer alleinigen Voll-Admin (Philipp Crljic) [FEST].
PORTAL_ROLE_SUPER_ADMIN = PlatformRole.SUPER_ADMIN.value
PORTAL_ROLE_CUSTOMER = PlatformRole.CUSTOMER.value


def jwt_payload_claims_super_admin_portal(payload: dict[str, Any]) -> bool:
    """True wenn Payload Super-Admin-Portal markiert (vor Subject-Validierung)."""
    pr = payload.get(JWT_CLAIM_PLATFORM_ROLE)
    if isinstance(pr, str) and pr.strip() == PORTAL_ROLE_SUPER_ADMIN:
        return True
    raw = payload.get(JWT_CLAIM_PORTAL_ROLES)
    if isinstance(raw, list):
        return any(
            str(x).strip() == PORTAL_ROLE_SUPER_ADMIN for x in raw if x is not None
        )
    if isinstance(raw, str) and raw.strip():
        return PORTAL_ROLE_SUPER_ADMIN in raw.split()
    return False


def merge_portal_roles_from_payload(payload: dict[str, Any]) -> frozenset[str]:
    """
    Effektive Portal-Rollen aus portal_roles-Liste/-String und optionalem platform_role.
    """
    out: set[str] = set()
    raw = payload.get(JWT_CLAIM_PORTAL_ROLES)
    if isinstance(raw, list):
        out.update(str(x) for x in raw if x is not None and str(x).strip())
    elif isinstance(raw, str) and raw.strip():
        out.update(raw.split())
    prm = payload.get(JWT_CLAIM_PLATFORM_ROLE)
    if isinstance(prm, str) and prm.strip():
        out.add(prm.strip())
    return frozenset(out)
