"""
Schutz vor Secret-Leaks in Logs und Audit-Payloads (heuristische Redaktion).

Nutzt ``execution_forensic.redact_nested_mapping`` fuer strukturierte Daten und
maskiert typische Token-Muster in Freitext.
"""

from __future__ import annotations

import re
from typing import Any

from shared_py.observability.execution_forensic import redact_nested_mapping

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
