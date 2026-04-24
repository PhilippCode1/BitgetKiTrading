"""
Schutz vor Secret-Leaks in Logs und Audit-Payloads (heuristische Redaktion).

Nutzt ``redact_secrets_in_json`` fuer bekannte Secret-Keys in JSON-Strukturen
(Wert -> ``***``), entfernt LLM/PII-Keys, Text-Maske.
"""

from __future__ import annotations

import re
from typing import Any

# Nur PII / Roh-LLM-Keys entfernen — Secrets bleiben als "Key": "***" sichtbar
_PII_KEY_PARTS: tuple[str, ...] = (
    "email",
    "phone",
    "user_id",
    "username",
    "first_name",
    "last_name",
    "full_name",
    "chat_id",
)
_LLM_KEY_PARTS: tuple[str, ...] = (
    "prompt",
    "messages",
    "completion",
    "raw_llm",
)


def _is_pii_or_raw_llm_key(name: str) -> bool:
    s = str(name).lower()
    for p in _PII_KEY_PARTS:
        if p in s:
            return True
    for p in _LLM_KEY_PARTS:
        if p in s:
            return True
    if s.startswith(("prompt", "raw_llm")):
        return True
    return s.startswith("messages_") and "idempotency" not in s

# Bekannte ENV-/Log-Zeilen: vollstaendiger Wert -> *** (Bitget, JWT, BFF, …)
_REDACT_FULL_ASSIGN: re.Pattern[str] = re.compile(
    r"(?im)^(\s*)(?P<k>"
    r"BITGET_(?:API_SECRET|API_KEY|API_PASSPHRASE|SECRET_KEY)|"
    r"OPENAI_API_KEY|"
    r"STRIPE_(?:SECRET_KEY|WEBHOOK_SECRET|RESTRICTED_KEY)|"
    r"PAYMENT_STRIPE_SECRET_KEY|PAYMENT_STRIPE_WEBHOOK_SECRET|"
    r"INTERNAL_API_KEY|GATEWAY_JWT_SECRET|JWT_SECRET|SECRET_KEY|ENCRYPTION_KEY|"
    r"ADMIN_TOKEN|DASHBOARD_GATEWAY_AUTHORIZATION"
    r")\s*=\s*[^\r\n#]+"
)

# Heuristiken — kein Ersatz fuer dedizierte Secret-Scanner (Gitleaks etc.).
_TEXT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"sk-(?:live|proj|test)-[A-Za-z0-9_\-]{20,}"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"sk_[A-Za-z0-9]{20,}"), "[REDACTED_SK]"),
    (re.compile(r"sk-[a-zA-Z0-9]{48,}"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"), "[REDACTED_SLACK]"),
    (
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
            r"[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----",
            re.I,
        ),
        "[REDACTED_PEM]",
    ),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_AWS_KEY_ID]"),
    (
        re.compile(r"https://api\.telegram\.org/bot[A-Za-z0-9:_\-]+/"),
        "https://api.telegram.org/bot[REDACTED]/",
    ),
]


# JSON: Kredential-Substrings (kein nacktes "key" wegen monkey/hockey)
_K_STARS: tuple[str, ...] = (
    "password",
    "api_secret",
    "api_key",
    "apikey",
    "passphrase",
    "private_key",
    "authorization",
    "credential",
    "bearer",
    "x-internal",
    "x_internal",
    "x-gateway",
    "x_gateway",
    "openai_",
    "openai",
    "bitget_",
    "bitget",
    "webhook_secret",
    "signed",
    "signature",
    "gateway_jwt",
    "internal_api",
    "admin_token",
    "encryption_",
    "secret_key",
    "stripe_",
)

_LLM_PREFIXES: tuple[str, ...] = (
    "prompt",
    "messages",
    "completion",
    "raw_llm",
    "raw_llm_",
)


def _is_llm_key(name: str) -> bool:
    s = str(name).lower()
    if s in _LLM_PREFIXES or any(s == p or s.startswith(p) for p in _LLM_PREFIXES):
        return True
    return s.startswith("prompt_") or s.startswith("raw_llm") or s.startswith(
        "completion_"
    )


def _is_secretish_json_key_stars(name: str) -> bool:
    s = str(name).lower()
    for frag in _K_STARS:
        if frag in s:
            if "history" in s and "secret" in frag:
                return False
            return True
    if s.endswith(("_key", "_secret", "_passphrase", "_token")):
        if "turnkey" in s or "monkey" in s or "hockey" in s:
            return False
        return True
    if s in ("key", "pwd", "auth", "secret", "creds", "credentials"):
        return True
    return False


def redact_secrets_in_json(
    obj: Any,
    *,
    max_depth: int = 10,
) -> Any:
    """
    Ersetzt bekannte Secret-JSON-Werte durch ``***`` (Maskierung fuer Logs).

    Vorrang: verschachtelte Struktur zuerst maskieren, damit tiefere Schluessel
    nicht als Klartext in teilweisen Dumps erscheinen.
    """
    if max_depth < 0:
        return obj
    if obj is None:
        return None
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            sk = str(k)
            if _is_llm_key(sk):
                continue
            if _is_secretish_json_key_stars(sk):
                if isinstance(v, dict | list):
                    out[sk] = redact_secrets_in_json(v, max_depth=max_depth - 1)
                else:
                    out[sk] = "***"
            else:
                out[sk] = redact_secrets_in_json(v, max_depth=max_depth - 1)
        return out
    if isinstance(obj, list):
        return [redact_secrets_in_json(x, max_depth=max_depth - 1) for x in obj[:500]]
    if isinstance(obj, str):
        return scrub_plaintext(obj, max_len=80_000)
    return obj


def _drop_pii_llm_from_mapping(obj: Any, *, max_depth: int = 10) -> Any:
    if max_depth < 0:
        return obj
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            sk = str(k)
            if _is_pii_or_raw_llm_key(sk) or _is_llm_key(sk):
                continue
            out[sk] = _drop_pii_llm_from_mapping(v, max_depth=max_depth - 1)
        return out
    if isinstance(obj, list):
        return [
            _drop_pii_llm_from_mapping(x, max_depth=max_depth - 1) for x in obj[:200]
        ]
    return obj


def scrub_plaintext(text: str, *, max_len: int = 120_000) -> str:
    s = text if len(text) <= max_len else text[: max_len - 20] + "…[truncated]"
    s = _REDACT_FULL_ASSIGN.sub(r"\1\g<k>=***", s)
    for pat, repl in _TEXT_PATTERNS:
        s = pat.sub(repl, s)
    return s


def scrub_audit_payload(obj: Any, *, max_depth: int = 6) -> Any:
    """
    Fuer audit-ledger / operator payloads: Secret-Keys in JSON -> ``***``,
    PII- und LLM-Roh-Keys entfernen, restliche String-Werte textmaskieren.
    """
    star = redact_secrets_in_json(obj, max_depth=max_depth)
    red = _drop_pii_llm_from_mapping(star, max_depth=max_depth)
    if isinstance(red, dict):
        out2: dict[str, Any] = {}
        for k, v in red.items():
            if isinstance(v, str):
                out2[k] = scrub_plaintext(v, max_len=48_000)
            else:
                out2[k] = v
        return out2
    if isinstance(red, str):
        return scrub_plaintext(red)
    return red
