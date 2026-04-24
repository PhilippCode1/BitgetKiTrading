from __future__ import annotations

import json
from typing import Any

REPAIR_SYSTEM_APPEND_DE = (
    "EIN Reparatur-Versuch: exakt zulaessiges JSON nach Schema, kein Prosa-Wrapper. "
    "Fehler: {error}"
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
    schema_for_repair: str,
    max_invalid_chars: int = 12_000,
) -> str:
    """Ein Reparatur-Roundtrip: Fehler-JSON, Validator, Schema-Text."""
    broken = _trunc_json(invalid_json_object, max_invalid_chars)
    err = (error_text or "").strip() or "unbekannter Fehler"
    sch = (schema_for_repair or "").strip() or "(Schema-Text fehlt)"
    head = (
        f"Das JSON ist ungültig. Repariere es unter Einhaltung dieses Schemas: {sch}\n\n"
    )
    tail = (
        "Gib EIN repariertes JSON-Objekt (Schema-konform) aus. Kein Prosa davor/danach."
    )
    return (
        f"{original_prompt}\n\n---\n{head}Fehler: {err}\n\n"
        f"Fehlerhafte Ausgabe (zu reparieren):\n{broken}\n\n{tail}"
    )
