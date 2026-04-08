from __future__ import annotations

from market_stream.provider_diagnostics import ProviderDiagnostics


def test_provider_diagnostics_protocol_and_transport() -> None:
    d = ProviderDiagnostics()
    assert d.as_health_fragment() == {"protocol": None, "transport": None}

    d.record_protocol_error("bitget_ws_error", "x" * 3000)
    d.record_transport_error("timeout")

    frag = d.as_health_fragment()
    assert frag["protocol"] is not None
    assert frag["protocol"]["source"] == "bitget_ws_error"
    assert len(frag["protocol"]["detail"]) == 2000
    assert frag["transport"] is not None
    assert "timeout" in (frag["transport"]["detail"] or "")
