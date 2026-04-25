import {
  buildSystemDiagnosticsViewModel,
  redactDiagnosticError,
} from "@/lib/system-diagnostics-view-model";
import type { SystemHealthResponse } from "@/lib/types";

function baseHealth(): SystemHealthResponse {
  return {
    server_ts_ms: Date.now(),
    symbol: "BTCUSDT",
    database: "ok",
    redis: "ok",
    data_freshness: {
      last_candle_ts_ms: Date.now(),
      last_signal_ts_ms: Date.now(),
      last_news_ts_ms: Date.now(),
    },
    stream_lengths_top: [],
    services: [
      {
        name: "llm_orchestrator",
        status: "ok",
        configured: true,
        ready: true,
        last_run_ts_ms: Date.now(),
      },
    ],
    warnings: [],
    execution: {
      execution_mode: "shadow",
      strategy_execution_mode: "manual",
      paper_path_active: true,
      shadow_trade_enable: true,
      shadow_path_active: true,
      live_trade_enable: false,
      live_order_submission_enabled: false,
    },
    ops: {
      monitor: { open_alert_count: 0 },
      alert_engine: { outbox_pending: 0, outbox_failed: 0, outbox_sending: 0 },
      live_broker: {
        latest_reconcile_status: "ok",
        latest_reconcile_created_ts: null,
        latest_reconcile_age_ms: null,
        latest_reconcile_drift_total: 0,
        active_kill_switch_count: 0,
        safety_latch_active: false,
        last_fill_created_ts: null,
        last_fill_age_ms: null,
        critical_audit_count_24h: 0,
        order_status_counts: {},
      },
    },
  };
}

describe("system-diagnostics-view-model", () => {
  it("zeigt Blockiert wenn kritischer Dienst fehlt", () => {
    const health = baseHealth();
    health.database = "down";
    const model = buildSystemDiagnosticsViewModel({
      health,
      runtime: null,
      liveState: null,
      openAlerts: [],
      healthEndpointWired: true,
    });
    expect(model.overallStatus).toBe("Blockiert");
  });

  it("macht Redis down sichtbar", () => {
    const health = baseHealth();
    health.redis = "down";
    const model = buildSystemDiagnosticsViewModel({
      health,
      runtime: null,
      liveState: null,
      openAlerts: [],
      healthEndpointWired: true,
    });
    expect(model.redisStatus).toBe("down");
    expect(model.summaryReasons.join(" ")).toMatch(/Redis\/Eventbus nicht ok/i);
  });

  it("markiert stale-data checks", () => {
    const health = baseHealth();
    health.data_freshness.last_candle_ts_ms = Date.now() - 200_000;
    health.data_freshness.last_signal_ts_ms = Date.now() - 200_000;
    health.ops.live_broker.latest_reconcile_status = "fail";
    const model = buildSystemDiagnosticsViewModel({
      health,
      runtime: null,
      liveState: null,
      openAlerts: [],
      healthEndpointWired: true,
    });
    expect(model.staleChecks.find((x) => x.key === "candles")?.stale).toBe(true);
    expect(model.staleChecks.find((x) => x.key === "signals")?.stale).toBe(true);
    expect(model.staleChecks.find((x) => x.key === "reconcile")?.stale).toBe(true);
  });

  it("redacted sensitive error payload", () => {
    const s = redactDiagnosticError("authorization=bearer abc token=xyz");
    expect(s).not.toContain("abc");
    expect(s).not.toContain("xyz");
  });

  it("zeigt deutschen empty/error state bei fehlendem endpoint", () => {
    const model = buildSystemDiagnosticsViewModel({
      health: null,
      runtime: null,
      liveState: null,
      openAlerts: [],
      healthEndpointWired: false,
    });
    expect(model.summaryReasons.join(" ")).toMatch(/nicht verdrahtet/i);
    expect(model.overallStatus).toBe("Blockiert");
  });
});
