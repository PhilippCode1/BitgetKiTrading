from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from shared_py.service_auth import (
    assert_internal_service_auth,
    internal_service_auth_required,
)


def test_internal_service_auth_optional_outside_production() -> None:
    settings = SimpleNamespace(service_internal_api_key="", production=False)
    ctx = assert_internal_service_auth(settings, None)
    assert ctx.auth_method == "none"
    assert internal_service_auth_required(settings) is False


def test_internal_service_auth_production_without_key_is_misconfigured() -> None:
    settings = SimpleNamespace(service_internal_api_key="", production=True)
    assert internal_service_auth_required(settings) is True
    with pytest.raises(HTTPException) as excinfo:
        assert_internal_service_auth(settings, None)
    assert excinfo.value.status_code == 503
    assert excinfo.value.detail["code"] == "INTERNAL_AUTH_MISCONFIGURED"


def test_internal_service_auth_requires_matching_key_in_production() -> None:
    settings = SimpleNamespace(
        service_internal_api_key="internal-key-123456",
        production=True,
    )
    assert internal_service_auth_required(settings) is True
    with pytest.raises(HTTPException):
        assert_internal_service_auth(settings, "wrong")
    ctx = assert_internal_service_auth(settings, "internal-key-123456")
    assert ctx.auth_method == "internal_api_key"


def test_internal_service_auth_missing_or_empty_header_returns_401_when_key_set() -> None:
    """Gleiches Verhalten wie falscher Key: kein Header bzw. leerer Wert."""
    settings = SimpleNamespace(
        service_internal_api_key="internal-key-123456",
        production=False,
    )
    for presented in (None, "", "   "):
        with pytest.raises(HTTPException) as excinfo:
            assert_internal_service_auth(settings, presented)
        assert excinfo.value.status_code == 401
        assert excinfo.value.detail["code"] == "INTERNAL_AUTH_REQUIRED"
