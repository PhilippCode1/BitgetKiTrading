"""Tests fuer shared_py.portal_access_contract (Prompt 10)."""

from __future__ import annotations

from shared_py.portal_access_contract import (
    JWT_CLAIM_PLATFORM_ROLE,
    JWT_CLAIM_PORTAL_ROLES,
    PORTAL_ROLE_SUPER_ADMIN,
    jwt_payload_claims_super_admin_portal,
    merge_portal_roles_from_payload,
)


def test_merge_portal_roles_list_and_platform_role() -> None:
    p = {
        JWT_CLAIM_PORTAL_ROLES: ["customer", PORTAL_ROLE_SUPER_ADMIN],
        JWT_CLAIM_PLATFORM_ROLE: "support_read",
    }
    assert merge_portal_roles_from_payload(p) == frozenset(
        {"customer", PORTAL_ROLE_SUPER_ADMIN, "support_read"}
    )


def test_jwt_payload_claims_super_admin_from_platform_role() -> None:
    assert jwt_payload_claims_super_admin_portal(
        {JWT_CLAIM_PLATFORM_ROLE: PORTAL_ROLE_SUPER_ADMIN}
    )
    assert not jwt_payload_claims_super_admin_portal(
        {JWT_CLAIM_PLATFORM_ROLE: "customer"}
    )
