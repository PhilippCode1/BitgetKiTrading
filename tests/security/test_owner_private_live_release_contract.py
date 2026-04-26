"""Contract: owner_private_live_release_payload_ok gleicht shared vectors (TS/Jest nutzt dieselbe Datei)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VECTORS = ROOT / "tests" / "fixtures" / "owner_private_live_release_vectors.json"


@pytest.fixture(scope="module")
def vectors() -> dict:
    data = json.loads(VECTORS.read_text(encoding="utf-8"))
    assert data.get("schema_version") == 1
    return data


def test_vectors_file_exists() -> None:
    assert VECTORS.is_file(), f"fehlt {VECTORS}"


def test_expect_true_cases(vectors: dict) -> None:
    from shared_py.readiness_scorecard import owner_private_live_release_payload_ok

    for case in vectors["expect_true"]:
        assert owner_private_live_release_payload_ok(case["payload"]) is True, case["id"]


def test_expect_false_cases(vectors: dict) -> None:
    from shared_py.readiness_scorecard import owner_private_live_release_payload_ok

    for case in vectors["expect_false"]:
        assert owner_private_live_release_payload_ok(case["payload"]) is False, case["id"]
