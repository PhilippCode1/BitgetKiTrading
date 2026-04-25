from __future__ import annotations

from pathlib import Path

from shared_py.health_map import (
    HealthMapComponent,
    assert_no_commercial_terms,
    component_payload,
    evaluate_health_map,
    redact_health_details,
)


def _base(name: str, *, status: str = "ok", freshness: str = "fresh", block: bool = False) -> HealthMapComponent:
    return HealthMapComponent(
        name=name,
        status=status,  # type: ignore[arg-type]
        freshness_status=freshness,  # type: ignore[arg-type]
        live_auswirkung_de="ok",
        blockiert_live=block,
        letzter_erfolg_ts="2026-01-01T00:00:00Z",
        letzter_fehler_ts=None,
        fehlergrund_de="",
        nächster_schritt_de="weiter",
    )


def test_all_ok_components_result_ok_if_no_live_blocker() -> None:
    comps = [_base("API-Gateway"), _base("Live-Broker"), _base("Reconcile"), _base("Postgres"), _base("Redis/Eventbus")]
    out = evaluate_health_map(comps)
    assert out["gesamtstatus"] == "ok"
    assert out["live_blockiert"] is False


def test_live_broker_unknown_blocks_live() -> None:
    comps = [_base("Live-Broker", status="unknown")]
    out = evaluate_health_map(comps)
    assert out["live_blockiert"] is True


def test_reconcile_stale_blocks_live() -> None:
    comps = [_base("Reconcile", status="ok", freshness="stale")]
    out = evaluate_health_map(comps)
    assert out["live_blockiert"] is True


def test_market_data_stale_blocks_signal_live() -> None:
    comps = [_base("Market-Stream", freshness="stale")]
    out = evaluate_health_map(comps)
    assert out["live_blockiert"] is True


def test_redis_missing_blocks_live_critical() -> None:
    comps = [_base("Redis/Eventbus", status="fail")]
    out = evaluate_health_map(comps)
    assert out["live_blockiert"] is True


def test_db_missing_blocks_live_critical() -> None:
    comps = [_base("Postgres", status="fail")]
    out = evaluate_health_map(comps)
    assert out["live_blockiert"] is True


def test_noncritical_llm_failure_does_not_block_safety() -> None:
    comps = [_base("LLM-Orchestrator", status="fail"), _base("Postgres"), _base("Redis/Eventbus"), _base("Reconcile")]
    out = evaluate_health_map(comps)
    assert out["live_blockiert"] is False
    assert out["gesamtstatus"] == "fail"


def test_payload_contains_no_secrets() -> None:
    redacted = redact_health_details("api_key=abc secret:xyz bearer 123")
    assert "abc" not in redacted
    assert "xyz" not in redacted
    assert "REDACTED" in redacted


def test_german_fields_present() -> None:
    d = component_payload(_base("API-Gateway"))
    for k in ("live_auswirkung_de", "fehlergrund_de", "nächster_schritt_de"):
        assert k in d


def test_ui_payload_has_no_billing_customer_terms() -> None:
    page = Path("apps/dashboard/src/app/(operator)/console/system-health-map/page.tsx").read_text(encoding="utf-8")
    assert "Systemzustand & Datenflüsse" in page
    assert_no_commercial_terms(page.lower())
