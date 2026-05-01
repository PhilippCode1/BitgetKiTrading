from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

import scripts.demo_stack_healthcheck as mod


def test_demo_stack_healthcheck_parsebar(monkeypatch: pytest.MonkeyPatch) -> None:
    original_client = mod.httpx.Client

    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if path.endswith("/api/demo/readiness"):
            return httpx.Response(200, json={"result": "PASS"})
        if path.endswith("/api/demo/status"):
            return httpx.Response(
                200,
                json={
                    "demo_mode": {
                        "live_trade_enable": False,
                        "bitget_demo_enabled": True,
                    }
                },
            )
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handler)

    class _ClientFactory:
        def __call__(self, *args: object, **kwargs: object) -> httpx.Client:
            return original_client(transport=transport)

    monkeypatch.setattr(mod.httpx, "Client", _ClientFactory())
    rep = mod.run("http://localhost:3000", "http://localhost:8000")
    assert rep.result == "PASS"


def test_healthcheck_timeout_does_not_crash_and_sets_blockers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_client = mod.httpx.Client

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/":
            raise httpx.ReadTimeout("timeout")
        return httpx.Response(
            200,
            json={
                "result": "PASS",
                "demo_mode": {"live_trade_enable": False, "bitget_demo_enabled": True},
            },
        )

    transport = httpx.MockTransport(handler)

    class _ClientFactory:
        def __call__(self, *args: object, **kwargs: object) -> httpx.Client:
            return original_client(transport=transport)

    monkeypatch.setattr(mod.httpx, "Client", _ClientFactory())
    rep = mod.run("http://localhost:3000", "http://localhost:8000")
    assert rep.result == "FAIL"
    assert "dashboard_timeout" in rep.blockers


def test_healthcheck_writes_json_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[name-defined]
    original_client = mod.httpx.Client

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/health"):
            raise httpx.ReadTimeout("timeout")
        return httpx.Response(
            200,
            json={
                "result": "PASS",
                "demo_mode": {"live_trade_enable": False, "bitget_demo_enabled": True},
            },
        )

    transport = httpx.MockTransport(handler)

    class _ClientFactory:
        def __call__(self, *args: object, **kwargs: object) -> httpx.Client:
            return original_client(transport=transport)

    monkeypatch.setattr(mod.httpx, "Client", _ClientFactory())
    out_json = tmp_path / "health.json"
    rc = mod.main(
        [
            "--dashboard-url",
            "http://localhost:3000",
            "--base-url",
            "http://localhost:8000",
            "--output-json",
            str(out_json),
        ]
    )
    assert rc == 1
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["result"] == "FAIL"
