/**
 * Operator-Alerts fuer die Main Console (Vorfälle & Warnungen).
 * Logik ist an `shared_py/operator_alerts.py` angeglichen — Aenderungen doppelt pflegen
 * oder spaeter ueber gemeinsame Spec/API konsolidieren.
 */
import type { LiveBrokerRuntimeItem, SystemHealthResponse } from "@/lib/types";

export type OperatorSeverity = "P0" | "P1" | "P2" | "P3";

export type OperatorAlertView = Readonly<{
  titel_de: string;
  beschreibung_de: string;
  severity: OperatorSeverity;
  live_blockiert: boolean;
  betroffene_komponente: string;
  betroffene_assets: readonly string[];
  empfohlene_aktion_de: string;
  nächster_sicherer_schritt_de: string;
  technische_details_redacted: string;
  zeitpunkt: string;
  korrelation_id: string;
  aktiv: boolean;
}>;

const SEV_RANK: Record<OperatorSeverity, number> = {
  P0: 0,
  P1: 1,
  P2: 2,
  P3: 3,
};

export function normalizeSeverity(raw: string | null | undefined): OperatorSeverity {
  const s = (raw ?? "").trim().toUpperCase();
  if (s === "P0" || s === "P1" || s === "P2" || s === "P3") return s;
  return "P1";
}

export function redactTechnicalDetails(value: unknown): string {
  let raw = value == null ? "" : String(value);
  raw = raw.replace(
    /(apikey|api_key|secret|token|password|authorization)\s*[:=]\s*\S+/gi,
    "$1=***REDACTED***",
  );
  raw = raw.replace(/bearer\s+\S+/gi, "Bearer ***REDACTED***");
  return raw.length > 2000 ? `${raw.slice(0, 2000)}…` : raw;
}

function nowIso(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `corr-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function mk(
  partial: Omit<OperatorAlertView, "zeitpunkt" | "korrelation_id" | "aktiv"> & {
    aktiv?: boolean;
  },
): OperatorAlertView {
  return {
    ...partial,
    zeitpunkt: nowIso(),
    korrelation_id: newId(),
    aktiv: partial.aktiv ?? true,
  };
}

export function sortOperatorAlerts(alerts: readonly OperatorAlertView[]): OperatorAlertView[] {
  return [...alerts].sort((a, b) => {
    const ar = a.aktiv ? 0 : 1;
    const br = b.aktiv ? 0 : 1;
    if (ar !== br) return ar - br;
    return SEV_RANK[a.severity] - SEV_RANK[b.severity];
  });
}

function warnBlob(health: SystemHealthResponse | null): string {
  if (!health) return "";
  const parts = [...(health.warnings ?? [])];
  const disp = health.warnings_display ?? health.warningsDisplay ?? [];
  for (const w of disp) {
    parts.push(w.title, w.message, w.next_step);
  }
  return parts.join(" ").toLowerCase();
}

export function buildOperatorAlertsFromConsoleSnapshot(input: {
  health: SystemHealthResponse | null;
  runtime: LiveBrokerRuntimeItem | null;
  killSwitchActiveCount: number;
}): OperatorAlertView[] {
  const { health, runtime, killSwitchActiveCount } = input;
  const alerts: OperatorAlertView[] = [];

  if (!health) {
    alerts.push(
      mk({
        titel_de: "System-Health nicht geladen",
        beschreibung_de:
          "Die Main Console konnte den Gateway-Health-Endpunkt nicht zuverlässig lesen. Live-Status ist unbekannt.",
        severity: "P1",
        live_blockiert: true,
        betroffene_komponente: "gateway / health",
        betroffene_assets: [],
        empfohlene_aktion_de: "Netzwerk, Gateway-Logs und Autorisierung prüfen.",
        nächster_sicherer_schritt_de: "Health erneut laden; bis dahin kein Live-Opening.",
        technische_details_redacted: "",
      }),
    );
  }

  if (health) {
    const redis = health.redis;
    if (redis && redis !== "ok") {
      alerts.push(
        mk({
          titel_de: "Redis im livekritischen Pfad gestört",
          beschreibung_de: `Redis-Status ist „${redis}“, nicht „ok“.`,
          severity: "P0",
          live_blockiert: true,
          betroffene_komponente: "redis",
          betroffene_assets: [],
          empfohlene_aktion_de: "Redis-Instanz und Verbindungsstring prüfen (ohne Secrets zu loggen).",
          nächster_sicherer_schritt_de: "Runbook „Redis“; danach Health erneut abfragen.",
          technische_details_redacted: redactTechnicalDetails(redis),
        }),
      );
    }
    if (health.database && health.database !== "ok") {
      alerts.push(
        mk({
          titel_de: "Datenbank im livekritischen Pfad gestört",
          beschreibung_de: `Datenbank-Status ist „${health.database}“, nicht „ok“.`,
          severity: "P0",
          live_blockiert: true,
          betroffene_komponente: "postgres",
          betroffene_assets: [],
          empfohlene_aktion_de: "DB-Erreichbarkeit und Migrationsschema prüfen.",
          nächster_sicherer_schritt_de: "Kein Live bis DB wieder grün laut Health.",
          technische_details_redacted: redactTechnicalDetails(health.database_schema ?? ""),
        }),
      );
    }

    const exr = health.execution?.execution_runtime;
    const liveOn =
      Boolean(health.execution?.live_trade_enable) &&
      Boolean(health.execution?.live_order_submission_enabled);
    const released = Boolean(
      exr?.live_release?.fully_released_for_automated_exchange_orders,
    );
    if (liveOn && !released) {
      alerts.push(
        mk({
          titel_de: "Live-Flags ohne Owner-Freigabe",
          beschreibung_de:
            "Live-Trading ist in der Health-Sicht aktiviert, aber die vollständige Owner-/Operator-Freigabe fehlt.",
          severity: "P0",
          live_blockiert: true,
          betroffene_komponente: "execution / live_release",
          betroffene_assets: [],
          empfohlene_aktion_de: "Freigaben und Evidence in Ops prüfen.",
          nächster_sicherer_schritt_de: "Live-Flags reduzieren oder dokumentierte Freigabe einholen.",
          technische_details_redacted: "",
        }),
      );
    }

    const wb = warnBlob(health);
    if (wb.includes("secret") && (wb.includes("leak") || wb.includes("verdacht"))) {
      alerts.push(
        mk({
          titel_de: "Verdacht auf Secret-Leak",
          beschreibung_de: "Health-Warnungen deuten auf exponierte Secrets hin.",
          severity: "P0",
          live_blockiert: true,
          betroffene_komponente: "security / secrets",
          betroffene_assets: [],
          empfohlene_aktion_de: "Quelle abstellen, Logs redigieren, Vault prüfen.",
          nächster_sicherer_schritt_de: "Incident-Review; kein Live bis geklärt.",
          technische_details_redacted: "",
        }),
      );
    }

    const outFail = health.ops?.alert_engine?.outbox_failed ?? 0;
    if (outFail > 0) {
      alerts.push(
        mk({
          titel_de: "Alert-Engine: fehlgeschlagene Outbox-Einträge",
          beschreibung_de: `${outFail} fehlgeschlagene Outbox-Einträge — Eskalation prüfen.`,
          severity: "P2",
          live_blockiert: false,
          betroffene_komponente: "alert-engine / outbox",
          betroffene_assets: [],
          empfohlene_aktion_de: "Monitor- und Alert-Versand prüfen.",
          nächster_sicherer_schritt_de: "Wiederholung vermeiden; keine Entwarnung ohne Quittung.",
          technische_details_redacted: String(outFail),
        }),
      );
    }
  }

  if (killSwitchActiveCount > 0) {
    alerts.push(
      mk({
        titel_de: "Kill-Switch aktiv",
        beschreibung_de: `Es sind ${killSwitchActiveCount} aktive Kill-Switch-Ereignis(se) gemeldet.`,
        severity: "P0",
        live_blockiert: true,
        betroffene_komponente: "live-broker / kill-switch",
        betroffene_assets: [],
        empfohlene_aktion_de: "Ursache klären; normale Orders stoppen.",
        nächster_sicherer_schritt_de: "Nur Safety-Pfade; Release nach Audit.",
        technische_details_redacted: "",
      }),
    );
  }

  if (runtime?.safety_latch_active === true) {
    alerts.push(
      mk({
        titel_de: "Safety-Latch aktiv",
        beschreibung_de: "Die Plattform hat die automatische Live-Execution angehalten (Safety-Latch).",
        severity: "P0",
        live_blockiert: true,
        betroffene_komponente: "live-broker / safety-latch",
        betroffene_assets: [],
        empfohlene_aktion_de: "Reconcile und Audit prüfen.",
        nächster_sicherer_schritt_de: "Latch-Release nur nach Freigabe und Dokumentation.",
        technische_details_redacted: "",
      }),
    );
  }

  if (runtime) {
    const st = (runtime.status ?? "").toLowerCase();
    if (st === "fail") {
      alerts.push(
        mk({
          titel_de: "Reconcile fehlgeschlagen",
          beschreibung_de: "Der letzte Reconcile-Lauf meldet Fehler.",
          severity: "P0",
          live_blockiert: true,
          betroffene_komponente: "live-broker / reconcile",
          betroffene_assets: [],
          empfohlene_aktion_de: "Reconcile-Logs und Drift prüfen.",
          nächster_sicherer_schritt_de: "Keine neuen Live-Openings bis grün.",
          technische_details_redacted: redactTechnicalDetails(runtime.status),
        }),
      );
    } else if (!st || st === "unknown" || st === "stale") {
      alerts.push(
        mk({
          titel_de: "Reconcile unbekannt oder veraltet",
          beschreibung_de: `Reconcile-Status: ${runtime.status || "unbekannt"}.`,
          severity: "P1",
          live_blockiert: true,
          betroffene_komponente: "live-broker / reconcile",
          betroffene_assets: [],
          empfohlene_aktion_de: "Live-Broker und Gateway-Zeit prüfen.",
          nächster_sicherer_schritt_de: "Fail-closed: kein Live bis Status verifiziert.",
          technische_details_redacted: redactTechnicalDetails(runtime.status),
        }),
      );
    }

    if (runtime.upstream_ok !== true) {
      alerts.push(
        mk({
          titel_de: "Exchange-Truth fehlt oder ist unklar",
          beschreibung_de: "Upstream-/Private-API-Status reicht nicht für sichere Live-Entscheidungen.",
          severity: "P0",
          live_blockiert: true,
          betroffene_komponente: "live-broker / exchange",
          betroffene_assets: [],
          empfohlene_aktion_de: "Bitget-Erreichbarkeit und Auth prüfen.",
          nächster_sicherer_schritt_de: "Read-only Diagnose, dann Reconcile.",
          technische_details_redacted: "",
        }),
      );
    }

    const bp = runtime.bitget_private_status;
    if (bp && bp.private_api_configured === true && bp.private_auth_ok === false) {
      alerts.push(
        mk({
          titel_de: "Bitget private API: Authentifizierung fehlgeschlagen",
          beschreibung_de: bp.private_auth_detail_de?.trim() || "Private Authentifizierung ist fehlgeschlagen.",
          severity: "P0",
          live_blockiert: true,
          betroffene_komponente: "live-broker / bitget-private",
          betroffene_assets: [],
          empfohlene_aktion_de: "Schlüsselrechte und Signatur prüfen (ohne Secrets in Logs).",
          nächster_sicherer_schritt_de: "Readiness erneut; kein Live-Submit.",
          technische_details_redacted: redactTechnicalDetails(
            [bp.private_auth_classification, bp.private_auth_exchange_code].filter(Boolean).join(" "),
          ),
        }),
      );
    }

    const unknownOrders = Number(runtime.order_status_counts?.unknown ?? 0);
    if (unknownOrders > 0) {
      alerts.push(
        mk({
          titel_de: "Unbekannter Order-Status nach Submit",
          beschreibung_de: `${unknownOrders} Order(s) mit unbekanntem Status — Retry ohne Reconcile ist verboten.`,
          severity: "P0",
          live_blockiert: true,
          betroffene_komponente: "live-broker / order-lifecycle",
          betroffene_assets: [],
          empfohlene_aktion_de: "Reconcile und Order-Journal prüfen.",
          nächster_sicherer_schritt_de: "Keine neuen Openings bis Klärung.",
          technische_details_redacted: String(unknownOrders),
        }),
      );
    }

    const errs = runtime.instrument_catalog?.errors ?? [];
    if (errs.length > 0) {
      alerts.push(
        mk({
          titel_de: "Instrumentenkatalog mit Fehlern",
          beschreibung_de: "Der Asset-/Instrumentenpfad meldet Fehler — Datenqualität kann für Live gefährdet sein.",
          severity: "P0",
          live_blockiert: true,
          betroffene_komponente: "instrument-catalog",
          betroffene_assets: errs.slice(0, 8),
          empfohlene_aktion_de: "Katalog-Refresh und Bitget-Readiness prüfen.",
          nächster_sicherer_schritt_de: "Livefähige Assets nur nach grünem Gate.",
          technische_details_redacted: redactTechnicalDetails(errs.join("; ")),
        }),
      );
    }

    const lane = runtime.operator_live_submission?.lane ?? "";
    if (lane === "live_lane_blocked_upstream" || lane === "live_lane_blocked_exchange") {
      alerts.push(
        mk({
          titel_de: "Liquiditäts- oder Exchange-Pfad blockiert",
          beschreibung_de:
            "Die Live-Lane ist wegen Upstream oder Exchange blockiert (z. B. fehlendes Orderbuch oder Verbindung).",
          severity: "P0",
          live_blockiert: true,
          betroffene_komponente: "live-broker / liquidity-guard",
          betroffene_assets: [],
          empfohlene_aktion_de: "Orderbuch-Stream und private Verbindung prüfen.",
          nächster_sicherer_schritt_de: "Kein Live-Opening bis Lane wieder frei.",
          technische_details_redacted: redactTechnicalDetails(lane),
        }),
      );
    }

    const reasons = (runtime.operator_live_submission?.reasons_de ?? []).join(" ").toLowerCase();
    if (
      (runtime.live_trade_enable || runtime.live_order_submission_enabled) &&
      (reasons.includes("unsicher") || reasons.includes("env") || reasons.includes("production"))
    ) {
      alerts.push(
        mk({
          titel_de: "Produktion mit unsicherer Konfiguration",
          beschreibung_de:
            "Live-relevante Flags sind gesetzt, aber die Runtime meldet unsichere oder unvollständige Umgebung.",
          severity: "P0",
          live_blockiert: true,
          betroffene_komponente: "runtime / env",
          betroffene_assets: [],
          empfohlene_aktion_de: "ENV-Validatoren und Ops-Checkliste ausführen.",
          nächster_sicherer_schritt_de: "Konfiguration korrigieren; kein Live bis dokumentierte Freigabe.",
          technische_details_redacted: redactTechnicalDetails(
            runtime.operator_live_submission?.reasons_de?.join(" | ") ?? "",
          ),
        }),
      );
    }
  }

  const hasHigh = alerts.some((a) => a.severity === "P0" || a.severity === "P1");
  if (health && !hasHigh) {
    alerts.push(
      mk({
        titel_de: "Hinweis: keine P0/P1 aus angebundenen Quellen",
        beschreibung_de:
          "Aus Health und Live-Broker-Runtime wurden keine höchsten Prioritätsmeldungen abgeleitet. Das ist keine Entwarnung für nicht angebundene Subsysteme.",
        severity: "P3",
        live_blockiert: false,
        betroffene_komponente: "main-console / incidents-view",
        betroffene_assets: [],
        empfohlene_aktion_de: "Weitere Quellen (Audit, Datenqualität) separat prüfen.",
        nächster_sicherer_schritt_de: "Vollständige Evidence vor Live beibehalten.",
        technische_details_redacted: "",
      }),
    );
  }

  return sortOperatorAlerts(alerts);
}
