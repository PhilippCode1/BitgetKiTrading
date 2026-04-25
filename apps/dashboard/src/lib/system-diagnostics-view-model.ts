import type {
  LiveBrokerRuntimeItem,
  LiveStateResponse,
  MonitorAlertItem,
  SystemHealthResponse,
} from "@/lib/types";

export type SystemOverallStatus = "OK" | "Warnung" | "Blockiert";

export type StaleCheckItem = {
  key:
    | "candles"
    | "orderbook"
    | "signals"
    | "reconcile"
    | "worker_heartbeat";
  label: string;
  stale: boolean;
  detail: string;
};

export type SystemDiagnosticsViewModel = {
  overallStatus: SystemOverallStatus;
  summaryReasons: string[];
  serviceStatus: Array<{ name: string; status: string; detail: string }>;
  dataSources: Array<{ name: string; status: string }>;
  dbStatus: string;
  redisStatus: string;
  bitgetPublicStatus: string;
  bitgetPrivateStatus: string;
  llmStatus: string;
  newsStatus: string;
  alertStatus: string;
  staleChecks: StaleCheckItem[];
  latestCriticalErrors: string[];
  latestSuccessfulChecks: string[];
};

const SECRET_RE =
  /\bauthorization\b\s*[:=]\s*bearer\s+\S+|\b(bearer|token|secret|api[_-]?key|password)\b\s*[:=]\s*\S+/gi;

export function redactDiagnosticError(raw: string | null | undefined): string {
  if (!raw) return "";
  return raw.slice(0, 240).replace(SECRET_RE, "$1=***");
}

function staleFromAge(ageMs: number | null | undefined, maxAgeMs: number): boolean {
  if (ageMs == null) return true;
  return ageMs > maxAgeMs;
}

function reconcileIsStale(health: SystemHealthResponse | null): boolean {
  const s = health?.ops?.live_broker?.latest_reconcile_status;
  return !s || s !== "ok";
}

function workerHeartbeatStale(health: SystemHealthResponse | null): boolean {
  if (!health) return true;
  const now = Date.now();
  const staleThreshold = 10 * 60_000;
  const candidates = health.services
    .map((s) => s.last_run_ts_ms)
    .filter((v): v is number => typeof v === "number");
  if (candidates.length === 0) return true;
  return candidates.some((ts) => now - ts > staleThreshold);
}

export function buildSystemDiagnosticsViewModel(input: {
  health: SystemHealthResponse | null;
  runtime: LiveBrokerRuntimeItem | null;
  liveState: LiveStateResponse | null;
  openAlerts: readonly MonitorAlertItem[];
  healthEndpointWired: boolean;
}): SystemDiagnosticsViewModel {
  const { health, runtime, liveState, openAlerts, healthEndpointWired } = input;
  const now = Date.now();
  const candleTs = health?.data_freshness?.last_candle_ts_ms ?? null;
  const signalTs = health?.data_freshness?.last_signal_ts_ms ?? null;
  const candlesStale = candleTs == null ? true : now - candleTs > 90_000;
  const signalsStale = signalTs == null ? true : now - signalTs > 120_000;
  const orderbookStale = staleFromAge(liveState?.latest_feature?.orderbook_age_ms, 90_000);
  const reconcileStale = reconcileIsStale(health);
  const heartbeatStale = workerHeartbeatStale(health);

  const staleChecks: StaleCheckItem[] = [
    {
      key: "candles",
      label: "Candles stale",
      stale: candlesStale,
      detail: candlesStale ? "Candles sind stale oder fehlen." : "Candles sind frisch.",
    },
    {
      key: "orderbook",
      label: "Orderbook stale",
      stale: orderbookStale,
      detail: orderbookStale
        ? "Orderbook-Alter ueber Grenzwert oder nicht verfuegbar."
        : "Orderbook ist aktuell.",
    },
    {
      key: "signals",
      label: "Signals stale",
      stale: signalsStale,
      detail: signalsStale ? "Signal-Zeitstempel ist stale/missing." : "Signale sind aktuell.",
    },
    {
      key: "reconcile",
      label: "Reconcile stale",
      stale: reconcileStale,
      detail: reconcileStale ? "Reconcile nicht ok oder unbekannt." : "Reconcile ist ok.",
    },
    {
      key: "worker_heartbeat",
      label: "Worker heartbeat stale",
      stale: heartbeatStale,
      detail: heartbeatStale
        ? "Mindestens ein Service-Heartbeat ist stale oder fehlt."
        : "Worker-Heartbeats sind im erwarteten Fenster.",
    },
  ];

  const criticalDown =
    !healthEndpointWired ||
    !health ||
    health.database !== "ok" ||
    health.redis !== "ok" ||
    runtime?.upstream_ok === false;
  const hasStaleCritical = staleChecks.some((x) => x.stale);
  const hasOpenCriticalAlerts = openAlerts.some((a) =>
    ["critical", "p0", "p1"].includes((a.severity || "").toLowerCase()),
  );

  const overallStatus: SystemOverallStatus = criticalDown
    ? "Blockiert"
    : hasStaleCritical || hasOpenCriticalAlerts
      ? "Warnung"
      : "OK";

  const reasons: string[] = [];
  if (!healthEndpointWired) reasons.push("Health-Endpunkt ist nicht verdrahtet.");
  if (!health) reasons.push("System-Health nicht lesbar.");
  if (health?.database !== "ok") reasons.push("Postgres nicht ok.");
  if (health?.redis !== "ok") reasons.push("Redis/Eventbus nicht ok.");
  if (runtime?.upstream_ok === false) reasons.push("Bitget Private nicht erreichbar.");
  if (hasStaleCritical) reasons.push("Stale-Daten erkannt.");
  if (hasOpenCriticalAlerts) reasons.push("Kritische Alerts sind offen.");

  const serviceStatus = (health?.services ?? []).map((s) => ({
    name: s.name,
    status: s.status || "unknown",
    detail:
      s.last_error != null
        ? redactDiagnosticError(s.last_error)
        : s.note || "Kein Zusatzdetail.",
  }));

  const latestCriticalErrors = (health?.services ?? [])
    .filter((s) => s.last_error)
    .map((s) => `${s.name}: ${redactDiagnosticError(s.last_error)}`)
    .slice(0, 6);

  const latestSuccessfulChecks = (health?.services ?? [])
    .filter((s) => s.ready === true || s.status === "ok")
    .map((s) => `${s.name}: letzter Check ok`)
    .slice(0, 6);

  return {
    overallStatus,
    summaryReasons: reasons.length > 0 ? reasons : ["Keine kritischen Probleme erkannt."],
    serviceStatus,
    dataSources: [
      { name: "Market-Stream", status: candlesStale ? "stale" : "ok" },
      { name: "Signal-Pipeline", status: signalsStale ? "stale" : "ok" },
      { name: "Orderbook", status: orderbookStale ? "stale" : "ok" },
      { name: "Reconcile", status: reconcileStale ? "stale" : "ok" },
    ],
    dbStatus: health?.database ?? "nicht verdrahtet",
    redisStatus: health?.redis ?? "nicht verdrahtet",
    bitgetPublicStatus:
      runtime?.bitget_private_status?.public_api_ok == null
        ? "unbekannt"
        : String(runtime.bitget_private_status.public_api_ok),
    bitgetPrivateStatus:
      runtime?.bitget_private_status?.private_auth_ok == null
        ? "unbekannt"
        : String(runtime.bitget_private_status.private_auth_ok),
    llmStatus: (health?.services ?? []).some((s) => s.name === "llm_orchestrator" && s.status === "ok")
      ? "ok"
      : "warnung/unknown",
    newsStatus: health?.data_freshness?.last_news_ts_ms ? "ok" : "unknown",
    alertStatus: `offen: ${openAlerts.length}`,
    staleChecks,
    latestCriticalErrors:
      latestCriticalErrors.length > 0
        ? latestCriticalErrors
        : ["Keine kritischen Fehlerdetails gemeldet."],
    latestSuccessfulChecks:
      latestSuccessfulChecks.length > 0
        ? latestSuccessfulChecks
        : ["Keine erfolgreichen Checks gemeldet."],
  };
}
