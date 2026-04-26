"""Struktur-Contract fuer config/required_secrets_matrix.json (keine Secrets, nur Schema)."""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MATRIX_PATH = REPO / "config" / "required_secrets_matrix.json"

_PHASES = ("local", "staging", "production")
_ALLOWED_LEVEL = frozenset({"required", "optional", "forbidden", "n/a"})


def _load() -> dict:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def test_matrix_file_exists() -> None:
    assert MATRIX_PATH.is_file(), f"fehlt: {MATRIX_PATH}"


def test_matrix_top_level_and_entries() -> None:
    data = _load()
    assert data.get("version") == 2
    assert isinstance(data.get("description"), str) and data["description"]
    assert isinstance(data.get("services_all"), list) and data["services_all"]
    entries = data.get("entries")
    assert isinstance(entries, list) and len(entries) >= 1
    for i, row in enumerate(entries):
        assert isinstance(row, dict), f"entry[{i}] muss object sein"
        env = row.get("env")
        assert isinstance(env, str) and env, f"entry[{i}].env"
        services = row.get("services")
        assert services == "*" or isinstance(services, list), f"entry[{i}].services"
        for ph in _PHASES:
            v = row.get(ph)
            assert v in _ALLOWED_LEVEL, (
                f"entry[{i}] {ph}={v!r} nicht in {sorted(_ALLOWED_LEVEL)}"
            )
