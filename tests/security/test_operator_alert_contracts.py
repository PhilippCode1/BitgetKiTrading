from __future__ import annotations

from shared_py.operator_alerts import (
    OperatorAlert,
    alert_from_reconcile_fail,
    alert_from_safety_latch_active,
    alert_informational_p3,
    alert_from_redis_or_db_live_critical,
    alert_payload_dict,
    assert_no_forbidden_commercial_terms,
    normalize_severity,
    redact_technical_details,
    sort_operator_alerts,
)


def test_reconcile_fail_p0_live_blocked() -> None:
    a = alert_from_reconcile_fail(detail="drift=3")
    assert a.severity == "P0"
    assert a.live_blockiert is True


def test_safety_latch_p0() -> None:
    a = alert_from_safety_latch_active()
    assert a.severity == "P0"
    assert a.live_blockiert is True


def test_redis_live_critical_p0_or_p1() -> None:
    a = alert_from_redis_or_db_live_critical(component="redis", detail="timeout")
    assert a.severity == "P0"
    assert a.live_blockiert is True


def test_p3_informational() -> None:
    a = alert_informational_p3(
        titel="Hinweis",
        beschreibung="Nur zur Information.",
        component="ops",
    )
    assert a.severity == "P3"
    assert a.live_blockiert is False


def test_secret_like_fields_redacted() -> None:
    raw = 'api_key: sk-secret-12345 token: abc'
    out = redact_technical_details(raw)
    assert "sk-secret-12345" not in out
    assert "REDACTED" in out


def test_german_required_payload_keys() -> None:
    a = alert_from_safety_latch_active()
    d = alert_payload_dict(a)
    for key in (
        "titel_de",
        "beschreibung_de",
        "severity",
        "live_blockiert",
        "betroffene_komponente",
        "betroffene_assets",
        "empfohlene_aktion_de",
        "nächster_sicherer_schritt_de",
        "technische_details_redacted",
        "zeitpunkt",
        "korrelation_id",
        "aktiv",
    ):
        assert key in d


def test_active_before_historical_sort() -> None:
    hist = OperatorAlert(
        titel_de="Alt",
        beschreibung_de="Archiv",
        severity="P0",
        live_blockiert=False,
        betroffene_komponente="x",
        betroffene_assets=[],
        empfohlene_aktion_de="—",
        nächster_sicherer_schritt_de="—",
        technische_details_redacted="",
        zeitpunkt="2020-01-01T00:00:00Z",
        korrelation_id="00000000-0000-0000-0000-000000000001",
        aktiv=False,
    )
    active_p2 = OperatorAlert(
        titel_de="Aktiv P2",
        beschreibung_de="…",
        severity="P2",
        live_blockiert=False,
        betroffene_komponente="y",
        betroffene_assets=[],
        empfohlene_aktion_de="—",
        nächster_sicherer_schritt_de="—",
        technische_details_redacted="",
        zeitpunkt="2020-01-02T00:00:00Z",
        korrelation_id="00000000-0000-0000-0000-000000000002",
        aktiv=True,
    )
    active_p0 = OperatorAlert(
        titel_de="Aktiv P0",
        beschreibung_de="…",
        severity="P0",
        live_blockiert=True,
        betroffene_komponente="z",
        betroffene_assets=[],
        empfohlene_aktion_de="—",
        nächster_sicherer_schritt_de="—",
        technische_details_redacted="",
        zeitpunkt="2020-01-03T00:00:00Z",
        korrelation_id="00000000-0000-0000-0000-000000000003",
        aktiv=True,
    )
    ordered = sort_operator_alerts([hist, active_p2, active_p0])
    assert ordered[0].korrelation_id == active_p0.korrelation_id
    assert ordered[1].korrelation_id == active_p2.korrelation_id
    assert ordered[2].korrelation_id == hist.korrelation_id


def test_unknown_severity_fail_safe_p1() -> None:
    assert normalize_severity(None) == "P1"
    assert normalize_severity("weird") == "P1"


def test_payload_no_billing_customer_terms() -> None:
    a = alert_from_safety_latch_active()
    blob = " ".join(str(v) for v in alert_payload_dict(a).values() if isinstance(v, (str, list)))
    assert_no_forbidden_commercial_terms(blob.lower())
    lowered = blob.lower()
    for forbidden in ("billing", "kunde", "subscription", "saas", "abo"):
        assert forbidden not in lowered


def test_assert_no_forbidden_raises() -> None:
    try:
        assert_no_forbidden_commercial_terms("billing aktiv")
    except ValueError as exc:
        assert "verbotener_begriff" in str(exc)
    else:
        raise AssertionError("expected ValueError")
