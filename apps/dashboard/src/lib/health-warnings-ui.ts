import { buildMachineRemediation } from "@/lib/health-warning-machine";
import type {
  HealthWarningDisplayItem,
  HealthWarningMachine,
  SystemHealthResponse,
} from "@/lib/types";

type HealthJson = SystemHealthResponse & {
  /** Manche Proxies liefern camelCase */
  warningsDisplay?: HealthWarningDisplayItem[];
};

function isDisplayRow(x: unknown): x is HealthWarningDisplayItem {
  if (!x || typeof x !== "object") return false;
  const o = x as Record<string, unknown>;
  const base =
    typeof o.code === "string" &&
    typeof o.title === "string" &&
    typeof o.message === "string" &&
    typeof o.next_step === "string" &&
    typeof o.related_services === "string";
  if (!base) return false;
  if (
    o.machine !== undefined &&
    (typeof o.machine !== "object" || o.machine === null)
  )
    return false;
  return true;
}

function isMachineShape(m: unknown): m is HealthWarningMachine {
  if (!m || typeof m !== "object") return false;
  const o = m as Record<string, unknown>;
  return (
    o.schema_version === "health-warning-machine-v1" &&
    typeof o.problem_id === "string" &&
    typeof o.summary_en === "string"
  );
}

function withMachine(
  w: HealthWarningDisplayItem,
  health: SystemHealthResponse,
): HealthWarningDisplayItem {
  if (w.machine && isMachineShape(w.machine)) return w;
  return { ...w, machine: buildMachineRemediation(w.code, health) };
}

/** Fallback wenn Gateway-Feld fehlt (ältere Images / Proxy) — Texte spiegeln shared_py/health_warnings_display.py */
function deriveWarningsFromCodes(
  codes: string[],
  health: SystemHealthResponse,
): HealthWarningDisplayItem[] {
  const ops = health.ops;
  const monCount =
    ops && typeof ops.monitor === "object" && ops.monitor !== null
      ? Number(
          (ops.monitor as { open_alert_count?: number }).open_alert_count ?? 0,
        )
      : 0;
  const outboxFailed =
    ops && typeof ops.alert_engine === "object" && ops.alert_engine !== null
      ? Number(
          (ops.alert_engine as { outbox_failed?: number }).outbox_failed ?? 0,
        )
      : 0;

  const known: Record<string, Omit<HealthWarningDisplayItem, "code">> = {
    schema_connect_failed: {
      title: "Datenbank nicht erreichbar",
      message:
        "Postgres ist nicht erreichbar (DSN/Netzwerk). Das ist ein technischer Fehler — nicht mit fehlenden Kerzen/Signalen verwechseln.",
      next_step:
        "DATABASE_URL, docker compose ps (postgres healthy), Gateway-Logs. Lokal: pnpm dev:up.",
      related_services: "postgres, api-gateway",
    },
    schema_missing_core_tables: {
      title: "Kern-Tabellen fehlen",
      message:
        "Erwartete Tabellen in app/tsdb fehlen — meist fehlende oder abgebrochene Migrationen. Kein normaler Leerzustand.",
      next_step:
        "python infra/migrate.py mit gültigem DATABASE_URL; danach GET /ready prüfen.",
      related_services: "postgres, api-gateway",
    },
    schema_pending_migrations: {
      title: "Ausstehende Migrationen",
      message:
        "Im Repo liegen SQL-Migrationen, die noch nicht in app.schema_migrations eingetragen sind. Schema hinter dem Code.",
      next_step:
        "python infra/migrate.py; zweiter Lauf ohne neue applied-Dateien.",
      related_services: "postgres, api-gateway",
    },
    schema_database_unhealthy: {
      title: "Datenbank-Schema ungesund",
      message: "DB-Check fehlgeschlagen ohne spezifischere Meldung.",
      next_step: "GET /db/health (Auth) und Gateway-Logs.",
      related_services: "api-gateway",
    },
    no_candles_timestamp: {
      title: "Noch keine Kerzen für dieses Symbol",
      message:
        "In der Datenbank liegt noch kein Kerzen-Endzeitstempel. Ohne Kerzen fehlt die Basis für Charts und viele Signal-Pipeline-Schritte.",
      next_step:
        "Market-Stream und Feature-Pipeline starten, 1–2 Minuten warten, dann neu laden. Frischer lokaler Stack: Migration 596 legt Demo-Kerzen an, wenn die Kerzen-Tabelle noch leer ist.",
      related_services: "market-stream, feature-engine",
    },
    no_signals_timestamp: {
      title: "Noch kein Signal für dieses Symbol",
      message:
        "Es gibt noch keinen Signal-Zeitstempel in app.signals_v1 für das gewählte Symbol. Das ist normal, solange die Signal-Engine nicht läuft oder noch keine Auswertung geschrieben hat.",
      next_step:
        "Signal-Engine prüfen (healthy), Redis/Postgres erreichbar. Nach Start einige Minuten warten und Health neu laden.",
      related_services: "signal-engine, drawing-engine, structure-engine",
    },
    no_news_timestamp: {
      title: "Noch keine News-Zeilen mit Zeitstempel",
      message:
        "Es wurden noch keine News mit gültigem Zeitstempel in app.news_items erfasst — der Health-Check nutzt das globale Maximum (nicht pro Symbol).",
      next_step:
        "News-Engine und LLM-Orchestrator starten oder News-Ingestion testen. Migration 596 kann eine Demo-News-Zeile einfügen, wenn die Tabelle leer ist.",
      related_services: "news-engine, llm-orchestrator",
    },
    stale_candles: {
      title: "Kerzendaten sind veraltet",
      message:
        "Die letzte Kerze ist älter als die konfigurierte Warnschwelle (Umgebungsvariable DATA_STALE_WARN_MS).",
      next_step:
        "Market-Stream und Bitget-/Netzwerk-Pfad prüfen (docker compose Logs market-stream). Lokal: BITGET_DEMO_* und BITGET_SYMBOL setzen, ggf. docker compose restart market-stream. Reines Dev ohne Live-Kurse: Schwelle in .env.local erhöhen (siehe .env.local.example).",
      related_services: "market-stream",
    },
    stale_signals: {
      title: "Signale sind veraltet",
      message:
        "Das letzte Signal ist älter als die konfigurierte Warnschwelle.",
      next_step:
        "Signal-Engine-Logs prüfen; Pipeline-Blocker (Drawings, Structure) eliminieren.",
      related_services: "signal-engine",
    },
    stale_news: {
      title: "News sind veraltet",
      message:
        "Die jüngste News ist älter als die konfigurierte Warnschwelle (global, nicht pro Symbol).",
      next_step:
        "News-Engine und Ingestion prüfen; bei leerem Stack Migration 596 kann Demo-News einfügen.",
      related_services: "news-engine",
    },
    live_broker_kill_switch_active: {
      title: "Kill-Switch aktiv",
      message: "Im Live-Broker ist mindestens ein Kill-Switch aktiv.",
      next_step: "Operator-Cockpit und Audit prüfen.",
      related_services: "live-broker",
    },
    live_broker_safety_latch_active: {
      title: "Safety-Latch aktiv",
      message: "Der Live-Broker meldet einen aktiven Safety-Latch.",
      next_step: "Forensik im Operator-Dashboard.",
      related_services: "live-broker",
    },
    live_broker_critical_audits_open: {
      title: "Kritische Live-Audits (24h)",
      message: "Kritische Audit-Ereignisse in den letzten 24 Stunden.",
      next_step: "Audit-Trail und Reconcile prüfen.",
      related_services: "live-broker",
    },
    monitor_alerts_open: {
      title: "Offene Monitor-Alerts",
      message:
        monCount > 0
          ? `In ops.alerts sind ${monCount} Zeilen mit state=open (jeweils eigener alert_key). Ursache beheben oder nach Prüfung schließen.`
          : "Der Monitor meldet offene Alerts in ops.alerts.",
      next_step:
        "Tabelle auf dieser Seite prüfen. Lokal ohne Bitget: LIVE_REQUIRE_EXCHANGE_HEALTH=false in .env.local (in Production bewusst true lassen). Nur Entwicklung, nach Prüfung: pnpm alerts:close-local oder pnpm alerts:close-local-all (PowerShell). SQL: scripts/sql/close_open_monitor_alerts_local.sql und close_open_monitor_alerts_local_all.sql",
      related_services: "monitor-engine, live-broker",
    },
    alert_outbox_failed: {
      title: "Alert-Outbox: fehlgeschlagene Sendungen",
      message:
        outboxFailed > 0
          ? `alert.alert_outbox: ${outboxFailed} Einträge failed — Telegram/Bot prüfen.`
          : "Fehlgeschlagene Eintraege in der Alert-Outbox.",
      next_step: "alert-engine-Logs und Telegram-Bot.",
      related_services: "alert-engine",
    },
  };

  const out: HealthWarningDisplayItem[] = [];
  for (const raw of codes) {
    const c = (raw || "").trim();
    if (!c) continue;
    const k = known[c];
    if (k) {
      out.push({ code: c, ...k });
      continue;
    }
    if (c.startsWith("live_broker_reconcile_")) {
      const st = c.slice("live_broker_reconcile_".length) || "unbekannt";
      out.push({
        code: c,
        title: "Live-Reconcile nicht ok",
        message: `Letzter Reconcile-Status: „${st}“.`,
        next_step: "Live-Broker-Runtime und Exchange-Erreichbarkeit prüfen.",
        related_services: "live-broker",
      });
      continue;
    }
    out.push({
      code: c,
      title: "Hinweis vom System",
      message:
        "Ein Health-Check meldet eine Abweichung (technischer Code im Feld code).",
      next_step: "API-Gateway-Logs zu system/health prüfen.",
      related_services: "—",
    });
  }
  return out;
}

/**
 * Anzeige-Liste für Health-Warnungen: bevorzugt `warnings_display` vom Gateway;
 * akzeptiert camelCase `warningsDisplay`; sonst Ableitung aus `warnings` + ops-Zaehlern.
 */
export function healthWarningsForDisplay(
  health: SystemHealthResponse,
): HealthWarningDisplayItem[] {
  const h = health as HealthJson;
  const rawWd = h.warnings_display ?? h.warningsDisplay;
  let items: HealthWarningDisplayItem[];
  if (Array.isArray(rawWd) && rawWd.length > 0) {
    const cleaned = rawWd.filter(isDisplayRow);
    if (cleaned.length > 0) {
      items = cleaned;
    } else {
      items = [];
    }
  } else {
    items = [];
  }
  if (items.length === 0) {
    const codes = health.warnings ?? [];
    if (!codes.length) return [];
    items = deriveWarningsFromCodes(codes, health);
  }
  return items.map((w) => withMachine(w, health));
}
