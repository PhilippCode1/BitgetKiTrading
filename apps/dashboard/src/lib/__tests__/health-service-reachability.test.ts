import {
  analyzeServiceReachability,
  connectivitySupplements,
  showConnectivityFirstAid,
  systemHealthAdminHubGreen,
} from "@/lib/health-service-reachability";
import type { SystemHealthResponse } from "@/lib/types";

function minimalHealth(
  services: SystemHealthResponse["services"],
): SystemHealthResponse {
  return {
    symbol: "BTCUSDT",
    server_ts_ms: 0,
    database: "ok",
    redis: "ok",
    warnings: [],
    data_freshness: {
      last_candle_ts_ms: null,
      last_signal_ts_ms: null,
      last_news_ts_ms: null,
    },
    execution: {
      execution_mode: "paper",
      strategy_execution_mode: "manual",
      paper_path_active: true,
      shadow_trade_enable: false,
      shadow_path_active: false,
      live_trade_enable: false,
      live_order_submission_enabled: false,
    },
    ops: {
      monitor: { open_alert_count: 0 },
      alert_engine: { outbox_pending: 0, outbox_failed: 0, outbox_sending: 0 },
      live_broker: {
        latest_reconcile_status: null,
        latest_reconcile_created_ts: null,
        latest_reconcile_age_ms: null,
        latest_reconcile_drift_total: 0,
        active_kill_switch_count: 0,
        last_fill_created_ts: null,
        last_fill_age_ms: null,
        critical_audit_count_24h: 0,
        order_status_counts: {},
      },
    },
    services,
    stream_lengths_top: [],
  };
}

describe("health-service-reachability", () => {
  it("showConnectivityFirstAid true bei vielen Timeouts", () => {
    const svc = ["a", "b", "c", "d", "e"].map((name) => ({
      name,
      configured: true,
      status: "error",
      detail: "API/HTTP: timed out",
    }));
    const h = minimalHealth(svc);
    expect(analyzeServiceReachability(h).timeoutLike).toBe(5);
    expect(showConnectivityFirstAid(h)).toBe(true);
  });

  it("showConnectivityFirstAid false wenn nur api-gateway ok", () => {
    const h = minimalHealth([
      { name: "api-gateway", configured: true, status: "ok" },
    ]);
    expect(showConnectivityFirstAid(h)).toBe(false);
  });

  it("connectivitySupplements erkennt monitor-engine refused und Split-Brain", () => {
    const svc = [
      { name: "api-gateway", configured: true, status: "ok" },
      { name: "news-engine", configured: true, status: "ok" },
      { name: "llm-orchestrator", configured: true, status: "ok" },
      {
        name: "monitor-engine",
        configured: true,
        status: "error",
        detail: "API/HTTP: <urlopen error [Errno 111] Connection refused>",
      },
      {
        name: "market-stream",
        configured: true,
        status: "error",
        detail: "API/HTTP: timed out",
      },
      {
        name: "signal-engine",
        configured: true,
        status: "error",
        detail: "API/HTTP: timed out",
      },
      {
        name: "feature-engine",
        configured: true,
        status: "error",
        detail: "API/HTTP: timed out",
      },
      {
        name: "paper-broker",
        configured: true,
        status: "error",
        detail: "API/HTTP: timed out",
      },
    ];
    const h = minimalHealth(svc);
    const s = connectivitySupplements(h);
    expect(s.monitorEngineConnectionRefused).toBe(true);
    expect(s.partialReachabilityPattern).toBe(true);
  });

  it("systemHealthAdminHubGreen: null und DB-Fehler false", () => {
    expect(systemHealthAdminHubGreen(null)).toBe(false);
    const h = minimalHealth([]);
    expect(
      systemHealthAdminHubGreen({ ...h, database: "error", warnings: [] }),
    ).toBe(false);
  });

  it("systemHealthAdminHubGreen: database ok aber Warnungen => false", () => {
    const h = minimalHealth([]);
    expect(
      systemHealthAdminHubGreen({
        ...h,
        database: "ok",
        warnings: ["stale_candles"],
      }),
    ).toBe(false);
  });

  it("systemHealthAdminHubGreen: database ok und leere warnings => true", () => {
    const h = minimalHealth([]);
    expect(
      systemHealthAdminHubGreen({ ...h, database: "ok", warnings: [] }),
    ).toBe(true);
  });
});
