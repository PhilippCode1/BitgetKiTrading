"""Zusammengesetzte FastAPI-Dependencies."""

from __future__ import annotations

import hashlib
import logging

import psycopg
from fastapi import Depends, HTTPException, Request
from psycopg.rows import dict_row
from shared_py.modul_mate_db_gates import assert_execution_allowed
from shared_py.product_policy import ExecutionPolicyViolationError

from api_gateway.audit import record_gateway_audit_line
from api_gateway.auth import GatewayAuthContext, require_sensitive_auth
from api_gateway.config import get_gateway_settings
from api_gateway.db import DatabaseHealthError, get_database_url
from api_gateway.rate_limit import get_rate_limit_redis

logger = logging.getLogger("api_gateway.deps")

# Stabiler Fehler-Code fuer Clients (i18n-Keys, keine lokalisierten Kundenfloskeln hier)
LIVE_TRADING_NOT_ALLOWED_ERROR_CODE = "LIVE_TRADING_NOT_ALLOWED_NO_CONTRACT"


def _bypasses_live_tenant_trading_check(auth: GatewayAuthContext) -> bool:
    """Break-Glass / Dienst-Identitaeten ohne Mandanten-Vertragspflicht."""
    if auth.has_role("admin:write"):
        return True
    if auth.auth_method in (
        "gateway_internal_key",
        "legacy_admin_token",
        "dev_anonymous",
    ):
        return True
    return False


def _cache_key(tenant_id: str) -> str:
    h = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()[:32]
    return f"gw:live_tenant_ok:v1:{h}"


def _read_live_ok_from_cache(tenant_id: str, *, ttl: int) -> bool | None:
    if ttl <= 0:
        return None
    r = get_rate_limit_redis()
    if r is None:
        return None
    try:
        v = r.get(_cache_key(tenant_id))
    except Exception as exc:
        logger.warning("live policy cache get failed: %s", exc)
        return None
    if v in (b"1", "1", b"Y", "Y", b"ok", "ok", 1):
        return True
    return None


def _write_live_ok_to_cache(tenant_id: str, *, ttl: int) -> None:
    if ttl <= 0:
        return
    r = get_rate_limit_redis()
    if r is None:
        return
    try:
        r.setex(_cache_key(tenant_id), int(ttl), b"1")
    except Exception as exc:
        logger.warning("live policy cache set failed: %s", exc)


def _live_policy_db_check(tenant_id: str) -> None:
    with psycopg.connect(
        get_database_url(),
        row_factory=dict_row,
        connect_timeout=4,
    ) as conn:
        assert_execution_allowed(conn, tenant_id=tenant_id, mode="LIVE")


def verify_live_trading_capability(auth: GatewayAuthContext) -> None:
    """
    Fail-Fast: Mandanten-JWT/Operator braucht dieselbe DB-Policy wie live-broker
    (assert_execution_allowed LIVE). Aufruf z. B. in mutation_deps. 403/503 siehe Code.
    """
    s = get_gateway_settings()
    if not s.live_broker_gateway_live_policy_enforce:
        return
    if _bypasses_live_tenant_trading_check(auth):
        return
    dft = (s.commercial_default_tenant_id or "default").strip()
    tid = auth.effective_tenant(default_tenant_id=dft)
    ttl = int(s.live_broker_gateway_live_policy_cache_ttl_sec)
    if _read_live_ok_from_cache(tid, ttl=ttl) is True:
        return
    try:
        _live_policy_db_check(tid)
    except DatabaseHealthError as exc:
        logger.warning("live trading policy: database unavailable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "GATEWAY_LIVE_POLICY_DATABASE_UNAVAILABLE",
                "message": "Policy-Datenbank nicht verfuegbar.",
            },
        ) from exc
    except ExecutionPolicyViolationError:
        raise HTTPException(
            status_code=403,
            detail={"error": LIVE_TRADING_NOT_ALLOWED_ERROR_CODE},
        ) from None
    except Exception as exc:
        logger.exception("live trading policy check failed tenant_id=%s", tid)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "GATEWAY_LIVE_POLICY_CHECK_FAILED",
                "message": "Policy-Pruefung fehlgeschlagen.",
            },
        ) from exc
    _write_live_ok_to_cache(tid, ttl=ttl)


def audited_sensitive(action: str):
    async def _dep(
        request: Request,
        auth: GatewayAuthContext = Depends(require_sensitive_auth),  # noqa: B008
    ) -> GatewayAuthContext:
        record_gateway_audit_line(request, auth, action)
        return auth

    return _dep
