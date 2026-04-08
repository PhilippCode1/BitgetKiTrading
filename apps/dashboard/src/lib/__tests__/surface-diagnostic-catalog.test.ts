import {
  resolveConsoleChartSurfaceDiagnostic,
  resolveLiveTerminalSurfaceDiagnostic,
  resolveOpenAlertsEscalationSurfaceDiagnostic,
  resolveOperatorExplainLlmSurfaceDiagnostic,
} from "@/lib/surface-diagnostic-catalog";
import type { LiveMarketFreshness } from "@/lib/types";

describe("surface-diagnostic-catalog", () => {
  const candleOk = {
    last_start_ts_ms: 1,
    last_ingest_ts_ms: 2,
    bar_duration_ms: 60_000,
    aligned_bucket_start_ms: 0,
    bar_lag_ms: 1000,
    ingest_age_ms: 2000,
  };
  const tickerOk = {
    exchange_ts_ms: 1,
    ingest_ts_ms: 2,
    quote_age_ms: 0,
    ingest_age_ms: 2000,
    last_pr: 1 as number | null,
  };
  const freshLive: LiveMarketFreshness = {
    status: "live",
    timeframe: "1m",
    stale_warn_ms: 120_000,
    candle: candleOk,
    ticker: tickerOk,
  };

  it("console: fetch error beats empty candles", () => {
    const m = resolveConsoleChartSurfaceDiagnostic({
      loading: false,
      fetchErr: "boom",
      candleCount: 0,
      symbol: "BTCUSDT",
      timeframe: "1m",
      freshness: null,
    });
    expect(m?.id).toBe("console_chart_fetch_failed");
  });

  it("console: empty candles when no fetch error", () => {
    const m = resolveConsoleChartSurfaceDiagnostic({
      loading: false,
      fetchErr: null,
      candleCount: 0,
      symbol: "BTCUSDT",
      timeframe: "1m",
      freshness: null,
    });
    expect(m?.id).toBe("console_chart_empty_candles");
    expect(m?.contextOverlay.chart_symbol).toBe("BTCUSDT");
  });

  it("console: bad freshness when candles present", () => {
    const stale: LiveMarketFreshness = {
      status: "stale",
      timeframe: "1m",
      stale_warn_ms: 120_000,
      candle: {
        last_start_ts_ms: 1,
        last_ingest_ts_ms: 2,
        bar_duration_ms: 60_000,
        aligned_bucket_start_ms: 0,
        bar_lag_ms: 9e7,
        ingest_age_ms: 9e7,
      },
      ticker: null,
    };
    const m = resolveConsoleChartSurfaceDiagnostic({
      loading: false,
      fetchErr: null,
      candleCount: 10,
      symbol: "ETHUSDT",
      timeframe: "5m",
      freshness: stale,
    });
    expect(m?.id).toBe("console_chart_freshness_bad");
  });

  it("terminal: fetch error first", () => {
    const m = resolveLiveTerminalSurfaceDiagnostic({
      fetchErr: "nope",
      candleCount: 0,
      streamPhase: "stale",
      marketFreshness: null,
      symbol: "BTCUSDT",
      timeframe: "1m",
      healthDb: "ok",
      healthRedis: "ok",
      sseEnabled: true,
    });
    expect(m?.id).toBe("terminal_fetch_failed");
  });

  it("terminal: stream stale when no fetch error", () => {
    const m = resolveLiveTerminalSurfaceDiagnostic({
      fetchErr: null,
      candleCount: 5,
      streamPhase: "stale",
      marketFreshness: freshLive,
      symbol: "BTCUSDT",
      timeframe: "1m",
      healthDb: "ok",
      healthRedis: "ok",
      sseEnabled: true,
    });
    expect(m?.id).toBe("terminal_stream_stale");
  });

  it("terminal: empty candles after stream checks", () => {
    const m = resolveLiveTerminalSurfaceDiagnostic({
      fetchErr: null,
      candleCount: 0,
      streamPhase: "live",
      marketFreshness: freshLive,
      symbol: "BTCUSDT",
      timeframe: "1m",
      healthDb: "ok",
      healthRedis: "ok",
      sseEnabled: true,
    });
    expect(m?.id).toBe("terminal_empty_candles");
  });

  it("open alerts: null when empty or only low severity", () => {
    expect(
      resolveOpenAlertsEscalationSurfaceDiagnostic([
        { severity: "info", alert_key: "a", title: "t" },
      ]),
    ).toBeNull();
    expect(resolveOpenAlertsEscalationSurfaceDiagnostic([])).toBeNull();
  });

  it("open alerts: escalated when critical/high", () => {
    const m = resolveOpenAlertsEscalationSurfaceDiagnostic([
      { severity: "info", alert_key: "a", title: "t" },
      { severity: "high", alert_key: "b", title: "bad" },
    ]);
    expect(m?.id).toBe("open_alerts_escalated");
    expect(m?.contextOverlay.alert_count_escalated).toBe(1);
  });

  it("operator explain: always returns model", () => {
    const m = resolveOperatorExplainLlmSurfaceDiagnostic("timeout");
    expect(m.id).toBe("operator_explain_llm_failed");
    expect(String(m.contextOverlay.error_excerpt)).toContain("timeout");
  });
});
