"""
Step-Up-Verifikation fuer Self-Service Go-Live (TOTP oder statischer PIN).

Production: GO_LIVE_REQUIRE_STEP_UP=true + GO_LIVE_STEP_UP_TOTP_SECRET (empfohlen)
oder GO_LIVE_STEP_UP_PIN (nur Staging/Dev).
"""

from __future__ import annotations

import hashlib
import hmac
import struct
import time
from typing import Final

from fastapi import HTTPException

from config.gateway_settings import GatewaySettings

_STEP_UP_WINDOW_SEC: Final[int] = 30
_STEP_UP_DIGITS: Final[int] = 6
_STEP_UP_SKEW_WINDOWS: Final[int] = 1


def _totp_at(*, secret: str, counter: int, digits: int = _STEP_UP_DIGITS) -> str:
    msg = struct.pack(">Q", counter)
    digest = hmac.new(secret.encode("utf-8"), msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    truncated = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(truncated % (10**digits)).zfill(digits)


def verify_totp_code(code: str, secret: str, *, now: float | None = None) -> bool:
    normalized = code.strip()
    if not normalized.isdigit() or len(normalized) != _STEP_UP_DIGITS:
        return False
    ts = time.time() if now is None else now
    counter = int(ts) // _STEP_UP_WINDOW_SEC
    for delta in range(-_STEP_UP_SKEW_WINDOWS, _STEP_UP_SKEW_WINDOWS + 1):
        if hmac.compare_digest(normalized, _totp_at(secret=secret, counter=counter + delta)):
            return True
    return False


def go_live_step_up_required(settings: GatewaySettings) -> bool:
    return bool(settings.go_live_require_step_up)


def assert_go_live_step_up_verified(
    *,
    step_up_code: str | None,
    settings: GatewaySettings,
) -> None:
    if not go_live_step_up_required(settings):
        return

    code = (step_up_code or "").strip()
    if not code:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "STEP_UP_REQUIRED",
                "message": (
                    "Go-Live erfordert eine Step-Up-Bestaetigung "
                    "(Authenticator-Code oder PIN)."
                ),
            },
        )

    totp_secret = settings.go_live_step_up_totp_secret.strip()
    if totp_secret:
        if verify_totp_code(code, totp_secret):
            return
        raise HTTPException(
            status_code=403,
            detail={
                "error": "STEP_UP_INVALID",
                "message": "Step-Up-Code ungueltig oder abgelaufen.",
            },
        )

    pin = settings.go_live_step_up_pin.strip()
    if pin and hmac.compare_digest(code, pin):
        return

    raise HTTPException(
        status_code=503,
        detail={
            "error": "STEP_UP_MISCONFIGURED",
            "message": (
                "Step-Up ist aktiviert, aber weder GO_LIVE_STEP_UP_TOTP_SECRET "
                "noch GO_LIVE_STEP_UP_PIN ist konfiguriert."
            ),
        },
    )
