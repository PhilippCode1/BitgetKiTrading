from __future__ import annotations

import json
from typing import Any

REPAIR_SYSTEM_APPEND_DE = (
    "Deine letzte Antwort war ungültiges JSON. Repariere diesen Fehler: {error}"
)


def _trunc_json(obj: Any, max_chars: int) -> str:
    raw = json.dumps(obj, ensure_ascii=False, default=str)
    if len(raw) <= max_chars:
        return raw
    return raw[:max_chars] + "\n… (gekürzt)"


def build_repair_user_prompt(
    *,
    original_prompt: str,
    invalid_json_object: Any,
    error_text: str,
    max_invalid_chars: int = 12_000,
) -> str:
    broken = _trunc_json(invalid_json_object, max_invalid_chars)
    err = (error_text or "").strip() or "unbekannter Fehler"
    return (
        f"{original_prompt}\n\n"
        f"---\n"
        f"Die folgende zuletzt erzeugte Ausgabe entsprach NICHT dem JSON-Schema (oder war kein valides JSON-Objekt dafür):\n"
        f"{broken}\n\n"
        f"Fehlermeldung(n) der Schema-Validierung: {err}\n\n"
        f"Gib ausschließlich EIN korrigiertes JSON-Objekt zurück, das exakt dem vorgegebenen "
        f"Structured-Output-Schema entspricht. Keine Prosa außerhalb des JSON."
    )
