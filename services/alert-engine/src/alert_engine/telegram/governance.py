"""RBAC und Manual-Action-Token (rein funktional, testbar)."""

from __future__ import annotations

import hashlib
import secrets


def operator_user_allowed(*, user_id: int | None, allowed_ids: set[int]) -> tuple[bool, str]:
    if not allowed_ids:
        return True, "rbac_disabled_allow_all"
    if user_id is None:
        return False, "rejected_rbac_telegram_user_unknown"
    if int(user_id) not in allowed_ids:
        return False, "rejected_rbac_user_not_in_allowlist"
    return True, "allowed_operator_user"


def manual_confirm_token_verify(
    *,
    configured_token: str,
    parts: list[str],
) -> tuple[bool, str | None]:
    """
    Zweiter Faktor neben Einmalcode: wenn configured_token leer, ok.
    Sonst parts[2] muss exakt matchen; Rueckgabe (ok, fingerprint_hex32).
    """
    tok = configured_token.strip()
    if not tok:
        return True, None
    if len(parts) < 3:
        return False, None
    presented = parts[2].strip()
    if not secrets.compare_digest(presented, tok):
        return False, None
    fp = hashlib.sha256(presented.encode("utf-8")).hexdigest()[:32]
    return True, fp
