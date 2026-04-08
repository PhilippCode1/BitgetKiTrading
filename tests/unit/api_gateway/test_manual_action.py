from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
API_GATEWAY_SRC = REPO_ROOT / "services" / "api-gateway" / "src"
for candidate in (REPO_ROOT, API_GATEWAY_SRC):
    s = str(candidate)
    if s not in sys.path:
        sys.path.insert(0, s)

from api_gateway.manual_action import (
    canonical_payload_fingerprint,
    fingerprint_payload_for_operator_release,
)


def test_canonical_payload_fingerprint_order_sensitive() -> None:
    a = canonical_payload_fingerprint({"z": 1, "a": 2})
    b = canonical_payload_fingerprint({"a": 2, "z": 1})
    assert a == b


def test_operator_release_fingerprint_binds_execution_id() -> None:
    p1 = fingerprint_payload_for_operator_release(
        "00000000-0000-0000-0000-0000000000aa",
        {"audit": {"x": 1}},
    )
    p2 = fingerprint_payload_for_operator_release(
        "00000000-0000-0000-0000-0000000000bb",
        {"audit": {"x": 1}},
    )
    assert canonical_payload_fingerprint(p1) != canonical_payload_fingerprint(p2)


def test_fingerprint_mismatch_on_extra_body_key() -> None:
    base = fingerprint_payload_for_operator_release("00000000-0000-0000-0000-0000000000cc", {})
    with_extra = fingerprint_payload_for_operator_release(
        "00000000-0000-0000-0000-0000000000cc",
        {"extra": 1},
    )
    assert canonical_payload_fingerprint(base) != canonical_payload_fingerprint(with_extra)
