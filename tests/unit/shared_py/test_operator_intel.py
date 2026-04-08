from __future__ import annotations

from shared_py.operator_intel import (
    build_operator_intel_envelope_payload,
    format_operator_intel_message,
    redact_operator_intel_payload,
)


def test_redact_strips_secret_like_keys() -> None:
    raw = {
        "symbol": "BTCUSDT",
        "api_key": "sekret",
        "chat_id": 123,
        "nested": {"system_prompt": "do evil", "ok": 1, "user_id": 456},
    }
    out = redact_operator_intel_payload(raw)
    assert out["api_key"] == "[redacted]"
    assert out["chat_id"] == "[redacted]"
    assert out["nested"]["system_prompt"] == "[redacted]"
    assert out["nested"]["user_id"] == "[redacted]"
    assert out["nested"]["ok"] == 1


def test_format_operator_intel_message_includes_context_lines() -> None:
    pl = build_operator_intel_envelope_payload(
        intel_kind="no_trade",
        symbol="ETHUSDT",
        correlation_id="sig:abc",
        market_family="futures",
        playbook_id="pb_trend",
        specialist_route="router:family_futures",
        regime="stress",
        risk_summary="decision_state=blocked",
        stop_exit_family="scale_out,runner",
        leverage_band="allowed=5 cap=7",
        reasons=["spread_wide", "stop_budget_fragile"],
        outcome="no_trade",
        signal_id="abc",
    )
    text = format_operator_intel_message(pl)
    assert "[NO-TRADE]" in text
    assert "ref: sig:abc" in text
    assert "Instrument: ETHUSDT" in text
    assert "Familie: futures" in text
    assert "Hebel-Band: allowed=5 cap=7" in text
    assert "spread_wide" in text


def test_build_payload_omits_empty_optional_fields() -> None:
    pl = build_operator_intel_envelope_payload(
        intel_kind="execution_update",
        symbol="BTCUSDT",
        execution_id="ex-1",
    )
    assert "market_family" not in pl
    assert pl["intel_format_version"] == 1
    assert "text" in pl and pl["text"]
