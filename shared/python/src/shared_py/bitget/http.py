from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlencode

from .config import BitgetSettings


def build_rest_headers(
    settings: BitgetSettings,
    extra_headers: Mapping[str, str] | None = None,
) -> dict[str, str]:
    headers: dict[str, str] = dict(extra_headers or {})
    headers.update(settings.demo_headers())
    return headers


def build_query_string(
    params: Mapping[str, Any] | Sequence[tuple[str, Any]] | None,
) -> str:
    if not params:
        return ""
    items = params.items() if isinstance(params, Mapping) else params
    encoded: list[tuple[str, str]] = []
    for key, value in items:
        if value is None:
            continue
        if isinstance(value, bool):
            normalized = "true" if value else "false"
        else:
            normalized = str(value)
        encoded.append((str(key), normalized))
    return urlencode(encoded, doseq=True)


def canonical_json_body(body: Mapping[str, Any] | None) -> str:
    if not body:
        return ""
    return json.dumps(body, separators=(",", ":"), ensure_ascii=False)


def build_signature_payload(
    *,
    timestamp_ms: int,
    method: str,
    request_path: str,
    query_string: str = "",
    body: str = "",
) -> str:
    clean_query = query_string[1:] if query_string.startswith("?") else query_string
    payload = f"{timestamp_ms}{method.upper()}{request_path}"
    if clean_query:
        payload = f"{payload}?{clean_query}"
    return f"{payload}{body}"


def sign_hmac_sha256_base64(secret_key: str, payload: str) -> str:
    digest = hmac.new(
        secret_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def build_private_rest_headers(
    settings: BitgetSettings,
    *,
    timestamp_ms: int,
    method: str,
    request_path: str,
    query_string: str = "",
    body: str = "",
    extra_headers: Mapping[str, str] | None = None,
) -> dict[str, str]:
    if not settings.effective_api_key:
        raise ValueError("Bitget API key fehlt fuer private REST-Anfrage")
    if not settings.effective_api_secret:
        raise ValueError("Bitget API secret fehlt fuer private REST-Anfrage")
    if not settings.effective_api_passphrase:
        raise ValueError("Bitget API passphrase fehlt fuer private REST-Anfrage")
    payload = build_signature_payload(
        timestamp_ms=timestamp_ms,
        method=method,
        request_path=request_path,
        query_string=query_string,
        body=body,
    )
    headers = build_rest_headers(
        settings,
        {
            "ACCESS-KEY": settings.effective_api_key,
            "ACCESS-SIGN": sign_hmac_sha256_base64(
                settings.effective_api_secret,
                payload,
            ),
            "ACCESS-TIMESTAMP": str(timestamp_ms),
            "ACCESS-PASSPHRASE": settings.effective_api_passphrase,
            "Content-Type": "application/json",
            "locale": settings.bitget_rest_locale,
        },
    )
    headers.update(dict(extra_headers or {}))
    return headers
