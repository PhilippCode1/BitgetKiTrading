"""Aggregations- und Wahrheitsschicht fuer GET /v1/system/health (rein funktional, testbar)."""

from __future__ import annotations

from typing import Any

from api_gateway.gateway_readiness_core import READINESS_CONTRACT_VERSION

TRUTH_LAYER_SCHEMA_VERSION = 1


def compute_aggregate_status(
    *,
    readiness_core_ok: bool,
    warnings: list[str],
    services: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Kompakter Zustand fuer UI und Monitoring.

    - red: Kern-Readiness fehlgeschlagen (gleiche Definition wie GET /ready ohne Peers).
    - degraded: Kern ok, aber Warnungen oder mindestens ein konfigurierter Worker-Sonde-Fehler.
    - green: Kern ok, keine Warnungen, alle konfigurierten Sonden ok (not_configured zaehlt nicht).
    """
    if not readiness_core_ok:
        return {
            "level": "red",
            "summary_de": "Kern-Readiness fehlgeschlagen (Postgres, Schema/Migrationen oder Redis).",
            "primary_reason_codes": ["readiness_core_failed"],
        }

    svc_issues: list[str] = []
    for s in services:
        if not s.get("configured"):
            continue
        st = str(s.get("status") or "").strip().lower()
        if st in ("error", "degraded"):
            name = str(s.get("name") or "unknown")
            svc_issues.append(name)

    warn_list = [w for w in warnings if isinstance(w, str) and w.strip()]
    if warn_list or svc_issues:
        codes = list(warn_list[:24])
        if svc_issues:
            codes.append("services_probe:" + ",".join(svc_issues[:12]))
        return {
            "level": "degraded",
            "summary_de": (
                "Kern-Readiness ok, aber Warnungen oder Worker-/Sonden-Abweichungen — Details in "
                "warnings, warnings_display und services."
            ),
            "primary_reason_codes": codes,
        }

    return {
        "level": "green",
        "summary_de": "Kern-Readiness ok, keine aktiven Warnungen, konfigurierte Sonden ohne Fehler.",
        "primary_reason_codes": [],
    }


def truth_layer_meta(*, auth_hint_de: str) -> dict[str, Any]:
    """Stabile Metadaten zum Verhaeltnis /ready vs. System-Health."""
    return {
        "schema_version": TRUTH_LAYER_SCHEMA_VERSION,
        "readiness": {
            "path": "/ready",
            "role": "readiness",
            "contract_version": READINESS_CONTRACT_VERSION,
            "semantics_de": (
                "Harte technische Bereitschaft: Postgres, Schema/Migrations-Abgleich, Redis; optional "
                "Peer-URLs aus READINESS_REQUIRE_URLS. HTTP 200 mit ready=false ist wahrheitsgemaess."
            ),
        },
        "system_health": {
            "path": "/v1/system/health",
            "role": "operator_aggregate",
            "contract_version": TRUTH_LAYER_SCHEMA_VERSION,
            "auth_de": auth_hint_de,
            "semantics_de": (
                "Erklaerte Aggregation fuer Operatoren und UI: Frische, Worker-Sonden, Ops-Zahlen, "
                "Warnungstexte. Feld aggregate.level fasst den Zustand fuer Dashboards zusammen; "
                "readiness_core.checks entspricht dem Kern von GET /ready (ohne Peers)."
            ),
        },
    }
