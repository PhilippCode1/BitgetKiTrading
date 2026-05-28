/**
 * Operator-Alerts fuer die Main Console (Vorfälle & Warnungen).
 * Logik ist an `shared_py/operator_alerts.py` angeglichen — Aenderungen doppelt pflegen
 * oder spaeter ueber gemeinsame Spec/API konsolidieren.
 */
import type { LiveBrokerRuntimeItem, SystemHealthResponse } from "@/lib/types";

export type OperatorSeverity = "P0" | "P1" | "P2" | "P3";

export type OperatorAlertView = Readonly<{
  titel_de: string;
  titel_en: string;
  beschreibung_de: string;
  beschreibung_en: string;
  severity: OperatorSeverity;
  live_blockiert: boolean;
  betroffene_komponente: string;
  betroffene_assets: readonly string[];
  empfohlene_aktion_de: string;
  empfohlene_aktion_en: string;
  nächster_sicherer_schritt_de: string;
  nächster_sicherer_schritt_en: string;
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

export function normalizeSeverity(
  raw: string | null | undefined,
): OperatorSeverity {
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

type MkInput = Omit<
  OperatorAlertView,
  | "zeitpunkt"
  | "korrelation_id"
  | "aktiv"
  | "titel_en"
  | "beschreibung_en"
  | "empfohlene_aktion_en"
  | "nächster_sicherer_schritt_en"
> & {
  aktiv?: boolean;
  titel_en?: string;
  beschreibung_en?: string;
  empfohlene_aktion_en?: string;
  nächster_sicherer_schritt_en?: string;
};

function mk(partial: MkInput): OperatorAlertView {
  return {
    ...partial,
    titel_en: partial.titel_en ?? partial.titel_de,
    beschreibung_en: partial.beschreibung_en ?? partial.beschreibung_de,
    empfohlene_aktion_en:
      partial.empfohlene_aktion_en ?? partial.empfohlene_aktion_de,
    nächster_sicherer_schritt_en:
      partial.nächster_sicherer_schritt_en ?? partial.nächster_sicherer_schritt_de,
    zeitpunkt: nowIso(),
    korrelation_id: newId(),
    aktiv: partial.aktiv ?? true,
  };
}

export function sortOperatorAlerts(
  alerts: readonly OperatorAlertView[],
): OperatorAlertView[] {
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
        titel_en: "System health not loaded",
        beschreibung_de:
          "Die Main Console konnte den Gateway-Health-Endpunkt nicht zuverlässig lesen. Live-Status ist unbekannt.",
        beschreibung_en:
          "The main console could not read the gateway health endpoint reliably. Live status is unknown.",
        severity: "P1",
        live_blockiert: true,
        betroffene_komponente: "gateway / health",
        betroffene_assets: [],
        empfohlene_aktion_de:
          "Netzwerk, Gateway-Logs und Autorisierung prüfen.",
        empfohlene_aktion_en:
          "Check network, gateway logs, and authorization.",
        nächster_sicherer_schritt_de:
          "Health erneut laden; bis dahin kein Live-Opening.",
        nächster_sicherer_schritt_en:
          "Reload health; no live opening until then.",
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
          titel_en: "Redis degraded on live-critical path",
          beschreibung_de: `Redis-Status ist „${redis}“, nicht „ok“.`,
          beschreibung_en: `Redis status is "${redis}", not "ok".`,
          severity: "P0",
          live_blockiert: true,
          betroffene_komponente: "redis",
          betroffene_assets: [],
          empfohlene_aktion_de:
            "Redis-Instanz und Verbindungsstring prüfen (ohne Secrets zu loggen).",
          empfohlene_aktion_en:
            "Check Redis instance and connection string (do not log secrets).",
          nächster_sicherer_schritt_de:
            "Runbook „Redis“; danach Health erneut abfragen.",
          nächster_sicherer_schritt_en:
            "Follow Redis runbook; then query health again.",
          technische_details_redacted: redactTechnicalDetails(redis),
        }),
      );
    }
    if (health.database && health.database !== "ok") {
      alerts.push(
        mk({
          titel_de: "Datenbank im livekritischen Pfad gestört",
          titel_en: "Database degraded on live-critical path",
          beschreibung_de: `Datenbank-Status ist „${health.database}“, nicht „ok“.`,
          beschreibung_en: `Database status is "${health.database}", not "ok".`,
          severity: "P0",
          live_blockiert: true,
          betroffene_komponente: "postgres",
          betroffene_assets: [],
          empfohlene_aktion_de:
            "DB-Erreichbarkeit und Migrationsschema prüfen.",
          empfohlene_aktion_en: "Check DB reachability and migration schema.",
          nächster_sicherer_schritt_de:
            "Kein Live bis DB wieder grün laut Health.",
          nächster_sicherer_schritt_en:
            "No live until DB is green again per health.",
          technische_details_redacted: redactTechnicalDetails(
            health.database_schema ?? "",
          ),
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
          titel_en: "Live flags without owner approval",
          beschreibung_de:
            "Live-Trading ist in der Health-Sicht aktiviert, aber die vollständige Owner-/Operator-Freigabe fehlt.",
          beschreibung_en:
            "Live trading appears enabled in health, but full owner/operator approval is missing.",
          severity: "P0",
          live_blockiert: true,
          betroffene_komponente: "execution / live_release",
          betroffene_assets: [],
          empfohlene_aktion_de: "Freigaben und Evidence in Ops prüfen.",
          empfohlene_aktion_en: "Review approvals and evidence in Ops.",
          nächster_sicherer_schritt_de:
            "Live-Flags reduzieren oder dokumentierte Freigabe einholen.",
          nächster_sicherer_schritt_en:
            "Reduce live flags or obtain documented approval.",
          technische_details_redacted: "",
        }),
      );
    }

    const wb = warnBlob(health);
    if (
      wb.includes("secret") &&
      (wb.includes("leak") || wb.includes("verdacht"))
    ) {
      alerts.push(
        mk({
          titel_de: "Verdacht auf Secret-Leak",
          titel_en: "Suspected secret leak",
          beschreibung_de:
            "Health-Warnungen deuten auf exponierte Secrets hin.",
          beschreibung_en: "Health warnings suggest exposed secrets.",
          severity: "P0",
          live_blockiert: true,
          betroffene_komponente: "security / secrets",
          betroffene_assets: [],
          empfohlene_aktion_de:
            "Quelle abstellen, Logs redigieren, Vault prüfen.",
          empfohlene_aktion_en: "Stop the source, redact logs, check Vault.",
          nächster_sicherer_schritt_de:
            "Incident-Review; kein Live bis geklärt.",
          nächster_sicherer_schritt_en:
            "Incident review; no live until resolved.",
          technische_details_redacted: "",
        }),
      );
    }

    const outFail = health.ops?.alert_engine?.outbox_failed ?? 0;
    if (outFail > 0) {
      alerts.push(
        mk({
          titel_de: "Alert-Engine: fehlgeschlagene Outbox-Einträge",
          titel_en: "Alert engine: failed outbox entries",
          beschreibung_de: `${outFail} fehlgeschlagene Outbox-Einträge — Eskalation prüfen.`,
          beschreibung_en: `${outFail} failed outbox entries — review escalation.`,
          severity: "P2",
          live_blockiert: false,
          betroffene_komponente: "alert-engine / outbox",
          betroffene_assets: [],
          empfohlene_aktion_de: "Monitor- und Alert-Versand prüfen.",
          empfohlene_aktion_en: "Check monitor and alert delivery.",
          nächster_sicherer_schritt_de:
            "Wiederholung vermeiden; keine Entwarnung ohne Quittung.",
          nächster_sicherer_schritt_en:
            "Avoid repeats; do not clear without acknowledgement.",
          technische_details_redacted: String(outFail),
        }),
      );
    }
  }

  if (killSwitchActiveCount > 0) {
    alerts.push(
      mk({
        titel_de: "Kill-Switch aktiv",
        titel_en: "Kill switch active",
        beschreibung_de: `Es sind ${killSwitchActiveCount} aktive Kill-Switch-Ereignis(se) gemeldet.`,
        beschreibung_en: `${killSwitchActiveCount} active kill-switch event(s) reported.`,
        severity: "P0",
        live_blockiert: true,
        betroffene_komponente: "live-broker / kill-switch",
        betroffene_assets: [],
        empfohlene_aktion_de: "Ursache klären; normale Orders stoppen.",
        empfohlene_aktion_en: "Clarify cause; stop normal orders.",
        nächster_sicherer_schritt_de: "Nur Safety-Pfade; Release nach Audit.",
        nächster_sicherer_schritt_en: "Safety paths only; release after audit.",
        technische_details_redacted: "",
      }),
    );
  }

  if (runtime?.safety_latch_active === true) {
    alerts.push(
      mk({
        titel_de: "Safety-Latch aktiv",
        titel_en: "Safety latch active",
        beschreibung_de:
          "Die Plattform hat die automatische Live-Execution angehalten (Safety-Latch).",
        beschreibung_en:
          "The platform halted automatic live execution (safety latch).",
        severity: "P0",
        live_blockiert: true,
        betroffene_komponente: "live-broker / safety-latch",
        betroffene_assets: [],
        empfohlene_aktion_de: "Reconcile und Audit prüfen.",
        empfohlene_aktion_en: "Review reconcile and audit.",
        nächster_sicherer_schritt_de:
          "Latch-Release nur nach Freigabe und Dokumentation.",
        nächster_sicherer_schritt_en:
          "Release latch only after approval and documentation.",
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
          titel_en: "Reconcile failed",
          beschreibung_de: "Der letzte Reconcile-Lauf meldet Fehler.",
          beschreibung_en: "The latest reconcile run reports errors.",
          severity: "P0",
          live_blockiert: true,
          betroffene_komponente: "live-broker / reconcile",
          betroffene_assets: [],
          empfohlene_aktion_de: "Reconcile-Logs und Drift prüfen.",
          empfohlene_aktion_en: "Check reconcile logs and drift.",
          nächster_sicherer_schritt_de: "Keine neuen Live-Openings bis grün.",
          nächster_sicherer_schritt_en: "No new live openings until green.",
          technische_details_redacted: redactTechnicalDetails(runtime.status),
        }),
      );
    } else if (!st || st === "unknown" || st === "stale") {
      alerts.push(
        mk({
          titel_de: "Reconcile unbekannt oder veraltet",
          titel_en: "Reconcile unknown or stale",
          beschreibung_de: `Reconcile-Status: ${runtime.status || "unbekannt"}.`,
          beschreibung_en: `Reconcile status: ${runtime.status || "unknown"}.`,
          severity: "P1",
          live_blockiert: true,
          betroffene_komponente: "live-broker / reconcile",
          betroffene_assets: [],
          empfohlene_aktion_de: "Live-Broker und Gateway-Zeit prüfen.",
          empfohlene_aktion_en: "Check live-broker and gateway time.",
          nächster_sicherer_schritt_de:
            "Fail-closed: kein Live bis Status verifiziert.",
          nächster_sicherer_schritt_en:
            "Fail-closed: no live until status is verified.",
          technische_details_redacted: redactTechnicalDetails(runtime.status),
        }),
      );
    }

    if (runtime.upstream_ok !== true) {
      alerts.push(
        mk({
          titel_de: "Exchange-Truth fehlt oder ist unklar",
          titel_en: "Exchange truth missing or unclear",
          beschreibung_de:
            "Upstream-/Private-API-Status reicht nicht für sichere Live-Entscheidungen.",
          beschreibung_en:
            "Upstream/private API status is insufficient for safe live decisions.",
          severity: "P0",
          live_blockiert: true,
          betroffene_komponente: "live-broker / exchange",
          betroffene_assets: [],
          empfohlene_aktion_de: "Bitget-Erreichbarkeit und Auth prüfen.",
          empfohlene_aktion_en: "Check Bitget reachability and auth.",
          nächster_sicherer_schritt_de: "Read-only Diagnose, dann Reconcile.",
          nächster_sicherer_schritt_en: "Read-only diagnosis, then reconcile.",
          technische_details_redacted: "",
        }),
      );
    }

    const bp = runtime.bitget_private_status;
    if (
      bp &&
      bp.private_api_configured === true &&
      bp.private_auth_ok === false
    ) {
      alerts.push(
        mk({
          titel_de: "Bitget private API: Authentifizierung fehlgeschlagen",
          titel_en: "Bitget private API: authentication failed",
          beschreibung_de:
            bp.private_auth_detail_de?.trim() ||
            "Private Authentifizierung ist fehlgeschlagen.",
          beschreibung_en:
            bp.private_auth_detail_de?.trim() ||
            "Private authentication failed.",
          severity: "P0",
          live_blockiert: true,
          betroffene_komponente: "live-broker / bitget-private",
          betroffene_assets: [],
          empfohlene_aktion_de:
            "Schlüsselrechte und Signatur prüfen (ohne Secrets in Logs).",
          empfohlene_aktion_en:
            "Check key permissions and signature (no secrets in logs).",
          nächster_sicherer_schritt_de: "Readiness erneut; kein Live-Submit.",
          nächster_sicherer_schritt_en: "Re-check readiness; no live submit.",
          technische_details_redacted: redactTechnicalDetails(
            [bp.private_auth_classification, bp.private_auth_exchange_code]
              .filter(Boolean)
              .join(" "),
          ),
        }),
      );
    }

    const unknownOrders = Number(runtime.order_status_counts?.unknown ?? 0);
    if (unknownOrders > 0) {
      alerts.push(
        mk({
          titel_de: "Unbekannter Order-Status nach Submit",
          titel_en: "Unknown order status after submit",
          beschreibung_de: `${unknownOrders} Order(s) mit unbekanntem Status — Retry ohne Reconcile ist verboten.`,
          beschreibung_en: `${unknownOrders} order(s) with unknown status — retry without reconcile is forbidden.`,
          severity: "P0",
          live_blockiert: true,
          betroffene_komponente: "live-broker / order-lifecycle",
          betroffene_assets: [],
          empfohlene_aktion_de: "Reconcile und Order-Journal prüfen.",
          empfohlene_aktion_en: "Check reconcile and order journal.",
          nächster_sicherer_schritt_de: "Keine neuen Openings bis Klärung.",
          nächster_sicherer_schritt_en: "No new openings until clarified.",
          technische_details_redacted: String(unknownOrders),
        }),
      );
    }

    const errs = runtime.instrument_catalog?.errors ?? [];
    if (errs.length > 0) {
      alerts.push(
        mk({
          titel_de: "Instrumentenkatalog mit Fehlern",
          titel_en: "Instrument catalog errors",
          beschreibung_de:
            "Der Asset-/Instrumentenpfad meldet Fehler — Datenqualität kann für Live gefährdet sein.",
          beschreibung_en:
            "The asset/instrument path reports errors — data quality may be unsafe for live.",
          severity: "P0",
          live_blockiert: true,
          betroffene_komponente: "instrument-catalog",
          betroffene_assets: errs.slice(0, 8),
          empfohlene_aktion_de: "Katalog-Refresh und Bitget-Readiness prüfen.",
          empfohlene_aktion_en: "Refresh catalog and check Bitget readiness.",
          nächster_sicherer_schritt_de:
            "Livefähige Assets nur nach grünem Gate.",
          nächster_sicherer_schritt_en:
            "Live-eligible assets only after a green gate.",
          technische_details_redacted: redactTechnicalDetails(errs.join("; ")),
        }),
      );
    }

    const lane = runtime.operator_live_submission?.lane ?? "";
    if (
      lane === "live_lane_blocked_upstream" ||
      lane === "live_lane_blocked_exchange"
    ) {
      alerts.push(
        mk({
          titel_de: "Liquiditäts- oder Exchange-Pfad blockiert",
          titel_en: "Liquidity or exchange path blocked",
          beschreibung_de:
            "Die Live-Lane ist wegen Upstream oder Exchange blockiert (z. B. fehlendes Orderbuch oder Verbindung).",
          beschreibung_en:
            "The live lane is blocked by upstream or exchange (e.g. missing order book or connection).",
          severity: "P0",
          live_blockiert: true,
          betroffene_komponente: "live-broker / liquidity-guard",
          betroffene_assets: [],
          empfohlene_aktion_de:
            "Orderbuch-Stream und private Verbindung prüfen.",
          empfohlene_aktion_en:
            "Check order-book stream and private connection.",
          nächster_sicherer_schritt_de:
            "Kein Live-Opening bis Lane wieder frei.",
          nächster_sicherer_schritt_en:
            "No live opening until the lane is clear again.",
          technische_details_redacted: redactTechnicalDetails(lane),
        }),
      );
    }

    const reasons = (runtime.operator_live_submission?.reasons_de ?? [])
      .join(" ")
      .toLowerCase();
    if (
      (runtime.live_trade_enable || runtime.live_order_submission_enabled) &&
      (reasons.includes("unsicher") ||
        reasons.includes("env") ||
        reasons.includes("production"))
    ) {
      alerts.push(
        mk({
          titel_de: "Produktion mit unsicherer Konfiguration",
          titel_en: "Production with unsafe configuration",
          beschreibung_de:
            "Live-relevante Flags sind gesetzt, aber die Runtime meldet unsichere oder unvollständige Umgebung.",
          beschreibung_en:
            "Live-relevant flags are set, but runtime reports an unsafe or incomplete environment.",
          severity: "P0",
          live_blockiert: true,
          betroffene_komponente: "runtime / env",
          betroffene_assets: [],
          empfohlene_aktion_de: "ENV-Validatoren und Ops-Checkliste ausführen.",
          empfohlene_aktion_en: "Run ENV validators and the Ops checklist.",
          nächster_sicherer_schritt_de:
            "Konfiguration korrigieren; kein Live bis dokumentierte Freigabe.",
          nächster_sicherer_schritt_en:
            "Fix configuration; no live until documented approval.",
          technische_details_redacted: redactTechnicalDetails(
            runtime.operator_live_submission?.reasons_de?.join(" | ") ?? "",
          ),
        }),
      );
    }
  }

  const hasHigh = alerts.some(
    (a) => a.severity === "P0" || a.severity === "P1",
  );
  if (health && !hasHigh) {
    alerts.push(
      mk({
        titel_de: "Hinweis: keine P0/P1 aus angebundenen Quellen",
        titel_en: "Note: no P0/P1 from connected sources",
        beschreibung_de:
          "Aus Health und Live-Broker-Runtime wurden keine höchsten Prioritätsmeldungen abgeleitet. Das ist keine Entwarnung für nicht angebundene Subsysteme.",
        beschreibung_en:
          "No highest-priority alerts were derived from health and live-broker runtime. This is not an all-clear for unconnected subsystems.",
        severity: "P3",
        live_blockiert: false,
        betroffene_komponente: "main-console / incidents-view",
        betroffene_assets: [],
        empfohlene_aktion_de:
          "Weitere Quellen (Audit, Datenqualität) separat prüfen.",
        empfohlene_aktion_en:
          "Review other sources (audit, data quality) separately.",
        nächster_sicherer_schritt_de:
          "Vollständige Evidence vor Live beibehalten.",
        nächster_sicherer_schritt_en:
          "Keep full evidence before going live.",
        technische_details_redacted: "",
      }),
    );
  }

  return sortOperatorAlerts(alerts);
}
