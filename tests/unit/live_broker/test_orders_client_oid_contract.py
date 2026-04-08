"""clientOid-Format und Idempotenz-Prefix-Vertrag (Bitget max. 50 Zeichen)."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_BROKER_SRC = REPO_ROOT / "services" / "live-broker" / "src"
for candidate in (REPO_ROOT, LIVE_BROKER_SRC):
    s = str(candidate)
    if s not in sys.path:
        sys.path.insert(0, s)

from live_broker.orders.service import client_oid_for_internal_order


def test_client_oid_format_is_stable_for_fixed_uuid() -> None:
    uid = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    oid = client_oid_for_internal_order("bgai-test", action_tag="crt", internal_order_id=uid)
    assert oid == "bgai-test-crt-aaaaaaaabbbbccccddddeeeeeeeeeeee"
    assert len(oid) <= 50


def test_client_oid_rejects_overlong_bitget_limit() -> None:
    uid = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    with pytest.raises(ValueError, match="50"):
        client_oid_for_internal_order(
            "very-long-prefix-that-makes-string-exceed-exchange-limit",
            action_tag="crt",
            internal_order_id=uid,
        )
