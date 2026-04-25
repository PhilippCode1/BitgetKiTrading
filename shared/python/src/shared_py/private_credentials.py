"""Private Bitget-Credential-Sicherheit (Single-Owner, fail-closed)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

CredentialStatus = Literal[
    "missing",
    "placeholder",
    "configured_redacted",
    "demo_only",
    "readonly_verified",
    "trading_permission_detected",
    "withdrawal_permission_detected",
    "invalid",
    "expired_or_revoked",
    "rotation_required",
    "live_write_blocked",
    "live_write_eligible_after_all_gates",
]


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def is_placeholder_value(value: str | None) -> bool:
    raw = (value or "").strip()
    if not raw:
        return True
    lower = raw.lower()
    markers = (
        "change_me",
        "changeme",
        "your_",
        "example",
        "<",
        "placeholder",
        "set_me",
        "dummy",
    )
    return any(m in lower for m in markers)


def mask_secret_hint(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return "missing"
    if is_placeholder_value(raw):
        return "placeholder"
    if len(raw) <= 6:
        return "***"
    return f"{raw[:2]}***{raw[-2:]}"


def redact_sensitive_text(text: str) -> str:
    out = re.sub(r"(?i)authorization\s*[:=]\s*bearer\s+\S+", "Authorization=***REDACTED***", text)
    out = re.sub(
        r"(?i)(api[_-]?key|secret|passphrase|password|token|authorization)\s*[:=]\s*\S+",
        r"\1=***REDACTED***",
        out,
    )
    out = re.sub(r"(?i)bearer\s+\S+", "Bearer ***REDACTED***", out)
    return out[:500]


@dataclass(frozen=True)
class PrivateCredentialSnapshot:
    key_hint: str
    secret_hint: str
    passphrase_hint: str
    status: CredentialStatus
    demo_enabled: bool
    read_only_checked: bool
    trading_permission_detected: bool
    withdrawal_permission_detected: bool | None
    live_write_blocked: bool
    live_write_eligible_after_all_gates: bool
    blockgruende_de: list[str]
    letzte_pruefung: str
    rotation_required: bool


def evaluate_private_credentials(
    *,
    bitget_api_key: str | None,
    bitget_api_secret: str | None,
    bitget_api_passphrase: str | None,
    bitget_demo_enabled: bool,
    execution_mode: str,
    live_trade_enable: bool,
    live_broker_enabled: bool,
    read_only_checked: bool,
    private_auth_ok: bool | None,
    permission_trading: bool | None,
    permission_withdrawal: bool | None,
    revoked_or_expired: bool,
    rotation_required: bool,
    all_live_gates_ok: bool,
) -> PrivateCredentialSnapshot:
    key_hint = mask_secret_hint(bitget_api_key)
    secret_hint = mask_secret_hint(bitget_api_secret)
    passphrase_hint = mask_secret_hint(bitget_api_passphrase)

    missing = key_hint == "missing" or secret_hint == "missing" or passphrase_hint == "missing"
    placeholder = key_hint == "placeholder" or secret_hint == "placeholder" or passphrase_hint == "placeholder"

    block: list[str] = []
    if missing:
        status: CredentialStatus = "missing"
        block.append("Bitget-Credentials fehlen.")
    elif placeholder:
        status = "placeholder"
        block.append("Placeholder-Credentials sind nicht gültig.")
    else:
        status = "configured_redacted"

    if bitget_demo_enabled:
        status = "demo_only"
        block.append("Demo-Credentials aktiv; kein echter Live-Betrieb.")
    if revoked_or_expired:
        status = "expired_or_revoked"
        block.append("Credential ist widerrufen oder abgelaufen.")
    if private_auth_ok is False:
        status = "invalid"
        block.append("Private Authentifizierung fehlgeschlagen.")
    if read_only_checked and status in {"configured_redacted", "demo_only"}:
        status = "readonly_verified"
    if permission_trading is True and status not in {"invalid", "expired_or_revoked"}:
        status = "trading_permission_detected"
    if permission_withdrawal is True:
        status = "withdrawal_permission_detected"
        block.append("Withdrawal-Permission erkannt (P0 No-Go).")
    if rotation_required and status not in {"missing", "placeholder"}:
        status = "rotation_required"
        block.append("Credential-Rotation erforderlich.")

    live_write_blocked = True
    if (
        status == "trading_permission_detected"
        and not bitget_demo_enabled
        and all_live_gates_ok
        and execution_mode == "live"
        and live_trade_enable
        and live_broker_enabled
    ):
        status = "live_write_eligible_after_all_gates"
        live_write_blocked = False
    else:
        if status not in {"missing", "placeholder", "invalid", "expired_or_revoked", "withdrawal_permission_detected", "rotation_required"}:
            status = "live_write_blocked"
        if permission_trading is not True:
            block.append("Trading-Permission nicht bestätigt.")
        if not all_live_gates_ok:
            block.append("Nicht alle Live-Gates sind grün.")
        if execution_mode != "live" or not live_trade_enable or not live_broker_enabled:
            block.append("Live-Write ist laut Runtime/Flags nicht aktiv.")

    return PrivateCredentialSnapshot(
        key_hint=key_hint,
        secret_hint=secret_hint,
        passphrase_hint=passphrase_hint,
        status=status,
        demo_enabled=bool(bitget_demo_enabled),
        read_only_checked=bool(read_only_checked),
        trading_permission_detected=bool(permission_trading),
        withdrawal_permission_detected=permission_withdrawal,
        live_write_blocked=live_write_blocked,
        live_write_eligible_after_all_gates=not live_write_blocked,
        blockgruende_de=block,
        letzte_pruefung=_now_iso(),
        rotation_required=bool(rotation_required),
    )


def snapshot_to_payload(snapshot: PrivateCredentialSnapshot) -> dict[str, Any]:
    return {
        "credential_status": snapshot.status,
        "credential_hints": {
            "api_key": snapshot.key_hint,
            "api_secret": snapshot.secret_hint,
            "passphrase": snapshot.passphrase_hint,
        },
        "demo_modus": snapshot.demo_enabled,
        "read_only_geprueft": snapshot.read_only_checked,
        "trading_permission_erkannt": snapshot.trading_permission_detected,
        "withdrawal_permission_erkannt": snapshot.withdrawal_permission_detected,
        "live_write_blocked": snapshot.live_write_blocked,
        "live_write_eligible_after_all_gates": snapshot.live_write_eligible_after_all_gates,
        "letzte_pruefung": snapshot.letzte_pruefung,
        "blockgruende_de": list(snapshot.blockgruende_de),
        "rotation_required": snapshot.rotation_required,
    }
