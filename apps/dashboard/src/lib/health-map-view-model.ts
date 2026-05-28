import type { LiveBrokerRuntimeItem, SystemHealthResponse } from "@/lib/types";

export type HealthMapStatus = "ok" | "warn" | "fail" | "unknown";
export type HealthMapFreshness =
  | "fresh"
  | "stale"
  | "missing"
  | "not_applicable";

export type HealthMapComponentView = Readonly<{
  komponente: string;
  status: HealthMapStatus;
  freshness_status: HealthMapFreshness;
  live_auswirkung_de: string;
  live_auswirkung_en: string;
  blockiert_live: boolean;
  letzter_erfolg_ts: string | null;
  letzter_fehler_ts: string | null;
  fehlergrund_de: string;
  fehlergrund_en: string;
  nächster_schritt_de: string;
  nächster_schritt_en: string;
}>;

export type HealthMapView = Readonly<{
  gesamtstatus: HealthMapStatus;
  live_blockiert: boolean;
  live_sicher: boolean;
  blocker_gründe_de: readonly string[];
  blocker_gründe_en: readonly string[];
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

function freshnessFromTs(
  tsMs: number | null | undefined,
  staleAfterMs: number,
): HealthMapFreshness {
  if (tsMs == null) return "missing";
  const age = Date.now() - tsMs;
  return age > staleAfterMs ? "stale" : "fresh";
}

type CInput = Omit<
  HealthMapComponentView,
  "live_auswirkung_en" | "fehlergrund_en" | "nächster_schritt_en"
> & {
  live_auswirkung_en?: string;
  fehlergrund_en?: string;
  nächster_schritt_en?: string;
};

function c(input: CInput): HealthMapComponentView {
  return {
    ...input,
    live_auswirkung_en: input.live_auswirkung_en ?? input.live_auswirkung_de,
    fehlergrund_en: input.fehlergrund_en ?? input.fehlergrund_de,
    nächster_schritt_en: input.nächster_schritt_en ?? input.nächster_schritt_de,
  };
}

function serviceStatus(
  health: SystemHealthResponse | null,
  name: string,
): HealthMapStatus {
  const s = health?.services?.find((x) => x.name === name);
  if (!s) return "unknown";
  const norm = String(s.status || "").toLowerCase();
  if (norm === "ok" || norm === "warn" || norm === "fail" || norm === "unknown")
    return norm as HealthMapStatus;
  return s.ready === true ? "ok" : "warn";
}

export function buildHealthMapViewModel(input: {
  health: SystemHealthResponse | null;
  runtime: LiveBrokerRuntimeItem | null;
}): HealthMapView {
  const { health, runtime } = input;
  const nowIso = new Date().toISOString();
  const components: HealthMapComponentView[] = [];

  const candleFreshness = freshnessFromTs(
    health?.data_freshness?.last_candle_ts_ms,
    90_000,
  );
  const signalFreshness = freshnessFromTs(
    health?.data_freshness?.last_signal_ts_ms,
    120_000,
  );
  const newsFreshness = freshnessFromTs(
    health?.data_freshness?.last_news_ts_ms,
    30 * 60_000,
  );
  const reconcileStatus = (runtime?.status ?? "").toLowerCase();
  const reconcileFreshness: HealthMapFreshness =
    reconcileStatus === "ok"
      ? "fresh"
      : reconcileStatus === "fail"
        ? "stale"
        : "missing";

  const dbStatus = health
    ? ((health.database === "ok" ? "ok" : "fail") as HealthMapStatus)
    : "unknown";
  const redisStatus = health
    ? ((health.redis === "ok"
        ? "ok"
        : health.redis
          ? "fail"
          : "unknown") as HealthMapStatus)
    : "unknown";
  const liveUnknown = !runtime || reconcileStatus === "unknown";
  const runtimeWarn =
    runtime?.operator_live_submission?.lane === "live_lane_degraded_reconcile";

  components.push(
    c({
      komponente: "API-Gateway",
      status: health ? "ok" : "unknown",
      freshness_status: "not_applicable",
      live_auswirkung_de: health
        ? "Gateway antwortet."
        : "Gateway-Daten fehlen; Live fail-closed.",
      live_auswirkung_en: health
        ? "Gateway is responding."
        : "Gateway data missing; live fail-closed.",
      blockiert_live: !health,
      letzter_erfolg_ts: health ? nowIso : null,
      letzter_fehler_ts: health ? null : nowIso,
      fehlergrund_de: health ? "" : "System-Health nicht erreichbar.",
      fehlergrund_en: health ? "" : "System health unreachable.",
      nächster_schritt_de: health
        ? "Weiter mit Datenfluss-Prüfung."
        : "Gateway/BFF-Verbindung prüfen.",
      nächster_schritt_en: health
        ? "Continue with data-flow checks."
        : "Check gateway/BFF connectivity.",
    }),
    c({
      komponente: "Dashboard/BFF",
      status: health ? "ok" : "unknown",
      freshness_status: "not_applicable",
      live_auswirkung_de: health
        ? "BFF liefert Health-Payload."
        : "BFF nicht verifiziert.",
      live_auswirkung_en: health
        ? "BFF delivers health payload."
        : "BFF not verified.",
      blockiert_live: !health,
      letzter_erfolg_ts: health ? nowIso : null,
      letzter_fehler_ts: health ? null : nowIso,
      fehlergrund_de: health ? "" : "Keine BFF-Daten für Main Console.",
      fehlergrund_en: health ? "" : "No BFF data for main console.",
      nächster_schritt_de: "BFF-Route /api/dashboard/gateway prüfen.",
      nächster_schritt_en: "Check BFF route /api/dashboard/gateway.",
    }),
    c({
      komponente: "Market-Stream",
      status: candleFreshness === "fresh" ? "ok" : "fail",
      freshness_status: candleFreshness,
      live_auswirkung_de:
        candleFreshness === "fresh"
          ? "Marktdaten frisch."
          : "Stale Market Data blockiert signalbasiertes Live.",
      live_auswirkung_en:
        candleFreshness === "fresh"
          ? "Market data is fresh."
          : "Stale market data blocks signal-driven live.",
      blockiert_live: candleFreshness !== "fresh",
      letzter_erfolg_ts: health?.data_freshness?.last_candle_ts_ms
        ? new Date(health.data_freshness.last_candle_ts_ms).toISOString()
        : null,
      letzter_fehler_ts: candleFreshness === "fresh" ? null : nowIso,
      fehlergrund_de:
        candleFreshness === "fresh" ? "" : "Candles stale oder fehlen.",
      fehlergrund_en:
        candleFreshness === "fresh" ? "" : "Candles stale or missing.",
      nächster_schritt_de:
        "Market-Stream/Bitget-Public prüfen, dann Signalpfad neu bewerten.",
      nächster_schritt_en:
        "Check market stream/Bitget public, then re-evaluate signal path.",
    }),
    c({
      komponente: "Feature-Engine",
      status: serviceStatus(health, "feature_engine"),
      freshness_status: signalFreshness,
      live_auswirkung_de: "Feature-Berechnung beeinflusst Signalqualität.",
      live_auswirkung_en: "Feature computation affects signal quality.",
      blockiert_live: signalFreshness !== "fresh",
      letzter_erfolg_ts: health?.data_freshness?.last_signal_ts_ms
        ? new Date(health.data_freshness.last_signal_ts_ms).toISOString()
        : null,
      letzter_fehler_ts: signalFreshness === "fresh" ? null : nowIso,
      fehlergrund_de:
        signalFreshness === "fresh"
          ? ""
          : "Feature-/Signal-Daten stale/missing.",
      fehlergrund_en:
        signalFreshness === "fresh"
          ? ""
          : "Feature/signal data stale or missing.",
      nächster_schritt_de: "Feature-Queue und Upstream-Lag prüfen.",
      nächster_schritt_en: "Check feature queue and upstream lag.",
    }),
    c({
      komponente: "Signal-Engine",
      status: signalFreshness === "fresh" ? "ok" : "fail",
      freshness_status: signalFreshness,
      live_auswirkung_de:
        signalFreshness === "fresh"
          ? "Signale sind aktuell."
          : "Stale Signale blockieren signalbasiertes Live.",
      live_auswirkung_en:
        signalFreshness === "fresh"
          ? "Signals are current."
          : "Stale signals block signal-driven live.",
      blockiert_live: signalFreshness !== "fresh",
      letzter_erfolg_ts: health?.data_freshness?.last_signal_ts_ms
        ? new Date(health.data_freshness.last_signal_ts_ms).toISOString()
        : null,
      letzter_fehler_ts: signalFreshness === "fresh" ? null : nowIso,
      fehlergrund_de:
        signalFreshness === "fresh" ? "" : "Signal-Frische unzureichend.",
      fehlergrund_en:
        signalFreshness === "fresh" ? "" : "Signal freshness insufficient.",
      nächster_schritt_de: "Signal-Engine und Eventbus-Lag prüfen.",
      nächster_schritt_en: "Check signal engine and event-bus lag.",
    }),
    c({
      komponente: "Paper-Broker",
      status: health ? "ok" : "unknown",
      freshness_status: "not_applicable",
      live_auswirkung_de:
        "Paper ist Referenzpfad; blockiert Live nicht direkt.",
      live_auswirkung_en:
        "Paper is a reference path; does not block live directly.",
      blockiert_live: false,
      letzter_erfolg_ts: health ? nowIso : null,
      letzter_fehler_ts: null,
      fehlergrund_de: "",
      fehlergrund_en: "",
      nächster_schritt_de: "Bei Drift Paper vs Live Vergleich nutzen.",
      nächster_schritt_en: "Use paper vs live comparison when drift is suspected.",
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
      live_auswirkung_en: liveUnknown
        ? "Live-broker unknown blocks live."
        : runtimeWarn
          ? "Live-broker degraded."
          : "Live-broker available.",
      blockiert_live: liveUnknown,
      letzter_erfolg_ts: runtime?.created_ts ?? null,
      letzter_fehler_ts: liveUnknown ? nowIso : null,
      fehlergrund_de: liveUnknown ? "Runtime fehlt oder unknown." : "",
      fehlergrund_en: liveUnknown ? "Runtime missing or unknown." : "",
      nächster_schritt_de: "Live-Broker-Runtime und Reconcile prüfen.",
      nächster_schritt_en: "Check live-broker runtime and reconcile.",
    }),
    c({
      komponente: "Alert-/Monitor-Engine",
      status:
        health && (health.ops.alert_engine.outbox_failed ?? 0) > 0
          ? "warn"
          : health
            ? "ok"
            : "unknown",
      freshness_status: "not_applicable",
      live_auswirkung_de:
        "Alerts stützen Eskalation; Ausfall blockiert nicht direkt.",
      live_auswirkung_en:
        "Alerts support escalation; outage does not block live directly.",
      blockiert_live: false,
      letzter_erfolg_ts: health ? nowIso : null,
      letzter_fehler_ts:
        health && (health.ops.alert_engine.outbox_failed ?? 0) > 0
          ? nowIso
          : null,
      fehlergrund_de:
        health && (health.ops.alert_engine.outbox_failed ?? 0) > 0
          ? "Outbox-Fehler vorhanden."
          : "",
      fehlergrund_en:
        health && (health.ops.alert_engine.outbox_failed ?? 0) > 0
          ? "Outbox errors present."
          : "",
      nächster_schritt_de: "Outbox-Retry und Monitor-Lieferung prüfen.",
      nächster_schritt_en: "Check outbox retry and monitor delivery.",
    }),
    c({
      komponente: "Redis/Eventbus",
      status: redisStatus,
      freshness_status: "not_applicable",
      live_auswirkung_de:
        redisStatus === "ok"
          ? "Eventbus verfügbar."
          : "Fehlender Redis/Eventbus blockiert Live bei Shadow-Match/Liquidity/Signals.",
      live_auswirkung_en:
        redisStatus === "ok"
          ? "Event bus available."
          : "Missing Redis/event bus blocks live for shadow-match/liquidity/signals.",
      blockiert_live: redisStatus !== "ok",
      letzter_erfolg_ts: redisStatus === "ok" ? nowIso : null,
      letzter_fehler_ts: redisStatus === "ok" ? null : nowIso,
      fehlergrund_de:
        redisStatus === "ok" ? "" : "Redis nicht ok oder unknown.",
      fehlergrund_en:
        redisStatus === "ok" ? "" : "Redis not ok or unknown.",
      nächster_schritt_de: "Redis-Health, Streams und Verbindungsweg prüfen.",
      nächster_schritt_en: "Check Redis health, streams, and connectivity.",
    }),
    c({
      komponente: "Postgres",
      status: dbStatus,
      freshness_status: "not_applicable",
      live_auswirkung_de:
        dbStatus === "ok"
          ? "DB verfügbar."
          : "Fehlende DB blockiert alle livekritischen Pfade.",
      live_auswirkung_en:
        dbStatus === "ok"
          ? "DB available."
          : "Missing DB blocks all live-critical paths.",
      blockiert_live: dbStatus !== "ok",
      letzter_erfolg_ts: dbStatus === "ok" ? nowIso : null,
      letzter_fehler_ts: dbStatus === "ok" ? null : nowIso,
      fehlergrund_de: dbStatus === "ok" ? "" : "Database-Health nicht ok.",
      fehlergrund_en: dbStatus === "ok" ? "" : "Database health not ok.",
      nächster_schritt_de: "DB/Schema-Health prüfen und wiederherstellen.",
      nächster_schritt_en: "Check and restore DB/schema health.",
    }),
    c({
      komponente: "Bitget Public API",
      status:
        runtime?.bitget_private_status?.public_api_ok === true
          ? "ok"
          : "unknown",
      freshness_status: candleFreshness,
      live_auswirkung_de: "Public API beeinflusst Marktdaten und Frische.",
      live_auswirkung_en: "Public API affects market data and freshness.",
      blockiert_live: candleFreshness !== "fresh",
      letzter_erfolg_ts: runtime?.created_ts ?? null,
      letzter_fehler_ts: candleFreshness === "fresh" ? null : nowIso,
      fehlergrund_de:
        candleFreshness === "fresh" ? "" : "Public-Market-Feed stale/missing.",
      fehlergrund_en:
        candleFreshness === "fresh" ? "" : "Public market feed stale or missing.",
      nächster_schritt_de: "Bitget Public-Konnektion und Stream prüfen.",
      nächster_schritt_en: "Check Bitget public connection and stream.",
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
      live_auswirkung_en: "Private read-only is the basis for exchange truth.",
      blockiert_live: runtime?.upstream_ok !== true,
      letzter_erfolg_ts: runtime?.created_ts ?? null,
      letzter_fehler_ts: runtime?.upstream_ok === true ? null : nowIso,
      fehlergrund_de:
        runtime?.upstream_ok === true
          ? ""
          : "Exchange-Truth fehlt oder private Auth ungeklärt.",
      fehlergrund_en:
        runtime?.upstream_ok === true
          ? ""
          : "Exchange truth missing or private auth unclear.",
      nächster_schritt_de: "Private Auth/Readonly-Pfad prüfen (ohne Secrets).",
      nächster_schritt_en: "Check private auth/read-only path (no secrets).",
    }),
    c({
      komponente: "LLM-Orchestrator",
      status: serviceStatus(health, "llm_orchestrator"),
      freshness_status: "not_applicable",
      live_auswirkung_de:
        "LLM-Ausfall degradiert Erklärungen, blockiert Safety nicht.",
      live_auswirkung_en:
        "LLM outage degrades explanations; does not block safety.",
      blockiert_live: false,
      letzter_erfolg_ts: health ? nowIso : null,
      letzter_fehler_ts:
        serviceStatus(health, "llm_orchestrator") === "ok" ? null : nowIso,
      fehlergrund_de:
        serviceStatus(health, "llm_orchestrator") === "ok"
          ? ""
          : "LLM nicht verfügbar oder unbekannt.",
      fehlergrund_en:
        serviceStatus(health, "llm_orchestrator") === "ok"
          ? ""
          : "LLM unavailable or unknown.",
      nächster_schritt_de:
        "Erklärungsdienste beobachten, Live-Safety separat bewerten.",
      nächster_schritt_en:
        "Monitor explanation services; assess live safety separately.",
    }),
    c({
      komponente: "News-Engine",
      status:
        newsFreshness === "missing"
          ? "unknown"
          : newsFreshness === "stale"
            ? "warn"
            : "ok",
      freshness_status: newsFreshness,
      live_auswirkung_de:
        "News beeinflusst Kontexterklärung, nicht den harten Safety-Kern.",
      live_auswirkung_en:
        "News affects context explanations, not the hard safety core.",
      blockiert_live: false,
      letzter_erfolg_ts: health?.data_freshness?.last_news_ts_ms
        ? new Date(health.data_freshness.last_news_ts_ms).toISOString()
        : null,
      letzter_fehler_ts: newsFreshness === "fresh" ? null : nowIso,
      fehlergrund_de: newsFreshness === "fresh" ? "" : "News stale/missing.",
      fehlergrund_en: newsFreshness === "fresh" ? "" : "News stale or missing.",
      nächster_schritt_de: "News-Fetch und Zeitstempel prüfen.",
      nächster_schritt_en: "Check news fetch and timestamps.",
    }),
    c({
      komponente: "Asset-Katalog",
      status:
        runtime?.instrument_catalog?.status === "ok"
          ? "ok"
          : runtime?.instrument_catalog
            ? "warn"
            : "unknown",
      freshness_status:
        runtime?.instrument_catalog?.fetch_completed_ts_ms == null
          ? "missing"
          : freshnessFromTs(
              runtime.instrument_catalog.fetch_completed_ts_ms,
              15 * 60_000,
            ),
      live_auswirkung_de: "Asset-Katalog steuert Asset-Freigaben und Blocker.",
      live_auswirkung_en: "Asset catalog controls asset approvals and blockers.",
      blockiert_live: Boolean(runtime?.instrument_catalog?.errors?.length),
      letzter_erfolg_ts: runtime?.instrument_catalog?.fetch_completed_ts_ms
        ? new Date(
            runtime.instrument_catalog.fetch_completed_ts_ms,
          ).toISOString()
        : null,
      letzter_fehler_ts: runtime?.instrument_catalog?.errors?.length
        ? nowIso
        : null,
      fehlergrund_de: runtime?.instrument_catalog?.errors?.length
        ? redact(runtime.instrument_catalog.errors.join("; "))
        : "",
      fehlergrund_en: runtime?.instrument_catalog?.errors?.length
        ? redact(runtime.instrument_catalog.errors.join("; "))
        : "",
      nächster_schritt_de: "Katalog-Refresh und Asset-Gates prüfen.",
      nächster_schritt_en: "Check catalog refresh and asset gates.",
    }),
    c({
      komponente: "Reconcile",
      status:
        reconcileStatus === "ok"
          ? "ok"
          : reconcileStatus === "fail"
            ? "fail"
            : "unknown",
      freshness_status: reconcileFreshness,
      live_auswirkung_de:
        reconcileFreshness === "fresh"
          ? "Reconcile aktuell."
          : "Stale Reconcile blockiert Live-Openings.",
      live_auswirkung_en:
        reconcileFreshness === "fresh"
          ? "Reconcile is current."
          : "Stale reconcile blocks live openings.",
      blockiert_live: reconcileFreshness !== "fresh",
      letzter_erfolg_ts: runtime?.created_ts ?? null,
      letzter_fehler_ts: reconcileFreshness === "fresh" ? null : nowIso,
      fehlergrund_de:
        reconcileFreshness === "fresh"
          ? ""
          : `Reconcile-Status=${reconcileStatus || "unknown"}`,
      nächster_schritt_de: "Reconcile-Lauf und Drift-Details prüfen.",
    }),
    c({
      komponente: "Shadow-Burn-in Evidence",
      status: runtime?.shadow_path_active ? "ok" : "warn",
      freshness_status: "not_applicable",
      live_auswirkung_de: "Shadow-Evidence fehlt -> Live-Freigabe riskant.",
      live_auswirkung_en: "Shadow evidence missing → live approval risky.",
      blockiert_live: !runtime?.shadow_path_active,
      letzter_erfolg_ts: runtime?.created_ts ?? null,
      letzter_fehler_ts: runtime?.shadow_path_active ? null : nowIso,
      fehlergrund_de: runtime?.shadow_path_active
        ? ""
        : "Shadow-Pfad nicht aktiv.",
      fehlergrund_en: runtime?.shadow_path_active
        ? ""
        : "Shadow path not active.",
      nächster_schritt_de: "Shadow-Burn-in Nachweise aktualisieren.",
      nächster_schritt_en: "Update shadow burn-in evidence.",
    }),
    c({
      komponente: "Restore/Safety Evidence",
      status: serviceStatus(health, "recovery"),
      freshness_status: "not_applicable",
      live_auswirkung_de: "Restore/Safety-Evidence beeinflusst Go/No-Go.",
      live_auswirkung_en: "Restore/safety evidence affects go/no-go.",
      blockiert_live: false,
      letzter_erfolg_ts: health ? nowIso : null,
      letzter_fehler_ts:
        serviceStatus(health, "recovery") === "ok" ? null : nowIso,
      fehlergrund_de:
        serviceStatus(health, "recovery") === "ok"
          ? ""
          : "Restore-Evidence nicht bestätigt.",
      fehlergrund_en:
        serviceStatus(health, "recovery") === "ok"
          ? ""
          : "Restore evidence not confirmed.",
      nächster_schritt_de: "DR-/Restore-Test-Evidence prüfen.",
      nächster_schritt_en: "Check DR/restore test evidence.",
    }),
  );

  const blocking = components.filter((x) => x.blockiert_live);
  const blockerDe = blocking.map(
    (x) => `${x.komponente}: ${x.live_auswirkung_de}`,
  );
  const blockerEn = blocking.map(
    (x) => `${x.komponente}: ${x.live_auswirkung_en}`,
  );

  const sorted = [...components].sort(
    (a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status],
  );
  const anyFail = sorted.some((x) => x.status === "fail");
  const anyUnknown = sorted.some((x) => x.status === "unknown");
  const anyWarn = sorted.some((x) => x.status === "warn");
  const gesamtstatus: HealthMapStatus = anyFail
    ? "fail"
    : anyUnknown
      ? "unknown"
      : anyWarn
        ? "warn"
        : "ok";

  return {
    gesamtstatus,
    live_blockiert: blockerDe.length > 0,
    live_sicher: blockerDe.length === 0 && gesamtstatus === "ok",
    blocker_gründe_de: blockerDe,
    blocker_gründe_en: blockerEn,
    komponenten: sorted,
  };
}
