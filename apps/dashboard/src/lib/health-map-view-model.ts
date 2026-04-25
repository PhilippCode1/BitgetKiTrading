import type { LiveBrokerRuntimeItem, SystemHealthResponse } from "@/lib/types";

export type HealthMapStatus = "ok" | "warn" | "fail" | "unknown";
export type HealthMapFreshness = "fresh" | "stale" | "missing" | "not_applicable";

export type HealthMapComponentView = Readonly<{
  komponente: string;
  status: HealthMapStatus;
  freshness_status: HealthMapFreshness;
  live_auswirkung_de: string;
  blockiert_live: boolean;
  letzter_erfolg_ts: string | null;
  letzter_fehler_ts: string | null;
  fehlergrund_de: string;
  nächster_schritt_de: string;
}>;

export type HealthMapView = Readonly<{
  gesamtstatus: HealthMapStatus;
  live_blockiert: boolean;
  live_sicher: boolean;
  blocker_gründe_de: readonly string[];
  komponenten: readonly HealthMapComponentView[];
}>;

const STATUS_ORDER: Record<HealthMapStatus, number> = {
  fail: 0,
  unknown: 1,
  warn: 2,
  ok: 3,
};

function redact(input: unknown): string {
  let raw = input == null ? "" : String(input);
  raw = raw.replace(
    /(apikey|api_key|secret|password|passphrase|token|authorization)\s*[:=]\s*\S+/gi,
    "$1=***REDACTED***",
  );
  raw = raw.replace(/bearer\s+\S+/gi, "Bearer ***REDACTED***");
  return raw;
}

function freshnessFromTs(tsMs: number | null | undefined, staleAfterMs: number): HealthMapFreshness {
  if (tsMs == null) return "missing";
  const age = Date.now() - tsMs;
  return age > staleAfterMs ? "stale" : "fresh";
}

function c(input: HealthMapComponentView): HealthMapComponentView {
  return input;
}

function serviceStatus(health: SystemHealthResponse | null, name: string): HealthMapStatus {
  const s = health?.services?.find((x) => x.name === name);
  if (!s) return "unknown";
  const norm = String(s.status || "").toLowerCase();
  if (norm === "ok" || norm === "warn" || norm === "fail" || norm === "unknown") return norm as HealthMapStatus;
  return s.ready === true ? "ok" : "warn";
}

export function buildHealthMapViewModel(input: {
  health: SystemHealthResponse | null;
  runtime: LiveBrokerRuntimeItem | null;
}): HealthMapView {
  const { health, runtime } = input;
  const nowIso = new Date().toISOString();
  const components: HealthMapComponentView[] = [];

  const candleFreshness = freshnessFromTs(health?.data_freshness?.last_candle_ts_ms, 90_000);
  const signalFreshness = freshnessFromTs(health?.data_freshness?.last_signal_ts_ms, 120_000);
  const newsFreshness = freshnessFromTs(health?.data_freshness?.last_news_ts_ms, 30 * 60_000);
  const reconcileStatus = (runtime?.status ?? "").toLowerCase();
  const reconcileFreshness: HealthMapFreshness =
    reconcileStatus === "ok" ? "fresh" : reconcileStatus === "fail" ? "stale" : "missing";

  const dbStatus = health ? ((health.database === "ok" ? "ok" : "fail") as HealthMapStatus) : "unknown";
  const redisStatus = health
    ? ((health.redis === "ok" ? "ok" : health.redis ? "fail" : "unknown") as HealthMapStatus)
    : "unknown";
  const liveUnknown = !runtime || reconcileStatus === "unknown";
  const runtimeWarn = runtime?.operator_live_submission?.lane === "live_lane_degraded_reconcile";

  components.push(
    c({
      komponente: "API-Gateway",
      status: health ? "ok" : "unknown",
      freshness_status: "not_applicable",
      live_auswirkung_de: health ? "Gateway antwortet." : "Gateway-Daten fehlen; Live fail-closed.",
      blockiert_live: !health,
      letzter_erfolg_ts: health ? nowIso : null,
      letzter_fehler_ts: health ? null : nowIso,
      fehlergrund_de: health ? "" : "System-Health nicht erreichbar.",
      nächster_schritt_de: health ? "Weiter mit Datenfluss-Prüfung." : "Gateway/BFF-Verbindung prüfen.",
    }),
    c({
      komponente: "Dashboard/BFF",
      status: health ? "ok" : "unknown",
      freshness_status: "not_applicable",
      live_auswirkung_de: health ? "BFF liefert Health-Payload." : "BFF nicht verifiziert.",
      blockiert_live: !health,
      letzter_erfolg_ts: health ? nowIso : null,
      letzter_fehler_ts: health ? null : nowIso,
      fehlergrund_de: health ? "" : "Keine BFF-Daten für Main Console.",
      nächster_schritt_de: "BFF-Route /api/dashboard/gateway prüfen.",
    }),
    c({
      komponente: "Market-Stream",
      status: candleFreshness === "fresh" ? "ok" : "fail",
      freshness_status: candleFreshness,
      live_auswirkung_de:
        candleFreshness === "fresh"
          ? "Marktdaten frisch."
          : "Stale Market Data blockiert signalbasiertes Live.",
      blockiert_live: candleFreshness !== "fresh",
      letzter_erfolg_ts: health?.data_freshness?.last_candle_ts_ms
        ? new Date(health.data_freshness.last_candle_ts_ms).toISOString()
        : null,
      letzter_fehler_ts: candleFreshness === "fresh" ? null : nowIso,
      fehlergrund_de: candleFreshness === "fresh" ? "" : "Candles stale oder fehlen.",
      nächster_schritt_de: "Market-Stream/Bitget-Public prüfen, dann Signalpfad neu bewerten.",
    }),
    c({
      komponente: "Feature-Engine",
      status: serviceStatus(health, "feature_engine"),
      freshness_status: signalFreshness,
      live_auswirkung_de: "Feature-Berechnung beeinflusst Signalqualität.",
      blockiert_live: signalFreshness !== "fresh",
      letzter_erfolg_ts: health?.data_freshness?.last_signal_ts_ms
        ? new Date(health.data_freshness.last_signal_ts_ms).toISOString()
        : null,
      letzter_fehler_ts: signalFreshness === "fresh" ? null : nowIso,
      fehlergrund_de: signalFreshness === "fresh" ? "" : "Feature-/Signal-Daten stale/missing.",
      nächster_schritt_de: "Feature-Queue und Upstream-Lag prüfen.",
    }),
    c({
      komponente: "Signal-Engine",
      status: signalFreshness === "fresh" ? "ok" : "fail",
      freshness_status: signalFreshness,
      live_auswirkung_de:
        signalFreshness === "fresh" ? "Signale sind aktuell." : "Stale Signale blockieren signalbasiertes Live.",
      blockiert_live: signalFreshness !== "fresh",
      letzter_erfolg_ts: health?.data_freshness?.last_signal_ts_ms
        ? new Date(health.data_freshness.last_signal_ts_ms).toISOString()
        : null,
      letzter_fehler_ts: signalFreshness === "fresh" ? null : nowIso,
      fehlergrund_de: signalFreshness === "fresh" ? "" : "Signal-Frische unzureichend.",
      nächster_schritt_de: "Signal-Engine und Eventbus-Lag prüfen.",
    }),
    c({
      komponente: "Paper-Broker",
      status: health ? "ok" : "unknown",
      freshness_status: "not_applicable",
      live_auswirkung_de: "Paper ist Referenzpfad; blockiert Live nicht direkt.",
      blockiert_live: false,
      letzter_erfolg_ts: health ? nowIso : null,
      letzter_fehler_ts: null,
      fehlergrund_de: "",
      nächster_schritt_de: "Bei Drift Paper vs Live Vergleich nutzen.",
    }),
    c({
      komponente: "Live-Broker",
      status: liveUnknown ? "unknown" : runtimeWarn ? "warn" : "ok",
      freshness_status: reconcileFreshness,
      live_auswirkung_de: liveUnknown
        ? "Live-Broker unknown blockiert Live."
        : runtimeWarn
          ? "Live-Broker degradiert."
          : "Live-Broker verfügbar.",
      blockiert_live: liveUnknown,
      letzter_erfolg_ts: runtime?.created_ts ?? null,
      letzter_fehler_ts: liveUnknown ? nowIso : null,
      fehlergrund_de: liveUnknown ? "Runtime fehlt oder unknown." : "",
      nächster_schritt_de: "Live-Broker-Runtime und Reconcile prüfen.",
    }),
    c({
      komponente: "Alert-/Monitor-Engine",
      status: health && (health.ops.alert_engine.outbox_failed ?? 0) > 0 ? "warn" : health ? "ok" : "unknown",
      freshness_status: "not_applicable",
      live_auswirkung_de: "Alerts stützen Eskalation; Ausfall blockiert nicht direkt.",
      blockiert_live: false,
      letzter_erfolg_ts: health ? nowIso : null,
      letzter_fehler_ts: health && (health.ops.alert_engine.outbox_failed ?? 0) > 0 ? nowIso : null,
      fehlergrund_de: health && (health.ops.alert_engine.outbox_failed ?? 0) > 0 ? "Outbox-Fehler vorhanden." : "",
      nächster_schritt_de: "Outbox-Retry und Monitor-Lieferung prüfen.",
    }),
    c({
      komponente: "Redis/Eventbus",
      status: redisStatus,
      freshness_status: "not_applicable",
      live_auswirkung_de:
        redisStatus === "ok"
          ? "Eventbus verfügbar."
          : "Fehlender Redis/Eventbus blockiert Live bei Shadow-Match/Liquidity/Signals.",
      blockiert_live: redisStatus !== "ok",
      letzter_erfolg_ts: redisStatus === "ok" ? nowIso : null,
      letzter_fehler_ts: redisStatus === "ok" ? null : nowIso,
      fehlergrund_de: redisStatus === "ok" ? "" : "Redis nicht ok oder unknown.",
      nächster_schritt_de: "Redis-Health, Streams und Verbindungsweg prüfen.",
    }),
    c({
      komponente: "Postgres",
      status: dbStatus,
      freshness_status: "not_applicable",
      live_auswirkung_de:
        dbStatus === "ok"
          ? "DB verfügbar."
          : "Fehlende DB blockiert alle livekritischen Pfade.",
      blockiert_live: dbStatus !== "ok",
      letzter_erfolg_ts: dbStatus === "ok" ? nowIso : null,
      letzter_fehler_ts: dbStatus === "ok" ? null : nowIso,
      fehlergrund_de: dbStatus === "ok" ? "" : "Database-Health nicht ok.",
      nächster_schritt_de: "DB/Schema-Health prüfen und wiederherstellen.",
    }),
    c({
      komponente: "Bitget Public API",
      status: runtime?.bitget_private_status?.public_api_ok === true ? "ok" : "unknown",
      freshness_status: candleFreshness,
      live_auswirkung_de: "Public API beeinflusst Marktdaten und Frische.",
      blockiert_live: candleFreshness !== "fresh",
      letzter_erfolg_ts: runtime?.created_ts ?? null,
      letzter_fehler_ts: candleFreshness === "fresh" ? null : nowIso,
      fehlergrund_de: candleFreshness === "fresh" ? "" : "Public-Market-Feed stale/missing.",
      nächster_schritt_de: "Bitget Public-Konnektion und Stream prüfen.",
    }),
    c({
      komponente: "Bitget Private Read-only",
      status:
        runtime?.bitget_private_status?.private_api_configured === true &&
        runtime?.bitget_private_status?.private_auth_ok === true
          ? "ok"
          : "unknown",
      freshness_status: "not_applicable",
      live_auswirkung_de: "Private Read-only ist Basis für Exchange-Truth.",
      blockiert_live: runtime?.upstream_ok !== true,
      letzter_erfolg_ts: runtime?.created_ts ?? null,
      letzter_fehler_ts: runtime?.upstream_ok === true ? null : nowIso,
      fehlergrund_de: runtime?.upstream_ok === true ? "" : "Exchange-Truth fehlt oder private Auth ungeklärt.",
      nächster_schritt_de: "Private Auth/Readonly-Pfad prüfen (ohne Secrets).",
    }),
    c({
      komponente: "LLM-Orchestrator",
      status: serviceStatus(health, "llm_orchestrator"),
      freshness_status: "not_applicable",
      live_auswirkung_de: "LLM-Ausfall degradiert Erklärungen, blockiert Safety nicht.",
      blockiert_live: false,
      letzter_erfolg_ts: health ? nowIso : null,
      letzter_fehler_ts: serviceStatus(health, "llm_orchestrator") === "ok" ? null : nowIso,
      fehlergrund_de: serviceStatus(health, "llm_orchestrator") === "ok" ? "" : "LLM nicht verfügbar oder unbekannt.",
      nächster_schritt_de: "Erklärungsdienste beobachten, Live-Safety separat bewerten.",
    }),
    c({
      komponente: "News-Engine",
      status: newsFreshness === "missing" ? "unknown" : newsFreshness === "stale" ? "warn" : "ok",
      freshness_status: newsFreshness,
      live_auswirkung_de: "News beeinflusst Kontexterklärung, nicht den harten Safety-Kern.",
      blockiert_live: false,
      letzter_erfolg_ts: health?.data_freshness?.last_news_ts_ms
        ? new Date(health.data_freshness.last_news_ts_ms).toISOString()
        : null,
      letzter_fehler_ts: newsFreshness === "fresh" ? null : nowIso,
      fehlergrund_de: newsFreshness === "fresh" ? "" : "News stale/missing.",
      nächster_schritt_de: "News-Fetch und Zeitstempel prüfen.",
    }),
    c({
      komponente: "Asset-Katalog",
      status: runtime?.instrument_catalog?.status === "ok" ? "ok" : runtime?.instrument_catalog ? "warn" : "unknown",
      freshness_status:
        runtime?.instrument_catalog?.fetch_completed_ts_ms == null
          ? "missing"
          : freshnessFromTs(runtime.instrument_catalog.fetch_completed_ts_ms, 15 * 60_000),
      live_auswirkung_de: "Asset-Katalog steuert Asset-Freigaben und Blocker.",
      blockiert_live: Boolean(runtime?.instrument_catalog?.errors?.length),
      letzter_erfolg_ts: runtime?.instrument_catalog?.fetch_completed_ts_ms
        ? new Date(runtime.instrument_catalog.fetch_completed_ts_ms).toISOString()
        : null,
      letzter_fehler_ts: runtime?.instrument_catalog?.errors?.length ? nowIso : null,
      fehlergrund_de: runtime?.instrument_catalog?.errors?.length
        ? redact(runtime.instrument_catalog.errors.join("; "))
        : "",
      nächster_schritt_de: "Katalog-Refresh und Asset-Gates prüfen.",
    }),
    c({
      komponente: "Reconcile",
      status: reconcileStatus === "ok" ? "ok" : reconcileStatus === "fail" ? "fail" : "unknown",
      freshness_status: reconcileFreshness,
      live_auswirkung_de:
        reconcileFreshness === "fresh"
          ? "Reconcile aktuell."
          : "Stale Reconcile blockiert Live-Openings.",
      blockiert_live: reconcileFreshness !== "fresh",
      letzter_erfolg_ts: runtime?.created_ts ?? null,
      letzter_fehler_ts: reconcileFreshness === "fresh" ? null : nowIso,
      fehlergrund_de: reconcileFreshness === "fresh" ? "" : `Reconcile-Status=${reconcileStatus || "unknown"}`,
      nächster_schritt_de: "Reconcile-Lauf und Drift-Details prüfen.",
    }),
    c({
      komponente: "Shadow-Burn-in Evidence",
      status: runtime?.shadow_path_active ? "ok" : "warn",
      freshness_status: "not_applicable",
      live_auswirkung_de: "Shadow-Evidence fehlt -> Live-Freigabe riskant.",
      blockiert_live: !runtime?.shadow_path_active,
      letzter_erfolg_ts: runtime?.created_ts ?? null,
      letzter_fehler_ts: runtime?.shadow_path_active ? null : nowIso,
      fehlergrund_de: runtime?.shadow_path_active ? "" : "Shadow-Pfad nicht aktiv.",
      nächster_schritt_de: "Shadow-Burn-in Nachweise aktualisieren.",
    }),
    c({
      komponente: "Restore/Safety Evidence",
      status: serviceStatus(health, "recovery"),
      freshness_status: "not_applicable",
      live_auswirkung_de: "Restore/Safety-Evidence beeinflusst Go/No-Go.",
      blockiert_live: false,
      letzter_erfolg_ts: health ? nowIso : null,
      letzter_fehler_ts: serviceStatus(health, "recovery") === "ok" ? null : nowIso,
      fehlergrund_de: serviceStatus(health, "recovery") === "ok" ? "" : "Restore-Evidence nicht bestätigt.",
      nächster_schritt_de: "DR-/Restore-Test-Evidence prüfen.",
    }),
  );

  const blocker = components
    .filter((x) => x.blockiert_live)
    .map((x) => `${x.komponente}: ${x.live_auswirkung_de}`);

  const sorted = [...components].sort((a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status]);
  const anyFail = sorted.some((x) => x.status === "fail");
  const anyUnknown = sorted.some((x) => x.status === "unknown");
  const anyWarn = sorted.some((x) => x.status === "warn");
  const gesamtstatus: HealthMapStatus = anyFail ? "fail" : anyUnknown ? "unknown" : anyWarn ? "warn" : "ok";

  return {
    gesamtstatus,
    live_blockiert: blocker.length > 0,
    live_sicher: blocker.length === 0 && gesamtstatus === "ok",
    blocker_gründe_de: blocker,
    komponenten: sorted,
  };
}
