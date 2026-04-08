"""Deterministische Checks fuer KI-Strategie-Entwuerfe (keine LLM-Hoheit)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

FORBIDDEN_RESULT_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {
        "order_intent",
        "broker_command",
        "place_order",
        "api_call",
        "execution_payload",
        "live_order_spec",
    }
)

ALLOWED_LANE_HINTS: frozenset[str] = frozenset(
    {
        "none",
        "paper_sandbox",
        "shadow_observe",
        "live_requires_full_gates",
    }
)

PROMOTION_TARGETS: frozenset[str] = frozenset(
    {
        "paper_sandbox",
        "shadow_observe",
        "live_requires_full_gates",
    }
)


def normalize_proposal_payload(result: dict[str, Any]) -> dict[str, Any]:
    """Serverseitig: Ausfuehrungshoheit erzwingen (niemals Client vertrauen)."""
    out = dict(result)
    out["execution_authority"] = "none"
    return out


def run_deterministic_validation(result: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Struktur- und Policy-Checks ohne Modell."""
    errors: list[str] = []
    if result.get("execution_authority") != "none":
        errors.append("execution_authority_not_none")
    for k in FORBIDDEN_RESULT_TOP_LEVEL_KEYS:
        if k in result:
            errors.append(f"forbidden_key:{k}")
    lane = result.get("suggested_execution_lane_hint")
    if lane not in ALLOWED_LANE_HINTS:
        errors.append("invalid_lane_hint")
    disc = (result.get("promotion_disclaimer_de") or "").strip()
    if len(disc) < 12:
        errors.append("promotion_disclaimer_too_short")
    if result.get("schema_version") != "1.0":
        errors.append("schema_version_not_1_0")
    ok = not errors
    report: dict[str, Any] = {
        "ok": ok,
        "errors": errors,
        "checked_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    return ok, report


def assert_promotion_allowed(
    *,
    lifecycle_status: str,
    human_acknowledged: bool,
    promotion_target: str,
) -> None:
    from fastapi import HTTPException

    if not human_acknowledged:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "HUMAN_ACK_REQUIRED",
                "message": "Promotion requires explicit human_acknowledged=true.",
            },
        )
    if lifecycle_status != "validation_passed":
        raise HTTPException(
            status_code=422,
            detail={
                "code": "VALIDATION_REQUIRED",
                "message": "Run deterministic validation successfully before promotion request.",
            },
        )
    if promotion_target not in PROMOTION_TARGETS:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_PROMOTION_TARGET",
                "message": "promotion_target must be paper_sandbox, shadow_observe, or live_requires_full_gates.",
            },
        )
