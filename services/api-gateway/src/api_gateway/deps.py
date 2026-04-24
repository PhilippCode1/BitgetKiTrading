"""Zusammengesetzte FastAPI-Dependencies."""

from __future__ import annotations

import hashlib
import logging
from decimal import Decimal
from typing import Any

import psycopg
from fastapi import Depends, HTTPException, Request
from psycopg.rows import dict_row
from shared_py.billing_wallet import fetch_prepaid_balance_list_usd
from shared_py.modul_mate_db_gates import assert_execution_allowed
from shared_py.product_policy import (
    ExecutionPolicyViolationError,
    plan_entitlement_key_enabled,
    prepaid_balance_sufficient,
)

from api_gateway.audit import record_gateway_audit_line
from api_gateway.auth import GatewayAuthContext, require_sensitive_auth
from api_gateway.config import get_gateway_settings
from api_gateway.db import DatabaseHealthError, get_database_url
from api_gateway.rate_limit import get_rate_limit_redis
from api_gateway.tenant_rls import gateway_psycopg

logger = logging.getLogger("api_gateway.deps")

# Stabiler Fehler-Code fuer Clients (i18n-Keys, keine lokalisierten Kundenfloskeln hier)
LIVE_TRADING_NOT_ALLOWED_ERROR_CODE = "LIVE_TRADING_NOT_ALLOWED_NO_CONTRACT"
COMMERCIAL_ENTITLEMENT_ERROR_CODE = "COMMERCIAL_ENTITLEMENT_REQUIRED"


def _bypasses_commercial_entitlement_check(auth: GatewayAuthContext) -> bool:
    if auth.has_role("admin:read") or auth.has_role("admin:write"):
        return True
    if auth.has_role("operator:mutate"):
        return True
    if auth.auth_method in (
        "gateway_internal_key",
        "legacy_admin_token",
        "dev_anonymous",
    ):
        return True
    return False


def _evaluate_commercial_feature_access(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    feature_name: str,
) -> tuple[bool, str, dict[str, Any]]:
    row = conn.execute(
        """
        SELECT plan_entitlement_key, min_prepaid_balance_list_usd
        FROM app.commercial_usage_entitlements
        WHERE feature_name = %s
        """,
        (feature_name,),
    ).fetchone()
    if row is None:
        return True, "feature_catalog_missing", {"feature": feature_name}
    plan_key = str(row["plan_entitlement_key"])
    min_b = row["min_prepaid_balance_list_usd"]
    min_d = (
        min_b
        if isinstance(min_b, Decimal)
        else Decimal(str(min_b)) if min_b is not None else Decimal("0")
    )
    trow = conn.execute(
        """
        SELECT p.entitlements_json, t.plan_id
        FROM app.tenant_commercial_state t
        JOIN app.commercial_plan_definitions p ON p.plan_id = t.plan_id
        WHERE t.tenant_id = %s
        """,
        (tenant_id,),
    ).fetchone()
    if trow is None:
        return (
            False,
            "no_tenant_commercial_state",
            {
                "feature": feature_name,
                "plan_entitlement_key": plan_key,
            },
        )
    ent = trow.get("entitlements_json")
    if isinstance(ent, str):
        import json

        try:
            ent = json.loads(ent)
        except json.JSONDecodeError:
            ent = {}
    if not isinstance(ent, dict):
        ent = {}
    if not plan_entitlement_key_enabled(ent, key=plan_key):
        return (
            False,
            "plan_feature_disabled",
            {
                "feature": feature_name,
                "plan_id": str(trow.get("plan_id") or ""),
                "plan_entitlement_key": plan_key,
            },
        )
    bal = fetch_prepaid_balance_list_usd(conn, tenant_id=tenant_id)
    if not prepaid_balance_sufficient(bal, min_list_usd=min_d):
        return (
            False,
            "insufficient_prepaid",
            {
                "feature": feature_name,
                "min_prepaid_balance_list_usd": str(min_d),
                "balance_list_usd": str(bal),
            },
        )
    return True, "ok", {"feature": feature_name, "plan_id": str(trow.get("plan_id") or "")}


def commercial_feature_access_check_or_http(
    *,
    auth: GatewayAuthContext,
    feature_name: str,
) -> None:
    """Wirft 402/503 sofern Feature-Katalog und Mandant existieren; sonst ok."""
    s = get_gateway_settings()
    if not s.commercial_enabled or not s.commercial_entitlement_enforce:
        return
    if _bypasses_commercial_entitlement_check(auth):
        return
    dft = (s.commercial_default_tenant_id or "default").strip()
    tid = auth.effective_tenant(default_tenant_id=dft)
    if not (tid or "").strip():
        raise HTTPException(
            status_code=402,
            detail={
                "error": COMMERCIAL_ENTITLEMENT_ERROR_CODE,
                "feature": feature_name,
                "reason": "missing_tenant_id",
            },
        )
    ok, reason, meta = True, "ok", {"feature": feature_name}
    try:
        with gateway_psycopg(
            get_database_url(),
            row_factory=dict_row,
            connect_timeout=4,
            tenant_id=tid,
        ) as conn:
            ok, reason, meta = _evaluate_commercial_feature_access(
                conn, tenant_id=tid, feature_name=feature_name
            )
    except psycopg.errors.UndefinedTable as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "COMMERCIAL_ENTITLEMENT_SCHEMA_MISSING",
                "message": "623_commercial_usage_entitlements_feature_catalog.sql",
            },
        ) from exc
    except DatabaseHealthError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "GATEWAY_COMMERCIAL_ENTITLEMENT_DB_UNAVAILABLE"},
        ) from exc
    if not ok:
        raise HTTPException(
            status_code=402,
            detail={
                "error": COMMERCIAL_ENTITLEMENT_ERROR_CODE,
                "feature": feature_name,
                "reason": reason,
                **{k: v for k, v in meta.items() if k != "feature"},
            },
        )


def require_commercial_entitlement(feature_name: str):
    def _dep(
        auth: GatewayAuthContext = Depends(require_sensitive_auth),  # noqa: B008
    ) -> GatewayAuthContext:
        commercial_feature_access_check_or_http(auth=auth, feature_name=feature_name)
        return auth

    return _dep


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
    with gateway_psycopg(
        get_database_url(),
        row_factory=dict_row,
        connect_timeout=4,
        tenant_id=tenant_id,
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
