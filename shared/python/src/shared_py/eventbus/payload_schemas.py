"""Event-Payload-Validierung (jsonschema) gegen shared/contracts/schemas."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import jsonschema
from jsonschema import Draft202012Validator


class SchemaValidationError(Exception):
    """Fehlgeschlagene JSON-Schema-Validierung einer Event-Payload-Instanz."""


def _monorepo_root() -> Path:
    for p in Path(__file__).resolve().parents:
        cat = p / "shared" / "contracts" / "catalog" / "payload_schema_map.json"
        if cat.is_file():
            return p
    raise FileNotFoundError("payload_schema_map.json (Monorepo-Root) nicht auffindbar.")


def _load_payload_schema_map() -> dict[str, str]:
    root = _monorepo_root()
    p = root / "shared" / "contracts" / "catalog" / "payload_schema_map.json"
    return json.loads(p.read_text(encoding="utf-8"))


PAYLOAD_SCHEMA_MAP: Final[dict[str, str]] = _load_payload_schema_map()
_SCHEMAS_DIR: Path = _monorepo_root() / "shared" / "contracts" / "schemas"

_validators: dict[str, Draft202012Validator] = {}


def _schema_path_for_event_type(event_type: str) -> Path:
    fn = PAYLOAD_SCHEMA_MAP[event_type]
    p = _SCHEMAS_DIR / fn
    if not p.is_file():
        msg = f"Fehlende Payload-Schema-Datei fuer {event_type!r}: {p}"
        raise FileNotFoundError(msg)
    return p


def _validator_for_event_type(event_type: str) -> Draft202012Validator:
    if event_type not in _validators:
        path = _schema_path_for_event_type(event_type)
        schema: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        _validators[event_type] = Draft202012Validator(schema)
    return _validators[event_type]


def ensure_payload_matches_schema(event_type: str, payload: object) -> None:
    if not isinstance(payload, dict):
        raise TypeError("payload muss ein object (dict) sein")
    v = _validator_for_event_type(event_type)
    try:
        v.validate(payload)
    except jsonschema.exceptions.ValidationError as e:
        raise SchemaValidationError(e.message) from e
