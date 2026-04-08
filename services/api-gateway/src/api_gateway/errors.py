"""Einheitliche JSON-Fehlerkoerper fuer Produktion (ohne interne Details)."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException


def http_error_envelope(*, status_code: int, code: str, message: str) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "status": status_code,
            "layer": "api-gateway",
        }
    }


def map_status_to_code(status_code: int) -> str:
    return {
        400: "BAD_REQUEST",
        401: "AUTHENTICATION_REQUIRED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        413: "PAYLOAD_TOO_LARGE",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMIT_EXCEEDED",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
    }.get(status_code, "HTTP_ERROR")


def public_message_for_status(status_code: int) -> str:
    return {
        400: "The request was invalid.",
        401: "Authentication required.",
        403: "Access denied.",
        404: "Resource not found.",
        413: "Request payload too large.",
        422: "Validation failed.",
        429: "Too many requests.",
        502: "Upstream service error.",
        503: "Service temporarily unavailable.",
    }.get(status_code, "Request could not be completed.")


def shape_http_exception(*, production: bool, exc: HTTPException) -> dict[str, Any]:
    if not production:
        d: Any = exc.detail
        return {"detail": d}
    code = map_status_to_code(exc.status_code)
    if isinstance(exc.detail, dict):
        inner = exc.detail.get("code")
        msg = exc.detail.get("message")
        if isinstance(inner, str):
            code = inner
        if isinstance(msg, str):
            return http_error_envelope(
                status_code=exc.status_code,
                code=code,
                message=msg,
            )
    return http_error_envelope(
        status_code=exc.status_code,
        code=code,
        message=public_message_for_status(exc.status_code),
    )
