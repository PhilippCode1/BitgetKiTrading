from __future__ import annotations

import io
import json
from unittest.mock import patch

import urllib.error

from shared_py.observability.health import check_http_ready_json


def test_check_http_ready_json_http_error_body_ready_false() -> None:
    payload = {
        "ready": False,
        "checks": {"postgres": {"ok": False, "detail": "down"}},
    }
    body = json.dumps(payload).encode("utf-8")
    err = urllib.error.HTTPError(
        "http://example/ready",
        503,
        "Service Unavailable",
        hdrs={},
        fp=io.BytesIO(body),
    )

    def fake_urlopen(*_a, **_kw):  # type: ignore[no-untyped-def]
        raise err

    with patch("urllib.request.urlopen", fake_urlopen):
        ok, detail = check_http_ready_json("http://example/ready", timeout_sec=1.0)
    assert ok is False
    assert "503" in detail


def test_check_http_ready_json_http_error_body_ready_true_nested_bad() -> None:
    payload = {
        "ready": True,
        "checks": {"x": {"ok": False, "detail": "nope"}},
    }
    body = json.dumps(payload).encode("utf-8")
    err = urllib.error.HTTPError(
        "http://example/ready",
        503,
        "Service Unavailable",
        hdrs={},
        fp=io.BytesIO(body),
    )

    def fake_urlopen(*_a, **_kw):  # type: ignore[no-untyped-def]
        raise err

    with patch("urllib.request.urlopen", fake_urlopen):
        ok, detail = check_http_ready_json("http://example/ready", timeout_sec=1.0)
    assert ok is False
    assert "503" in detail
