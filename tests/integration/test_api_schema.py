"""
API-Antworten gegen JSON-Schema pruefen (optional: laufender api-gateway).
Keine Secrets in Logs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest
from jsonschema import Draft202012Validator

REPO = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO / "infra" / "tests" / "schemas"


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def test_signals_recent_fixture_validates() -> None:
    from jsonschema import Draft202012Validator

    schema = _load_schema("signals_recent_response.schema.json")
    data = json.loads(
        (REPO / "tests" / "fixtures" / "signals_fixture.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(data)


@pytest.mark.integration
def test_live_signals_recent_matches_schema() -> None:
    base = os.getenv("API_GATEWAY_URL", "").strip()
    if not base:
        pytest.skip("API_GATEWAY_URL nicht gesetzt")

    schema = _load_schema("signals_recent_response.schema.json")
    url = base.rstrip("/") + "/v1/signals/recent"
    r = httpx.get(url, params={"limit": 1}, timeout=10.0)
    r.raise_for_status()
    data = r.json()
    Draft202012Validator(schema).validate(data)
