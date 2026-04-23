from __future__ import annotations

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
