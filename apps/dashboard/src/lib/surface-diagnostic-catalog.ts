import type { LiveMarketFreshness } from "@/lib/types";

export type SurfaceDiagnosticId =
  | "console_chart_fetch_failed"
  | "console_chart_empty_candles"
  | "console_chart_freshness_bad"
  | "terminal_fetch_failed"
  | "terminal_empty_candles"
  | "terminal_stream_stale"
  | "terminal_freshness_bad"
  | "health_page_load_failed"
  | "operator_explain_llm_failed"
  | "open_alerts_escalated";

export type SurfaceDiagnosticModel = Readonly<{
  id: SurfaceDiagnosticId;
  /** Basis für t("{messageBaseKey}.title") usw. */
  messageBaseKey: string;
  contextOverlay: Record<string, unknown>;
}>;

const BAD_FRESHNESS: ReadonlySet<LiveMarketFreshness["status"]> = new Set([
  "stale",
  "dead",
  "no_candles",
]);

function isEscalatedSeverity(raw: string): boolean {
  const x = raw.trim().toLowerCase();
  if (!x) return false;
  if (x === "critical" || x === "fatal" || x === "error" || x === "high") {
    return true;
  }
  if (x.includes("critical") || x.includes("fatal")) return true;
  if (x.startsWith("p0") || x.startsWith("p1")) return true;
  if (x.startsWith("sev0") || x.startsWith("sev1")) return true;
  return false;
}

export function resolveConsoleChartSurfaceDiagnostic(input: {
  loading: boolean;
  fetchErr: string | null;
  candleCount: number;
  symbol: string;
  timeframe: string;
  freshness: LiveMarketFreshness | null;
}): SurfaceDiagnosticModel | null {
  const { loading, fetchErr, candleCount, symbol, timeframe, freshness } =
    input;
  if (fetchErr) {
    return {
      id: "console_chart_fetch_failed",
      messageBaseKey: "diagnostic.surfaces.consoleChartFetchFailed",
      contextOverlay: {
        surface: "console_live_market_chart",
        chart_symbol: symbol,
        chart_timeframe: timeframe,
        fetch_error_excerpt: fetchErr.slice(0, 400),
      },
    };
  }
  if (!loading && candleCount === 0) {
    return {
      id: "console_chart_empty_candles",
      messageBaseKey: "diagnostic.surfaces.consoleChartEmpty",
      contextOverlay: {
        surface: "console_live_market_chart",
        chart_symbol: symbol,
        chart_timeframe: timeframe,
        freshness_status: freshness?.status ?? null,
      },
    };
  }
  if (freshness && BAD_FRESHNESS.has(freshness.status)) {
    return {
      id: "console_chart_freshness_bad",
      messageBaseKey: "diagnostic.surfaces.consoleChartFreshness",
      contextOverlay: {
        surface: "console_live_market_chart",
        chart_symbol: symbol,
        chart_timeframe: timeframe,
        freshness_status: freshness.status,
        candle_bar_lag_ms: freshness.candle?.bar_lag_ms ?? null,
        candle_ingest_age_ms: freshness.candle?.ingest_age_ms ?? null,
      },
    };
  }
  return null;
}

export function resolveLiveTerminalSurfaceDiagnostic(input: {
  fetchErr: string | null;
  candleCount: number;
  streamPhase: string;
  marketFreshness: LiveMarketFreshness | null;
  symbol: string;
  timeframe: string;
  healthDb: string;
  healthRedis: string;
  sseEnabled: boolean | null | undefined;
}): SurfaceDiagnosticModel | null {
  if (input.fetchErr) {
    return {
      id: "terminal_fetch_failed",
      messageBaseKey: "diagnostic.surfaces.terminalFetchFailed",
      contextOverlay: {
        surface: "live_terminal",
        symbol: input.symbol,
        timeframe: input.timeframe,
        fetch_error_excerpt: input.fetchErr.slice(0, 400),
        health_db: input.healthDb,
        health_redis: input.healthRedis,
      },
    };
  }
  if (input.streamPhase === "stale") {
    return {
      id: "terminal_stream_stale",
      messageBaseKey: "diagnostic.surfaces.terminalStreamStale",
      contextOverlay: {
        surface: "live_terminal",
        symbol: input.symbol,
        timeframe: input.timeframe,
        sse_meta_enabled:
          input.sseEnabled === undefined || input.sseEnabled === null
            ? null
            : input.sseEnabled,
      },
    };
  }
  if (input.candleCount === 0) {
    return {
      id: "terminal_empty_candles",
      messageBaseKey: "diagnostic.surfaces.terminalEmptyCandles",
      contextOverlay: {
        surface: "live_terminal",
        symbol: input.symbol,
        timeframe: input.timeframe,
        health_db: input.healthDb,
        health_redis: input.healthRedis,
      },
    };
  }
  if (
    input.marketFreshness &&
    BAD_FRESHNESS.has(input.marketFreshness.status)
  ) {
    return {
      id: "terminal_freshness_bad",
      messageBaseKey: "diagnostic.surfaces.terminalFreshnessBad",
      contextOverlay: {
        surface: "live_terminal",
        symbol: input.symbol,
        timeframe: input.timeframe,
        freshness_status: input.marketFreshness.status,
      },
    };
  }
  return null;
}

export function resolveHealthPageLoadSurfaceDiagnostic(
  loadError: string,
): SurfaceDiagnosticModel {
  return {
    id: "health_page_load_failed",
    messageBaseKey: "diagnostic.surfaces.healthPageLoadFailed",
    contextOverlay: {
      surface: "health_page",
      load_error_excerpt: loadError.slice(0, 600),
      upstream_calls: [
        "fetchSystemHealthCached",
        "fetchMonitorAlertsOpen",
        "fetchAlertOutboxRecent",
      ],
    },
  };
}

export function resolveOperatorExplainLlmSurfaceDiagnostic(
  errorMessage: string,
): SurfaceDiagnosticModel {
  return {
    id: "operator_explain_llm_failed",
    messageBaseKey: "diagnostic.surfaces.operatorExplainLlmFailed",
    contextOverlay: {
      surface: "operator_explain",
      llm_route: "POST /api/dashboard/llm/operator-explain",
      error_excerpt: errorMessage.slice(0, 600),
    },
  };
}

export type OpenAlertLite = Readonly<{
  severity: string;
  alert_key: string;
  title: string;
}>;

export function resolveOpenAlertsEscalationSurfaceDiagnostic(
  alerts: readonly OpenAlertLite[],
): SurfaceDiagnosticModel | null {
  if (!alerts.length) return null;
  const bad = alerts.filter((a) => isEscalatedSeverity(a.severity));
  if (!bad.length) return null;
  return {
    id: "open_alerts_escalated",
    messageBaseKey: "diagnostic.surfaces.openAlertsEscalated",
    contextOverlay: {
      surface: "monitor_open_alerts",
      alert_count_open: alerts.length,
      alert_count_escalated: bad.length,
      sample_keys: bad.slice(0, 8).map((b) => b.alert_key),
      sample_titles: bad.slice(0, 4).map((b) => b.title),
    },
  };
}
