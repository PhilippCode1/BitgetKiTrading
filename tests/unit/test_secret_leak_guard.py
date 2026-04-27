import numpy as np
import pytest

from shared_py.observability.secret_leak_guard import (
    scrub_audit_payload,
    scrub_plaintext,
)
from shared_py.rust_core_bridge import assert_float64_c_contiguous


def test_scrub_plaintext_openai_style() -> None:
    s = "token=" + "sk-proj-" + "abcdefghijklmnopqrstuvwxyz0123456789"
    out = scrub_plaintext(s)
    assert "sk-proj-" not in out
    assert "[REDACTED" in out


def test_scrub_plaintext_bitget_env_line() -> None:
    s = "BITGET_API_SECRET=not_leaking_this_value_12345"
    out = scrub_plaintext(s)
    assert "not_leaking" not in out
    assert "BITGET_API_SECRET=***" in out


def test_scrub_audit_payload_masks_secret_keys() -> None:
    d = scrub_audit_payload({"api_key": "x", "nested": {"password": "y", "ok": 1}}, max_depth=4)
    assert isinstance(d, dict)
    assert d.get("api_key") == "***"
    assert d.get("nested", {}).get("password") == "***"
    assert d.get("nested", {}).get("ok") == 1


def test_assert_float64_c_contiguous_ok() -> None:
    a = np.ascontiguousarray(np.array([1.0, 2.0], dtype=np.float64))
    assert_float64_c_contiguous("t", a)


def test_assert_float64_c_contiguous_rejects_wrong_dtype() -> None:
    a = np.array([1.0, 2.0], dtype=np.float32)
    with pytest.raises(ValueError, match="float64"):
        assert_float64_c_contiguous("t", a)
