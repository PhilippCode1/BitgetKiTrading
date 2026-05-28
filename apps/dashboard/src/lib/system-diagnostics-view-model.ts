import type {
  LiveBrokerRuntimeItem,
  LiveStateResponse,
  MonitorAlertItem,
  SystemHealthResponse,
} from "@/lib/types";

export type SystemOverallStatus = "OK" | "Warnung" | "Blockiert";

export type StaleCheckItem = {
  key: "candles" | "orderbook" | "signals" | "reconcile" | "worker_heartbeat";
  stale: boolean;
};

export type SystemDiagnosticsReasonKey =
  | "healthEndpointUnwired"
  | "healthUnreadable"
  | "postgresNotOk"
  | "redisNotOk"
  | "bitgetPrivateUnreachable"
  | "staleDataDetected"
  | "criticalAlertsOpen"
  | "noCriticalIssues";

export type SystemDiagnosticsViewModel = {
  overallStatus: SystemOverallStatus;
  summaryReasonKeys: readonly SystemDiagnosticsReasonKey[];
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

function staleFromAge(
  ageMs: number | null | undefined,
  maxAgeMs: number,
): boolean {
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
  const orderbookStale = staleFromAge(
    liveState?.latest_feature?.orderbook_age_ms,
    90_000,
  );
  const reconcileStale = reconcileIsStale(health);
  const heartbeatStale = workerHeartbeatStale(health);

  const staleChecks: StaleCheckItem[] = [
    { key: "candles", stale: candlesStale },
    { key: "orderbook", stale: orderbookStale },
    { key: "signals", stale: signalsStale },
    { key: "reconcile", stale: reconcileStale },
    { key: "worker_heartbeat", stale: heartbeatStale },
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

  const reasonKeys: SystemDiagnosticsReasonKey[] = [];
  if (!healthEndpointWired) reasonKeys.push("healthEndpointUnwired");
  if (!health) reasonKeys.push("healthUnreadable");
  if (health?.database !== "ok") reasonKeys.push("postgresNotOk");
  if (health?.redis !== "ok") reasonKeys.push("redisNotOk");
  if (runtime?.upstream_ok === false)
    reasonKeys.push("bitgetPrivateUnreachable");
  if (hasStaleCritical) reasonKeys.push("staleDataDetected");
  if (hasOpenCriticalAlerts) reasonKeys.push("criticalAlertsOpen");
  if (reasonKeys.length === 0) reasonKeys.push("noCriticalIssues");

  const serviceStatus = (health?.services ?? []).map((s) => ({
    name: s.name,
    status: s.status || "unknown",
    detail:
      s.last_error != null
        ? redactDiagnosticError(s.last_error)
        : s.note || "__service_no_detail__",
  }));

  const latestCriticalErrors = (health?.services ?? [])
    .filter((s) => s.last_error)
    .map((s) => `${s.name}: ${redactDiagnosticError(s.last_error)}`)
    .slice(0, 6);

  const latestSuccessfulChecks = (health?.services ?? [])
    .filter((s) => s.ready === true || s.status === "ok")
    .map((s) => `__service_ok__:${s.name}`)
    .slice(0, 6);

  return {
    overallStatus,
    summaryReasonKeys: reasonKeys,
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
    llmStatus: (health?.services ?? []).some(
      (s) => s.name === "llm_orchestrator" && s.status === "ok",
    )
      ? "ok"
      : "__llm_degraded__",
    newsStatus: health?.data_freshness?.last_news_ts_ms ? "ok" : "unknown",
    alertStatus: `__alerts_open__:${openAlerts.length}`,
    staleChecks,
    latestCriticalErrors:
      latestCriticalErrors.length > 0
        ? latestCriticalErrors
        : ["__no_critical_errors__"],
    latestSuccessfulChecks:
      latestSuccessfulChecks.length > 0
        ? latestSuccessfulChecks
        : ["__no_success_checks__"],
  };
}
