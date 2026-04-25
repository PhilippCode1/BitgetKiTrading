"""
Menschenlesbare Texte fuer System-Health-Warn-Codes (Gateway/Dashboard).

Zusaetzlich: Feld `machine` — strukturierte, englischsprachige Signale fuer KI/Automation
(neben deutschsprachiger Operator-UI in title/message/next_step).
"""

from __future__ import annotations

from typing import Any


def _entry(
    *,
    title: str,
    message: str,
    next_step: str,
    related_services: str,
) -> dict[str, str]:
    return {
        "title": title,
        "message": message,
        "next_step": next_step,
        "related_services": related_services,
    }


_KNOWN: dict[str, dict[str, str]] = {
    "schema_connect_failed": _entry(
        title="Datenbank nicht erreichbar",
        message=(
            "Das API-Gateway kann Postgres nicht erreichen (Verbindung/DSN). "
            "Ohne DB sind Migrationen und Kerzen/Signale nicht beurteilbar — das ist ein technischer Fehler, kein „leerer“ Stack."
        ),
        next_step=(
            "Postgres-Container/DSN pruefen (DATABASE_URL), docker compose ps, Gateway-Logs. "
            "Lokal: pnpm dev:up wartet auf healthy postgres."
        ),
        related_services="postgres, api-gateway",
    ),
    "schema_missing_core_tables": _entry(
        title="Kern-Tabellen fehlen (Migrationen)",
        message=(
            "Die Datenbank antwortet, aber erwartete Kern-Tabellen in app/tsdb fehlen. "
            "Typisch: Migrationen wurden nicht angewendet oder eine teilweise leere DB — nicht mit „noch keine Marktdaten“ verwechseln."
        ),
        next_step=(
            "`python infra/migrate.py` mit gueltigem DATABASE_URL ausfuehren; danach GET /ready und GET /v1/system/health "
            "(`database_schema.missing_tables` pruefen). Compose: Migration vor Workern laut docs/stack_readiness.md."
        ),
        related_services="postgres, api-gateway",
    ),
    "schema_pending_migrations": _entry(
        title="Ausstehende SQL-Migrationen",
        message=(
            "In `app.schema_migrations` fehlen Eintraege fuer eine oder mehrere Dateien aus `infra/migrations/postgres/`. "
            "Das Schema ist hinter dem Repo-Stand zurueck — neue API-Abfragen koennen mit SQL-Fehlern brechen."
        ),
        next_step=(
            "`python infra/migrate.py` ausfuehren; zweiter Lauf sollte „no pending“ melden. "
            "Im Gateway-Image sind die *.sql-Dateien unter /app/infra/migrations/postgres fuer den Abgleich."
        ),
        related_services="postgres, api-gateway",
    ),
    "schema_database_unhealthy": _entry(
        title="Datenbank-Schema ungesund",
        message=(
            "Die aggregierte DB-Pruefung ist fehlgeschlagen, ohne dass eine spezifischere Ursache gemeldet wurde. "
            "Logs und GET /db/health (mit Auth) pruefen."
        ),
        next_step="api-gateway-Logs; optional GET /db/schema und GET /db/health.",
        related_services="api-gateway, postgres",
    ),
    "no_candles_timestamp": _entry(
        title="Noch keine Kerzen fuer dieses Symbol",
        message=(
            "In der Datenbank liegt noch kein Kerzen-Endzeitstempel. "
            "Ohne Kerzen fehlt die Basis fuer Charts und viele Signal-Pipeline-Schritte."
        ),
        next_step=(
            "Market-Stream und Feature-Pipeline starten, 1–2 Minuten warten, "
            "dann diese Seite neu laden. Optional lokal: BITGET_ALLOW_DEMO_SCHEMA_SEEDS=true "
            "und zweite Migrate-Phase (postgres_demo), siehe docs/migrations.md."
        ),
        related_services="market-stream, feature-engine",
    ),
    "no_signals_timestamp": _entry(
        title="Noch kein Signal fuer dieses Symbol",
        message=(
            "Es gibt noch keinen Signal-Zeitstempel in app.signals_v1 fuer das gewaehlte Symbol. "
            "Das ist normal, solange die Signal-Engine nicht laeuft oder noch keine Auswertung geschrieben hat."
        ),
        next_step=(
            "Signal-Engine pruefen (healthy), Redis/Postgres erreichbar. "
            "Nach Start einige Minuten warten und Health neu laden."
        ),
        related_services="signal-engine, drawing-engine, structure-engine",
    ),
    "no_news_timestamp": _entry(
        title="Noch keine News-Zeilen mit Zeitstempel",
        message=(
            "Es wurden noch keine News mit gueltigem Zeitstempel in app.news_items erfasst — "
            "der Health-Check nutzt das globale Maximum (nicht pro Symbol)."
        ),
        next_step=(
            "News-Engine und LLM-Orchestrator starten oder News-Ingestion testen. "
            "Optional: Demo-SQL unter infra/migrations/postgres_demo (siehe Doku 11) oder NEWS_FIXTURE_MODE."
        ),
        related_services="news-engine, llm-orchestrator",
    ),
    "stale_candles": _entry(
        title="Kerzendaten sind veraltet",
        message="Die letzte Kerze ist aelter als die konfigurierte Warnschwelle (Umgebungsvariable DATA_STALE_WARN_MS).",
        next_step=(
            "Market-Stream und Bitget-/Netzwerk-Pfad pruefen (`docker compose` Logs market-stream). "
            "Lokal: BITGET_DEMO_* und BITGET_SYMBOL setzen, ggf. `docker compose restart market-stream`. "
            "Reines Dev ohne Live-Kurse: Schwelle in `.env.local` erhoehen (siehe `.env.local.example`)."
        ),
        related_services="market-stream",
    ),
    "stale_signals": _entry(
        title="Signale sind veraltet",
        message="Das letzte Signal ist aelter als die konfigurierte Warnschwelle.",
        next_step="Signal-Engine-Logs pruefen; Pipeline-Blocker (Drawings, Structure) eliminieren.",
        related_services="signal-engine",
    ),
    "stale_news": _entry(
        title="News sind veraltet",
        message="Die juengste News ist aelter als die konfigurierte Warnschwelle (global, nicht pro Symbol).",
        next_step="News-Engine und Ingestion pruefen; optional Demo-News via postgres_demo oder Fixture-Mode (Doku 11).",
        related_services="news-engine",
    ),
    "live_broker_kill_switch_active": _entry(
        title="Kill-Switch aktiv",
        message=(
            "Im Live-Broker ist mindestens ein Kill-Switch aktiv — neue riskante Orders werden "
            "bewusst gestoppt (kein stilles Nicht-Handeln)."
        ),
        next_step=(
            "GET /v1/live-broker/runtime (operator_live_submission, active_kill_switches) und "
            "GET /v1/live-broker/kill-switch/events/recent; nur nach Ursachenklärung per Safety-API freigeben."
        ),
        related_services="live-broker",
    ),
    "live_broker_safety_latch_active": _entry(
        title="Safety-Latch aktiv",
        message=(
            "Der Live-Broker meldet einen aktiven Safety-Latch — ein gebundener Stop, bis ein "
            "befugter Operator die Freigabe setzt."
        ),
        next_step=(
            "Live-Broker-Seite: Runtime-Banner und Audit category=safety_latch; "
            "POST /v1/live-broker/safety/safety-latch/release nur mit Rollen + Aktions-Token."
        ),
        related_services="live-broker",
    ),
    "live_broker_critical_audits_open": _entry(
        title="Kritische Live-Audits (24h)",
        message="Es liegen kritische Audit-Ereignisse in den letzten 24 Stunden vor.",
        next_step="Audit-Trail und Reconcile-Status pruefen.",
        related_services="live-broker",
    ),
    "monitor_alerts_open": _entry(
        title="Offene Monitor-Alerts",
        message="Der Monitor-Engine hat mindestens einen offenen Alert.",
        next_step=(
            "Health-Seite: Tabelle „offene Alerts“ pruefen. Nach Ursachenfix Eintraege in Postgres auf "
            "resolved/acked setzen. "
            "Lokal ohne Bitget: LIVE_REQUIRE_EXCHANGE_HEALTH=false in .env.local (in Production bewusst true lassen). "
            "Nur Entwicklung, nach manueller Pruefung: im Repo-Root `pnpm alerts:close-local` (Stichprobe) oder "
            "`pnpm alerts:close-local-all` (alle offenen; PowerShell). "
            "SQL-Beispiele: scripts/sql/close_open_monitor_alerts_local.sql und "
            "close_open_monitor_alerts_local_all.sql."
        ),
        related_services="monitor-engine, live-broker",
    ),
    "alert_outbox_failed": _entry(
        title="Alert-Outbox: fehlgeschlagene Sendungen",
        message="In der Telegram-/Alert-Outbox gibt es fehlgeschlagene Eintraege.",
        next_step="alert-engine Logs, Telegram-Bot und Netzwerk pruefen.",
        related_services="alert-engine",
    ),
}


def _dynamic_reconcile(code: str) -> dict[str, str] | None:
    prefix = "live_broker_reconcile_"
    if not code.startswith(prefix):
        return None
    status = code[len(prefix) :].strip() or "unbekannt"
    return _entry(
        title="Live-Reconcile nicht „ok“",
        message=f"Der letzte Reconcile-Status ist „{status}“ (technischer Wert aus dem Live-Broker).",
        next_step="Live-Broker-Runtime und Reconcile-Details pruefen; Exchange-Erreichbarkeit testen.",
        related_services="live-broker",
    )


def _enrich_with_ops(
    code: str,
    base: dict[str, str],
    *,
    ops_summary: dict[str, Any] | None,
) -> dict[str, str]:
    if not ops_summary:
        return base
    out = dict(base)
    if code == "monitor_alerts_open":
        mon = ops_summary.get("monitor")
        if isinstance(mon, dict):
            n = int(mon.get("open_alert_count") or 0)
            if n > 0:
                out["message"] = (
                    f"In ops.alerts sind {n} Zeilen mit state=open (jede Zeile = eigener alert_key). "
                    "Ursachen beheben oder nach Pruefung schliessen — sonst bleibt diese Warnung."
                )
    if code == "alert_outbox_failed":
        ae = ops_summary.get("alert_engine")
        if isinstance(ae, dict):
            f = int(ae.get("outbox_failed") or 0)
            if f > 0:
                out["message"] = (
                    f"In alert.alert_outbox: {f} Eintraege mit state=failed (Telegram/Versand). "
                    "Outbox-Tabelle auf der Health-Seite und alert-engine-Logs pruefen."
                )
    if code == "live_broker_kill_switch_active":
        lb = ops_summary.get("live_broker")
        if isinstance(lb, dict):
            n = int(lb.get("active_kill_switch_count") or 0)
            if n > 0:
                out["message"] = (
                    f"Aktive Kill-Switches (aus Reconcile/Ops gezaehlt): {n}. "
                    "Jeder Eintrag traegt scope/reason in live.kill_switch_events — "
                    "Runtime operator_live_submission fasst die Lage fuer die Konsole zusammen."
                )
    if code == "live_broker_safety_latch_active":
        lb = ops_summary.get("live_broker")
        if isinstance(lb, dict) and bool(lb.get("safety_latch_active")):
            out["message"] = (
                "Safety-Latch ist gesetzt (letzter Audit-Eintrag category=safety_latch, action=arm). "
                "Das ist eine explizite Sperre, kein Konfigurations-Nebeneffekt ohne Text."
            )
    return out


def _ops_signals(ops_summary: dict[str, Any] | None) -> dict[str, Any]:
    if not ops_summary:
        return {}
    mon = ops_summary.get("monitor") if isinstance(ops_summary.get("monitor"), dict) else {}
    ae = ops_summary.get("alert_engine") if isinstance(ops_summary.get("alert_engine"), dict) else {}
    lb = ops_summary.get("live_broker") if isinstance(ops_summary.get("live_broker"), dict) else {}
    return {
        "open_alert_count": int(mon.get("open_alert_count") or 0) if mon else 0,
        "outbox_failed": int(ae.get("outbox_failed") or 0) if ae else 0,
        "outbox_pending": int(ae.get("outbox_pending") or 0) if ae else 0,
        "latest_reconcile_status": lb.get("latest_reconcile_status"),
        "active_kill_switch_count": int(lb.get("active_kill_switch_count") or 0) if lb else 0,
        "safety_latch_active": bool(lb.get("safety_latch_active")),
        "critical_audit_count_24h": int(lb.get("critical_audit_count_24h") or 0) if lb else 0,
    }


def build_machine_remediation(
    code: str,
    *,
    ops_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Englisch, strukturiert: problem_id, severity, facts, suggested_actions, verify_commands.
    Ziel: direkter Input fuer LLM-/CI-Healing ohne erneutes Raten.
    """
    c = (code or "").strip()
    sig = _ops_signals(ops_summary)

    def _base(
        *,
        problem_id: str,
        severity: str,
        summary_en: str,
        actions: list[dict[str, Any]],
        verify: list[str],
        extra_facts: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        facts: dict[str, Any] = {"warning_code": c, **sig}
        if extra_facts:
            facts.update(extra_facts)
        return {
            "schema_version": "health-warning-machine-v1",
            "problem_id": problem_id,
            "severity": severity,
            "summary_en": summary_en,
            "facts": facts,
            "suggested_actions": actions,
            "verify_commands": verify,
        }

    if c == "monitor_alerts_open":
        n = sig.get("open_alert_count", 0)
        return _base(
            problem_id="health.ops_alerts_open",
            severity="warn",
            summary_en=(
                f"Postgres table ops.alerts has {n} rows with state=open. "
                "System health adds warning monitor_alerts_open when count>0. "
                "Each row is a distinct alert_key; resolve root cause then set state to resolved/acked, "
                "or reduce noise locally if probes fail without exchange credentials."
            ),
            actions=[
                {
                    "type": "http_inspect",
                    "method": "GET",
                    "path": "/v1/monitor/alerts/open",
                    "purpose_en": "List open alerts with titles/messages for triage",
                },
                {
                    "type": "env_optional",
                    "key": "LIVE_REQUIRE_EXCHANGE_HEALTH",
                    "value": "false",
                    "when_en": "local/paper without Bitget API — stops blocking on public probe",
                    "when_de": "lokal/paper ohne Bitget — weniger Probe-Blockaden",
                },
                {
                    "type": "sql_reference",
                    "path": "scripts/sql/close_open_monitor_alerts_local.sql",
                    "purpose_en": "Example SQL to close known-noise alert_key after review",
                },
                {
                    "type": "sql_reference",
                    "path": "scripts/sql/close_open_monitor_alerts_local_all.sql",
                    "purpose_en": "Close all open ops.alerts locally after explicit review (dev only)",
                },
                {
                    "type": "dev_script",
                    "command": "pnpm alerts:close-local-all",
                    "purpose_en": "PowerShell helper wrapping SQL / safety checks (repo root)",
                },
                {
                    "type": "compose_logs",
                    "services": ["monitor-engine", "live-broker", "api-gateway"],
                },
            ],
            verify=[
                "docker compose ps monitor-engine live-broker api-gateway",
                "curl -sS \"$API_GATEWAY_URL/v1/system/health\" | jq '.warnings,.ops.monitor,.warnings_display'",
                "psql \"$DATABASE_URL\" -c \"select state, count(*) from ops.alerts group by 1;\"",
            ],
        )

    if c == "alert_outbox_failed":
        f = sig.get("outbox_failed", 0)
        return _base(
            problem_id="health.alert_outbox_failed",
            severity="warn",
            summary_en=(
                f"alert.alert_outbox has {f} rows in state failed. "
                "Telegram or downstream delivery is failing; fix bot token, network, or payload."
            ),
            actions=[
                {
                    "type": "http_inspect",
                    "method": "GET",
                    "path": "/v1/alerts/outbox/recent",
                },
                {"type": "compose_logs", "services": ["alert-engine"]},
                {"type": "env_check", "keys": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_USERNAME"]},
            ],
            verify=[
                "curl -sS \"$API_GATEWAY_URL/v1/system/health\" | jq '.ops.alert_engine'",
            ],
        )

    if c in ("no_candles_timestamp", "stale_candles"):
        return _base(
            problem_id=f"health.{c}",
            severity="warn" if c == "stale_candles" else "info",
            summary_en="Candle freshness for health symbol is missing or older than DATA_STALE_WARN_MS.",
            actions=[
                {"type": "compose_logs", "services": ["market-stream", "feature-engine"]},
                {"type": "env_check", "keys": ["BITGET_UNIVERSE_SYMBOLS", "DATA_STALE_WARN_MS"]},
            ],
            verify=[
                "curl -sS \"$API_GATEWAY_URL/v1/system/health\" | jq '.data_freshness,.symbol'",
            ],
        )

    if c in ("no_signals_timestamp", "stale_signals"):
        return _base(
            problem_id=f"health.{c}",
            severity="warn" if c == "stale_signals" else "info",
            summary_en="Signal freshness for health symbol is missing or stale.",
            actions=[{"type": "compose_logs", "services": ["signal-engine", "drawing-engine", "structure-engine"]}],
            verify=["curl -sS \"$API_GATEWAY_URL/v1/system/health\" | jq '.data_freshness'"],
        )

    if c in ("no_news_timestamp", "stale_news"):
        return _base(
            problem_id=f"health.{c}",
            severity="warn" if c == "stale_news" else "info",
            summary_en="News freshness (global max) missing or stale.",
            actions=[{"type": "compose_logs", "services": ["news-engine", "llm-orchestrator"]}],
            verify=[],
        )

    if c in (
        "live_broker_kill_switch_active",
        "live_broker_safety_latch_active",
        "live_broker_critical_audits_open",
    ):
        return _base(
            problem_id=f"health.{c}",
            severity="critical",
            summary_en=f"Live broker safety or audit condition: {c}.",
            actions=[
                {"type": "http_inspect", "path": "/v1/live-broker/runtime"},
                {"type": "compose_logs", "services": ["live-broker"]},
            ],
            verify=["curl -sS \"$API_GATEWAY_URL/v1/system/health\" | jq '.ops.live_broker'"],
        )

    if c.startswith("live_broker_reconcile_"):
        st = c[len("live_broker_reconcile_") :]
        return _base(
            problem_id="health.live_broker_reconcile_not_ok",
            severity="warn",
            summary_en=f"Latest live reconcile snapshot status is not ok: {st!r}.",
            actions=[{"type": "compose_logs", "services": ["live-broker"]}],
            verify=["curl -sS \"$API_GATEWAY_URL/v1/system/health\" | jq '.ops.live_broker'"],
            extra_facts={"reconcile_status": st},
        )

    return _base(
        problem_id=f"health.unmapped.{c}" if c else "health.unmapped",
        severity="warn",
        summary_en="Unmapped health warning code; inspect full /v1/system/health JSON and gateway logs.",
        actions=[
            {"type": "http_inspect", "path": "/v1/system/health"},
            {"type": "compose_logs", "services": ["api-gateway"]},
        ],
        verify=[
            "curl -sS \"$API_GATEWAY_URL/v1/system/health\" | jq '.warnings, .warnings_display, .services'",
        ],
        extra_facts={"raw_code": c},
    )


def describe_health_warning(
    code: str,
    *,
    ops_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Operator-Texte (de) + machine-Block (en, strukturiert) fuer einen Warn-Code."""
    c = (code or "").strip()
    if c in _KNOWN:
        out_enriched = _enrich_with_ops(c, dict(_KNOWN[c]), ops_summary=ops_summary)
        out_enriched["code"] = c
        out_enriched["machine"] = build_machine_remediation(c, ops_summary=ops_summary)
        return out_enriched
    dyn = _dynamic_reconcile(c)
    if dyn is not None:
        out = dict(dyn)
        out["code"] = c
        out["machine"] = build_machine_remediation(c, ops_summary=ops_summary)
        return out
    return {
        "code": c,
        "title": "Hinweis vom System",
        "message": (
            f"Unbekannter Health-Code „{c}“. Vollstaendige Diagnose: Gateway-Log zu GET /v1/system/health "
            "und JSON-Felder warnings, services, integrations_matrix pruefen."
        ),
        "next_step": (
            "curl /v1/system/health (mit Auth) speichern; api-gateway-Logs nach „system health“ filtern; "
            "bei Integrationsfehlern integrations_matrix Zeilen mit health_error_public lesen."
        ),
        "related_services": "api-gateway",
        "machine": build_machine_remediation(c, ops_summary=ops_summary),
    }


def build_warnings_display(
    codes: list[str],
    *,
    ops_summary: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return [describe_health_warning(c, ops_summary=ops_summary) for c in codes]
