"""Tests fuer Go-Live Step-Up (TOTP/PIN)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

REPO_ROOT = Path(__file__).resolve().parents[3]
GATEWAY_SRC = REPO_ROOT / "services" / "api-gateway" / "src"
for p in (REPO_ROOT, GATEWAY_SRC):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from api_gateway.go_live_step_up import (  # noqa: E402
    _totp_at,
    assert_go_live_step_up_verified,
    verify_totp_code,
)


def test_verify_totp_accepts_current_window() -> None:
    secret = "test-secret-for-totp"
    counter = 1_700_000_000 // 30
    code = _totp_at(secret=secret, counter=counter)
    now = float(counter * 30)
    assert verify_totp_code(code, secret, now=now) is True


def test_assert_step_up_skipped_when_disabled() -> None:
    settings = MagicMock()
    settings.go_live_require_step_up = False
    assert_go_live_step_up_verified(step_up_code=None, settings=settings)


def test_assert_step_up_required_when_missing_code() -> None:
    settings = MagicMock()
    settings.go_live_require_step_up = True
    settings.go_live_step_up_totp_secret = "abcdefghijklmnop"
    settings.go_live_step_up_pin = ""
    with pytest.raises(HTTPException) as exc:
        assert_go_live_step_up_verified(step_up_code=None, settings=settings)
    assert exc.value.status_code == 403
    assert exc.value.detail["error"] == "STEP_UP_REQUIRED"


def test_assert_step_up_accepts_pin_in_dev() -> None:
    settings = MagicMock()
    settings.go_live_require_step_up = True
    settings.go_live_step_up_totp_secret = ""
    settings.go_live_step_up_pin = "123456"
    assert_go_live_step_up_verified(step_up_code="123456", settings=settings)
