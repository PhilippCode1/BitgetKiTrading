from __future__ import annotations

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
                json={"demo_mode": {"live_trade_enable": False, "bitget_demo_enabled": True}},
            )
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handler)

    class _ClientFactory:
        def __call__(self, *args: object, **kwargs: object) -> httpx.Client:
            return original_client(transport=transport)

    monkeypatch.setattr(mod.httpx, "Client", _ClientFactory())
    rep = mod.run("http://localhost:3000", "http://localhost:8000")
    assert rep.result == "PASS"
