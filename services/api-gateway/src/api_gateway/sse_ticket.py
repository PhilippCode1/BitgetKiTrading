"""Kurzlebige, signierte SSE-Session-Cookies (ohne JWT im Browser-LocalStorage)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

_SEP = "|"


def resolve_sse_signing_secret(settings: Any) -> str | None:
    raw = str(getattr(settings, "gateway_sse_signing_secret", "") or "").strip()
    if raw:
        return raw
    jwt_s = str(getattr(settings, "gateway_jwt_secret", "") or "").strip()
    if jwt_s:
        return jwt_s
    ik = str(getattr(settings, "gateway_internal_api_key", "") or "").strip()
    return ik or None


def build_sse_ticket(*, secret: str, sub: str, ttl_sec: int) -> str:
    exp = int(time.time()) + int(ttl_sec)
    sub_s = (sub or "anon")[:128]
    body = f"1{_SEP}{exp}{_SEP}{sub_s}"
    sig = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    payload = {"v": 1, "exp": exp, "sub": sub_s, "sig": sig}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def verify_sse_ticket(token: str, *, secret: str) -> bool:
    try:
        pad = "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(token + pad)
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, OSError):
        return False
    if not isinstance(payload, dict):
        return False
    if int(payload.get("v") or 0) != 1:
        return False
    exp = int(payload.get("exp") or 0)
    if exp <= int(time.time()):
        return False
    sub_s = str(payload.get("sub") or "")[:128]
    sig = str(payload.get("sig") or "")
    body = f"1{_SEP}{exp}{_SEP}{sub_s}"
    expected = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)
