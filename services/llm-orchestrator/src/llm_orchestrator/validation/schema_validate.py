from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator


class SchemaValidationError(ValueError):
    def __init__(self, message: str, errors: list[str]) -> None:
        super().__init__(message)
        self.errors = errors


def validate_against_schema(schema: dict[str, Any], instance: dict[str, Any]) -> None:
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errs = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if errs:
        messages = [e.message for e in errs[:12]]
        raise SchemaValidationError("JSON-Schema-Validierung fehlgeschlagen", messages)


def validator_for(schema: dict[str, Any]) -> Draft202012Validator:
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def format_schema_errors_for_prompt(errors: list[str], *, max_items: int = 12) -> str:
    """Für Repair-Prompt: kompakte, deterministische Fehlertexte."""
    n = max(1, int(max_items))
    parts = [str(x).strip() for x in (errors or []) if str(x).strip()][:n]
    return "; ".join(parts) if parts else "unbekannter Schemafehler"


def compact_schema_for_repair_prompt(
    schema: dict[str, Any], *, max_chars: int = 10_000
) -> str:
    """Gekapptes JSON-Schema-Textstück für den Reparatur-Prompt."""
    try:
        s = json.dumps(schema, ensure_ascii=False, default=str, indent=2)
    except (TypeError, ValueError, OverflowError) as exc:
        return f"(Schema nicht serialisierbar: {exc!s})"[:max_chars]
    if len(s) > max_chars:
        return (
            s[:max_chars] + "\n... (gekuerzt, volles Schema liegt im Dienst)"
        )
    return s
