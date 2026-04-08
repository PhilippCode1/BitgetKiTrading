from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
API_GATEWAY_SRC = REPO_ROOT / "services" / "api-gateway" / "src"
for candidate in (REPO_ROOT, API_GATEWAY_SRC):
    s = str(candidate)
    if s not in sys.path:
        sys.path.insert(0, s)


def test_sanitize_display_name_strips_control_chars() -> None:
    from api_gateway.db_customer_portal import sanitize_display_name

    assert sanitize_display_name("  Anna\x00 ") == "Anna"
    assert sanitize_display_name("   ") is None
    assert sanitize_display_name(None) is None
    long = "x" * 200
    assert len(sanitize_display_name(long) or "") == 120


def test_access_matrix_flags() -> None:
    from api_gateway.auth import GatewayAuthContext

    ctx = GatewayAuthContext(
        actor="u1",
        auth_method="jwt",
        roles=frozenset({"billing:read"}),
        tenant_id="t1",
        portal_roles=frozenset({"customer"}),
    )
    m = ctx.access_matrix()
    assert m["billing_read"] is True
    assert m["portal_customer"] is True
    assert m["admin_write"] is False
