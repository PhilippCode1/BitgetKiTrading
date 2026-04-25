"""
Strukturierte Betreiberhinweise fuer ops.alerts / events:system_alert.

Ziel: Alert zeigt nicht nur das Symptom, sondern wahrscheinliche Ursachen,
Einstieg im Stack, betroffene Dienste und erwartete Folgewirkung (Runbooks / SLOs).
"""

from __future__ import annotations

from typing import Any

OPERATOR_CONTEXT_VERSION = 1

_DOC_STACK = "docs/stack_readiness.md"
_DOC_OBS = "docs/observability.md"
_DOC_OBS_SLO = "docs/observability_slos.md"
_DOC_ROOT_SLO = "OBSERVABILITY_AND_SLOS.md"
_DOC_INCIDENTS = "docs/emergency_runbook.md"


def _family(alert_key: str) -> str:
    if alert_key.startswith("svc:"):
        return "service_probe"
    if alert_key.startswith("stream:"):
        return "redis_stream"
    if alert_key.startswith("freshness:"):
        return "data_freshness"
    if alert_key.startswith("stream_stalled:"):
        return "stream_stalled"
    if alert_key.startswith("trading:"):
        return "trading_sql"
    return "unknown"


def _parse_svc(alert_key: str) -> tuple[str, str]:
    # svc:<name>:<check>
    parts = alert_key.split(":")
    svc = parts[1] if len(parts) > 1 else ""
    chk = parts[2] if len(parts) > 2 else ""
    return svc, chk


def _parse_stream(alert_key: str) -> tuple[str, str]:
    # stream:<stream>:group:<group>  (Stream-Name kann Doppelpunkte enthalten)
    if not alert_key.startswith("stream:") or ":group:" not in alert_key:
        return "", ""
    rest = alert_key[len("stream:") :]
    stream_part, group_part = rest.split(":group:", 1)
    return stream_part, group_part


def _parse_stalled(alert_key: str) -> str:
    if alert_key.startswith("stream_stalled:"):
        return alert_key.split(":", 1)[1]
    return ""


def merge_operator_guidance(
    *,
    alert_key: str,
    base_details: dict[str, Any],
    severity: str,
    title: str,
    observed_at_ms: int,
) -> dict[str, Any]:
    """Gibt neues details-Dict: Basis + Operator-Felder + Korrelation."""
    out = dict(base_details)
    fam = _family(alert_key)

    affected: list[str] = []
    causes: list[str] = []
    first_steps: list[str] = []
    stack_entry = ""
    downstream = ""
    summary = ""

    if fam == "service_probe":
        svc, chk = _parse_svc(alert_key)
        affected = [svc, "api-gateway"]
        summary = f"Service-Probe {svc}/{chk} meldet Abweichung (Severity {severity})."
        causes = [
            f"Dienst {svc} nicht erreichbar, /ready false oder /metrics nicht 200.",
            "Compose-Reihenfolge: Upstream von diesem Dienst noch nicht healthy.",
            "Falsche HEALTH_URL / Netzwerk zwischen monitor-engine und Ziel.",
        ]
        first_steps = [
            f"`docker compose ps {svc}` und Logs des Dienstes pruefen.",
            f"Manuell `GET <base>/ready` und `/health` (URL steht in details.url falls gesetzt).",
            "Vergleich mit `GET /v1/system/health` (Gateway, JWT) fuer aggregierte Sicht.",
        ]
        stack_entry = f"Worker {svc} → Ursache in dessen Logs und READINESS_REQUIRE_URLS; dann Gateway-Health."
        downstream = (
            "Nachgelagerte Ketten (Signale, Live, Charts) koennen leer oder veraltet wirken, "
            "ohne dass das Symptom die Ursache ist."
        )
        if svc == "live-broker" and chk == "kill_switch":
            causes = [
                "Mindestens ein aktiver Kill-Switch in live.kill_switch_events.",
                "Bewusster Safety-Stop — kein stilles Fehlen von Orders.",
            ]
            first_steps = [
                "Gateway: `GET /v1/live-broker/runtime` (operator_live_submission, active_kill_switches).",
                "Audit und Freigabe nur mit Rollen + Safety-API.",
            ]
            downstream = "Live-Order-Submission blockiert bis Freigabe — Paper/Shadow weiter moeglich je nach Modus."
        elif svc == "live-broker" and chk == "reconcile":
            causes.append("Reconcile-Lauf fehlgeschlagen oder Exchange-Probe negativ.")
            first_steps.insert(0, "live-broker Logs: reconcile, exchange_probe, Bitget-Erreichbarkeit.")

    elif fam == "redis_stream":
        stream, group = _parse_stream(alert_key)
        affected = ["redis", "consumer-services"]
        summary = f"Redis-Stream {stream} / Gruppe {group}: hohes Pending oder Lag."
        causes = [
            "Consumer langsam oder down (Engine startet nicht oder haengt).",
            "Producer schreibt schneller als verarbeitet — Backlog waechst.",
            "Redis Ressourcen oder Netz-Latenz.",
        ]
        first_steps = [
            f"`redis-cli XPENDING {stream} {group}` und `XINFO GROUPS {stream}` pruefen.",
            "Betroffenen Consumer-Dienst aus MONITOR_STREAMS/MONITOR_STREAM_GROUPS zuordnen und neu starten.",
            f"Siehe {_DOC_OBS} (Stream-Lag, SLIs).",
        ]
        stack_entry = "Redis zuerst, dann der Worker, der diese Gruppe konsumiert."
        downstream = (
            "Signale/Events stauen sich — verzoegerte Verarbeitung, ggf. veraltete UI und Drift in nachgelagerten Schritten."
        )
        out.setdefault("stream", stream)
        out.setdefault("group", group)

    elif fam == "data_freshness":
        dp = alert_key.removeprefix("freshness:")
        affected = ["postgres", "pipeline-producers"]
        summary = f"Datenpunkt '{dp}' ist aelter als SLO-Schwelle oder fehlt (Severity {severity})."
        causes = [
            "Producer schreibt nicht (market-stream, feature-engine, signal-engine, news-engine, …).",
            "Falsches Symbol/Umfeld — Health-Frische bezieht sich auf konfigurierte Datenpunkte.",
            "DB erreichbar, aber keine neuen Zeilen — Pipeline-Kette unterbrochen.",
        ]
        first_steps = [
            "Gateway `GET /v1/system/health` → data_freshness / warnings_display lesen.",
            f"Passenden Producer laut Stack-Doku zuordnen ({_DOC_STACK}, {_DOC_OBS}).",
            "`DATA_STALE_WARN_MS` nur nach Ursachenfix anpassen, nicht zur Alert-Unterdrueckung.",
        ]
        if dp.startswith("candles"):
            affected.insert(0, "market-stream")
            stack_entry = "market-stream → Bitget/Netz → feature-engine"
        elif dp == "signals":
            affected.insert(0, "signal-engine")
            stack_entry = "signal-engine + feature/structure/drawing/news upstream"
        elif dp == "llm":
            affected.insert(0, "llm-orchestrator")
            stack_entry = "llm-orchestrator, Redis, ggf. OpenAI-Quota"
        else:
            stack_entry = "Zuerst Postgres-Zeitstempel pruefen, dann zugehoerigen Producer laut Doku."
        downstream = (
            "Charts, Signale oder KI-Panels koennen leer oder veraltet sein; Live-Risiko steigt wenn Kerzen/Signale ausbleiben."
        )
        out.setdefault("datapoint", dp)

    elif fam == "stream_stalled":
        stream = _parse_stalled(alert_key)
        affected = ["market-stream", "redis", stream or "events-stream"]
        summary = (
            f"Stream-Laenge von '{stream}' hat sich nicht erhoeht, waehrend 1m-Kerzen kritisch stale sind."
        )
        causes = [
            "Keine neuen Events trotz erwarteter Pipeline-Aktivitaet — oft market-stream oder Bitget.",
            "Kritischer Block vor dem Stream (vorherige Stufe schreibt nicht).",
        ]
        first_steps = [
            "market-stream Logs: WebSocket, 429, Reconnect.",
            "Redis: Stream-Laenge und letzte IDs pruefen; Producer-Prozess healthy.",
            f"Runbook: Redis-Streams / Backlog pruefen ({_DOC_OBS}, {_DOC_INCIDENTS}).",
        ]
        stack_entry = "market-stream und Bitget-Verbindung zuerst, dann Redis-Stream."
        downstream = (
            "Kritisch: Pipeline wirkt eingefroren — Signale und nachgelagerte Automation koennen ausbleiben."
        )
        out.setdefault("stream", stream)

    elif fam == "trading_sql":
        affected = ["postgres", "signal-engine", "live-broker", "api-gateway"]
        summary = f"Trading-SQL-Schwelle ausgeloest: {alert_key}."
        causes = [
            "Erhoehte Fehlerrate oder ungewoehnliche Verteilung in Signal-/Execution-Daten.",
            "Konfiguration oder Marktregime geaendert — nicht automatisch Bug.",
        ]
        first_steps = [
            f"Metrik/Query in `monitor_engine/alerts/trading_sql_alerts.py` zum alert_key zuordnen.",
            f"Vergleich mit Prometheus-Regeln in `infra/observability/prometheus-alerts.yml` und {_DOC_OBS_SLO}.",
            "Stichprobe in app.signals_v1 bzw. live.* per SQL.",
        ]
        stack_entry = "SQL-Alert = Symptom in Daten — Ursache in Signal-/Risk-Logik oder Umgebung suchen."
        downstream = (
            "Abhaengig vom alert_key: mehr Abstention, Schattenpfad-Aktivitaet oder Auth-Rauschen — "
            "Konsole und Alerts duerfen gleichzeitig auffaellig sein."
        )
        if "kill_switch" in alert_key or "reconcile" in alert_key:
            affected = ["live-broker", "postgres"]

    else:
        summary = f"Monitor-Alert {alert_key} (Severity {severity})."
        causes = ["Siehe title/message und details; Familie nicht speziell klassifiziert."]
        first_steps = [
            "`GET /v1/monitor/alerts/open` und `GET /v1/system/health` (JWT).",
            f"monitor-engine Logs; Referenz {_DOC_INCIDENTS}.",
        ]
        stack_entry = "monitor-engine → betroffenen Subsystem aus alert_key ableiten."
        downstream = "Folgewirkung abhaengig vom Subsystem — Health- und Integrationsmatrix pruefen."

    out["operator_context_version"] = OPERATOR_CONTEXT_VERSION
    out["operator_summary_de"] = summary
    out["operator_likely_causes_de"] = causes
    out["operator_first_steps_de"] = first_steps
    out["operator_affected_services"] = affected
    out["operator_stack_entry_de"] = stack_entry
    out["operator_downstream_impact_de"] = downstream
    out["operator_doc_refs"] = [
        _DOC_INCIDENTS,
        _DOC_ROOT_SLO,
        _DOC_OBS_SLO,
        _DOC_OBS,
        _DOC_STACK,
    ]
    out["operator_alert_title"] = title
    out["correlation"] = {
        "alert_key": alert_key,
        "alert_family": fam,
        "severity": severity,
        "observed_at_ms": observed_at_ms,
    }
    return out
