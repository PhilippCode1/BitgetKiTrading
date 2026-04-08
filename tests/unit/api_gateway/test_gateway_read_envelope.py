from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
API_GATEWAY_SRC = REPO_ROOT / "services" / "api-gateway" / "src"
for candidate in (REPO_ROOT, API_GATEWAY_SRC):
    s = str(candidate)
    if s not in sys.path:
        sys.path.insert(0, s)

from api_gateway.errors import http_error_envelope
from api_gateway.gateway_read_envelope import (
    READ_ENVELOPE_CONTRACT_VERSION,
    merge_read_envelope,
)


def test_merge_read_envelope_sets_contract_version() -> None:
    body = merge_read_envelope(
        {"items": []},
        status="ok",
        message=None,
        empty_state=True,
        degradation_reason="no_rows",
        next_step=None,
    )
    assert body["read_envelope_contract_version"] == READ_ENVELOPE_CONTRACT_VERSION
    assert body["status"] == "ok"
    assert body["empty_state"] is True


def test_http_error_envelope_includes_layer() -> None:
    body = http_error_envelope(
        status_code=401,
        code="AUTHENTICATION_REQUIRED",
        message="Authentication required.",
    )
    assert body["error"]["layer"] == "api-gateway"
    assert body["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_merge_read_envelope_degraded_shape() -> None:
    body = merge_read_envelope(
        {},
        status="degraded",
        message="DB down",
        empty_state=True,
        degradation_reason="database_error",
        next_step="Postgres pruefen",
    )
    assert body["read_envelope_contract_version"] == READ_ENVELOPE_CONTRACT_VERSION
    assert body["degradation_reason"] == "database_error"
