from __future__ import annotations

import httpx
import pytest

import scripts.demo_stress_smoke as mod


def test_stress_smoke_default_kein_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    original_client = mod.httpx.Client
    called_submit = {"value": False}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/api/demo/order/submit"):
            called_submit["value"] = True
        return httpx.Response(200, json={"ok": True, "allowed": False})

    transport = httpx.MockTransport(handler)

    class _ClientFactory:
        def __call__(self, *args: object, **kwargs: object) -> httpx.Client:
            return original_client(transport=transport)

    monkeypatch.setattr(mod.httpx, "Client", _ClientFactory())
    rep = mod.run(
        base_url="http://localhost:8000",
        dashboard_url="http://localhost:3000",
        duration_sec=1,
        include_preview=False,
        include_submit=False,
    )
    assert rep.result == "PASS"
    assert called_submit["value"] is False
