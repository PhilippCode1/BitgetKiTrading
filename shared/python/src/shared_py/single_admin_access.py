"""Single-Admin Zugriffsschutz: Philipp als einziger Admin (private Main Console)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SingleAdminContext:
    admin_subject: str | None
    caller_subject: str | None
    production: bool
    legacy_admin_token_allowed: bool


def assert_single_admin_context(ctx: SingleAdminContext) -> None:
    if not ctx.admin_subject:
        raise ValueError("single_admin_subject_missing")
    if not ctx.caller_subject:
        raise ValueError("caller_subject_missing")
    if ctx.caller_subject != ctx.admin_subject:
        raise PermissionError("single_admin_subject_mismatch")
    if ctx.production and ctx.legacy_admin_token_allowed:
        raise PermissionError("legacy_admin_token_forbidden_in_production")


def is_server_only_secret_name(env_name: str) -> bool:
    n = env_name.strip().upper()
    return bool(
        re.search(r"(TOKEN|SECRET|PASS|PASSWORD|API_KEY|JWT|AUTHORIZATION|INTERNAL_API_KEY)", n)
        and not n.startswith("NEXT_PUBLIC_")
    )


def redact_auth_error(raw: str) -> str:
    text = str(raw)
    text = re.sub(r"(?i)(bearer)\s+[A-Za-z0-9._\-]+", r"\1 ***REDACTED***", text)
    text = re.sub(
        r"(?i)(token|secret|password|passphrase|api[_-]?key|authorization)\s*[:=]\s*\S+",
        r"\1=***REDACTED***",
        text,
    )
    return text[:240]


def private_console_access_blocks_sensitive_action(*, has_auth: bool, is_single_admin_ok: bool) -> bool:
    """Fail-closed: ohne Auth oder ohne validen Single-Admin-Kontext blockieren."""
    if not has_auth:
        return True
    if not is_single_admin_ok:
        return True
    return False


def contains_forbidden_public_secret_env(env_text: str) -> bool:
    for line in env_text.splitlines():
        l = line.strip()
        if not l or l.startswith("#") or "=" not in l:
            continue
        k, _ = l.split("=", 1)
        ku = k.strip().upper()
        if ku.startswith("NEXT_PUBLIC_") and re.search(r"(TOKEN|SECRET|PASS|API_KEY|JWT|AUTHORIZATION)", ku):
            return True
    return False


def requires_gateway_auth_message_de(text: str) -> bool:
    low = text.lower()
    return "dashboard_gateway_authorization fehlt" in low or "bearer-jwt" in low
