from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema import FormatChecker


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


@lru_cache(maxsize=1)
def drawing_schema_path() -> Path:
    return _repo_root() / "shared" / "contracts" / "schemas" / "drawing.schema.json"


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    path = drawing_schema_path()
    with path.open(encoding="utf-8") as fh:
        schema = json.load(fh)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_drawing_record(instance: dict[str, Any]) -> None:
    _validator().validate(instance)
