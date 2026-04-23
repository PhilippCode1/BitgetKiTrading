"""
Schutz vor Secret-Leaks in Logs und Audit-Payloads (heuristische Redaktion).

Nutzt ``execution_forensic.redact_nested_mapping`` fuer strukturierte Daten und
maskiert typische Token-Muster in Freitext.
"""

from __future__ import annotations

import re
from typing import Any

from shared_py.observability.execution_forensic import redact_nested_mapping

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
    (re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"), "[REDACTED_SLACK]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----", re.I), "[REDACTED_PEM]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_AWS_KEY_ID]"),
    (re.compile(r"https://api\.telegram\.org/bot[A-Za-z0-9:_\-]+/"), "https://api.telegram.org/bot[REDACTED]/"),
]


def scrub_plaintext(text: str, *, max_len: int = 120_000) -> str:
    s = text if len(text) <= max_len else text[: max_len - 20] + "…[truncated]"
    s = _REDACT_FULL_ASSIGN.sub(r"\1\g<k>=***", s)
    for pat, repl in _TEXT_PATTERNS:
        s = pat.sub(repl, s)
    return s


def scrub_audit_payload(obj: Any, *, max_depth: int = 6) -> Any:
    """Fuer audit-ledger / operator payloads: strukturierte Keys + grobe Text-Maskierung."""
    red = redact_nested_mapping(obj, max_depth=max_depth)
    if isinstance(red, dict):
        out: dict[str, Any] = {}
        for k, v in red.items():
            if isinstance(v, str):
                out[k] = scrub_plaintext(v, max_len=48_000)
            else:
                out[k] = v
        return out
    if isinstance(red, str):
        return scrub_plaintext(red)
    return red
