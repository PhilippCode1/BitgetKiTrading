from __future__ import annotations

from shared_py.audit_contracts import (
    build_german_forensic_summary,
    build_private_audit_event,
    redact_secrets,
    validate_private_audit_event,
)
from shared_py.replay_summary import build_replay_summary


def _valid_event(**overrides: object) -> dict[str, object]:
    event: dict[str, object] = {
        "event_id": "evt-1",
        "event_type": "private_decision_audit",
        "timestamp": "2026-04-25T15:00:00Z",
        "git_sha": "abc123",
        "service": "signal-engine",
        "asset_symbol": "ETHUSDT",
        "market_family": "futures",
        "product_type": "USDT-FUTURES",
        "margin_coin": "USDT",
        "decision_type": "risk_decision",
        "decision": "do_not_trade",
        "reason_codes": ["data_quality_not_green"],
        "reason_text_de": "Datenqualitaet ist nicht gruen; Live bleibt blockiert.",
        "risk_tier": "RISK_TIER_1_MAJOR_LIQUID",
        "liquidity_tier": "green",
        "data_quality_status": "data_stale",
        "exchange_truth_status": "healthy",
        "reconcile_status": "clean",
        "operator_context": "philipp",
        "trace_id": "trace-1",
        "correlation_id": "corr-1",
        "no_secrets_confirmed": True,
    }
    event.update(overrides)
    return event


def test_audit_event_without_event_type_invalid() -> None:
    event = _valid_event()
    event.pop("event_type")
    result = validate_private_audit_event(event)
    assert result.valid is False
    assert "missing_event_type" in result.errors


def test_audit_event_without_timestamp_invalid() -> None:
    result = validate_private_audit_event(_valid_event(timestamp=""))
    assert result.valid is False
    assert "missing_timestamp" in result.errors


def test_live_decision_without_asset_symbol_invalid() -> None:
    result = validate_private_audit_event(_valid_event(decision_type="live_decision", asset_symbol=""))
    assert result.valid is False
    assert "missing_asset_symbol" in result.errors
    assert "live_decision_missing_asset_symbol" in result.errors


def test_order_decision_without_exchange_truth_invalid() -> None:
    result = validate_private_audit_event(
        _valid_event(decision_type="order_decision", exchange_truth_status="")
    )
    assert result.valid is False
    assert "missing_exchange_truth_status" in result.errors
    assert "order_decision_missing_exchange_truth_status" in result.errors


def test_risk_decision_without_reason_codes_invalid() -> None:
    result = validate_private_audit_event(_valid_event(reason_codes=[]))
    assert result.valid is False
    assert "missing_reason_codes" in result.errors
    assert "risk_decision_missing_reason_codes" in result.errors


def test_secrets_are_redacted() -> None:
    payload = {
        "Authorization": "Bearer secret",
        "nested": {"api_key": "real-key", "ok": "value"},
    }
    out = redact_secrets(payload)
    assert out["Authorization"] == "[REDACTED]"
    assert out["nested"]["api_key"] == "[REDACTED]"
    assert out["nested"]["ok"] == "value"


def test_replay_summary_detects_missing_signal_risk_exchange_steps() -> None:
    summary = build_replay_summary({"steps": {"signal": {"event_id": "s1"}}})
    assert summary["replay_sufficient"] is False
    assert "risk" in summary["missing_steps"]
    assert "exchange" in summary["missing_steps"]


def test_complete_fixture_is_replay_sufficient() -> None:
    summary = build_replay_summary(
        {
            "steps": {
                "signal": {"event_id": "s1"},
                "risk": {"reason_codes": ["ok"]},
                "exchange": {"exchange_truth_status": "healthy"},
            }
        }
    )
    assert summary["replay_sufficient"] is True


def test_german_reason_text_required_and_summary_present() -> None:
    result = validate_private_audit_event(_valid_event(reason_text_de=""))
    assert result.valid is False
    assert "missing_reason_text_de" in result.errors
    assert "reason_text_de_missing" in result.errors

    event = _valid_event()
    built = build_private_audit_event(event)
    assert built["validation"]["valid"] is True
    assert "Entscheidung fuer ETHUSDT" in build_german_forensic_summary(event)
