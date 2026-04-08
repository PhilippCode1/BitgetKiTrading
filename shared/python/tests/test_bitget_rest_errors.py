from __future__ import annotations

from shared_py.bitget.errors import classify_bitget_private_rest_failure


def test_classify_symbol_unknown_as_validation() -> None:
    c = classify_bitget_private_rest_failure(
        http_status=200,
        payload={"code": "40404", "msg": "symbol not exist"},
        fallback_message="x",
    )
    assert c.classification == "validation"
    assert c.retryable is False


def test_classify_http_401_empty_body_as_auth() -> None:
    c = classify_bitget_private_rest_failure(
        http_status=401,
        payload={},
        fallback_message="x",
    )
    assert c.classification == "auth"


def test_classify_http_403_empty_body_as_permission() -> None:
    c = classify_bitget_private_rest_failure(
        http_status=403,
        payload={},
        fallback_message="x",
    )
    assert c.classification == "permission"
