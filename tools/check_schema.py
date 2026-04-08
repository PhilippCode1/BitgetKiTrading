#!/usr/bin/env python3
"""
Validiert JSON-Daten gegen ein JSON-Schema (jsonschema, Draft 2020-12).
Relativ zum Repo-Root ausfuehren.

Beispiel:
  python tools/check_schema.py \\
    --schema infra/tests/schemas/signals_recent_response.schema.json \\
    --json_file tests/fixtures/signals_fixture.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    p = argparse.ArgumentParser(description="JSON Schema Validation")
    p.add_argument("--schema", required=True, help="Pfad zur Schema-JSON")
    p.add_argument("--json_file", default=None, help="Zu pruefende JSON-Datei")
    p.add_argument("--stdin", action="store_true", help="JSON von stdin lesen")
    args = p.parse_args()

    schema_path = Path(args.schema)
    if not schema_path.is_file():
        print(f"Schema nicht gefunden: {schema_path}", file=sys.stderr)
        return 2

    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        print("Bitte installieren: pip install jsonschema", file=sys.stderr)
        return 2

    schema = _load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    if args.stdin:
        instance = json.loads(sys.stdin.read())
    elif args.json_file:
        jpath = Path(args.json_file)
        if not jpath.is_file():
            print(f"JSON-Datei nicht gefunden: {jpath}", file=sys.stderr)
            return 2
        instance = _load_json(jpath)
    else:
        print("Entweder --json_file oder --stdin angeben.", file=sys.stderr)
        return 2

    errors = sorted(validator.iter_errors(instance), key=lambda e: e.path)
    if errors:
        for err in errors:
            print(f"{list(err.path)}: {err.message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
