"""Kurzlebige, gebundene Tokens fuer Gateway -> live-broker Mutationen (Anti-Replay via Redis)."""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from typing import Any

import jwt
from fastapi import HTTPException
from redis import Redis
from redis.exceptions import RedisError

from api_gateway.config import GatewaySettings

logger = logging.getLogger("api_gateway.manual_action")

MANUAL_ACTION_AUD = "gateway-manual-action-v1"
MANUAL_ACTION_ISS = "bitget-btc-ai-gateway"

# Route-Keys muessen mit Mint-Payload und FastAPI-Routen uebereinstimmen.
ROUTE_KEY_OPERATOR_RELEASE = "live_broker_operator_release"
ROUTE_KEY_SAFETY_KILL_SWITCH_ARM = "live_broker_safety_kill_switch_arm"
ROUTE_KEY_SAFETY_KILL_SWITCH_RELEASE = "live_broker_safety_kill_switch_release"
ROUTE_KEY_SAFETY_CANCEL_ALL = "live_broker_safety_orders_cancel_all"
ROUTE_KEY_SAFETY_EMERGENCY_FLATTEN = "live_broker_safety_emergency_flatten"
ROUTE_KEY_SAFETY_LATCH_RELEASE = "live_broker_safety_safety_latch_release"

OPERATOR_ROUTE_KEYS: frozenset[str] = frozenset(
    {
        ROUTE_KEY_OPERATOR_RELEASE,
        ROUTE_KEY_SAFETY_LATCH_RELEASE,
    }
)
EMERGENCY_ROUTE_KEYS: frozenset[str] = frozenset(
    {
        ROUTE_KEY_SAFETY_KILL_SWITCH_ARM,
        ROUTE_KEY_SAFETY_KILL_SWITCH_RELEASE,
        ROUTE_KEY_SAFETY_CANCEL_ALL,
        ROUTE_KEY_SAFETY_EMERGENCY_FLATTEN,
    }
)


def canonical_payload_fingerprint(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def resolve_manual_action_signing_secret(settings: GatewaySettings) -> str:
    raw = settings.gateway_manual_action_secret.strip()
    if raw:
        return raw
    jwt_s = settings.gateway_jwt_secret.strip()
    if jwt_s:
        return jwt_s
    raise HTTPException(
        status_code=503,
        detail={
            "code": "MANUAL_ACTION_SECRET_MISSING",
            "message": "GATEWAY_MANUAL_ACTION_SECRET oder GATEWAY_JWT_SECRET erforderlich.",
        },
    )


def mint_manual_action_token(
    *,
    settings: GatewaySettings,
    actor: str,
    route_key: str,
    payload: dict[str, Any],
) -> tuple[str, int]:
    secret = resolve_manual_action_signing_secret(settings)
    fp = canonical_payload_fingerprint(payload)
    jti = str(uuid.uuid4())
    now = int(time.time())
    ttl = max(30, int(settings.gateway_manual_action_ttl_sec))
    exp = now + ttl
    tok = jwt.encode(
        {
            "sub": str(actor)[:200],
            "rk": route_key,
            "fp": fp,
            "jti": jti,
            "iat": now,
            "exp": exp,
            "aud": MANUAL_ACTION_AUD,
            "iss": MANUAL_ACTION_ISS,
        },
        secret,
        algorithm="HS256",
    )
    return str(tok), exp


def verify_manual_action_token(
    *,
    token: str,
    settings: GatewaySettings,
    route_key: str,
    payload: dict[str, Any],
    redis_client: Redis | None,
) -> dict[str, Any]:
    secret = resolve_manual_action_signing_secret(settings)
    try:
        data = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=MANUAL_ACTION_AUD,
            issuer=MANUAL_ACTION_ISS,
            options={"require": ["exp", "jti", "rk", "fp"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=401,
            detail={"code": "MANUAL_ACTION_TOKEN_INVALID", "message": str(exc)},
        ) from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=401, detail="invalid token payload")
    if str(data.get("rk")) != route_key:
        raise HTTPException(
            status_code=403,
            detail={"code": "MANUAL_ACTION_ROUTE_MISMATCH", "message": "Token passt nicht zur Route."},
        )
    if str(data.get("fp")) != canonical_payload_fingerprint(payload):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "MANUAL_ACTION_PAYLOAD_MISMATCH",
                "message": "Request-Body weicht von Token-Bindung ab.",
            },
        )
    jti = str(data.get("jti") or "")
    if not jti:
        raise HTTPException(status_code=401, detail="token ohne jti")
    if settings.gateway_manual_action_redis_replay_guard:
        if redis_client is None:
            raise HTTPException(
                status_code=503,
                detail={"code": "MANUAL_ACTION_REDIS_REQUIRED", "message": "Anti-Replay nicht verfuegbar."},
            )
        exp_ts = int(data.get("exp") or 0)
        ttl = max(5, exp_ts - int(time.time()) + 10)
        try:
            ok = bool(redis_client.set(f"gateway:mia:jti:{jti}", b"1", nx=True, ex=ttl))
        except RedisError as exc:
            logger.warning("manual action redis replay guard: %s", exc)
            raise HTTPException(
                status_code=503,
                detail={"code": "MANUAL_ACTION_REDIS_ERROR", "message": "Anti-Replay fehlgeschlagen."},
            ) from exc
        if not ok:
            raise HTTPException(
                status_code=409,
                detail={"code": "MANUAL_ACTION_REPLAY", "message": "Token bereits verbraucht oder aktiv."},
            )
    return data


def fingerprint_payload_for_operator_release(
    execution_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    out = dict(body)
    out["_execution_id"] = str(execution_id).strip()
    return out
