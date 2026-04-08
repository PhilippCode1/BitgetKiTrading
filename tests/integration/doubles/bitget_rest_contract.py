"""
Bitget Mix-REST: feste Beispielpayloads fuer Contract-Tests.

Spiegeln die oeffentliche JSON-Form; keine Produktions-Hosts.
"""

from __future__ import annotations

from typing import Any

# Erfolg: oeffentliche Zeit
SAMPLE_PUBLIC_TIME_OK: dict[str, Any] = {
    "code": "00000",
    "msg": "success",
    "requestTime": 1_700_000_000_000,
    "data": {"serverTime": "1700000000000"},
}

# Erfolg: Order platziert
SAMPLE_PLACE_ORDER_OK: dict[str, Any] = {
    "code": "00000",
    "msg": "success",
    "requestTime": 1_700_000_000_100,
    "data": {"clientOid": "bgai-test-crt-abcd", "orderId": "ex-12345"},
}

# Signatur / Auth (nicht retrybar im Live-Broker-Client)
SAMPLE_SIGNATURE_ERROR: dict[str, Any] = {
    "code": "40009",
    "msg": "sign signature error",
    "requestTime": 1_700_000_000_050,
    "data": {},
}

# Duplikat clientOid
SAMPLE_DUPLICATE_CLIENT_OID: dict[str, Any] = {
    "code": "01003",
    "msg": "Duplicate data exists",
    "requestTime": 1_700_000_000_060,
    "data": {},
}


def assert_bitget_envelope_shape(payload: dict[str, Any]) -> None:
    assert "code" in payload
    assert "msg" in payload
    assert "requestTime" in payload
