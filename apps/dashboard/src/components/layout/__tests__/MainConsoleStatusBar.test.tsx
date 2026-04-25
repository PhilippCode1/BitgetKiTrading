/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";

import { MainConsoleStatusBar } from "@/components/layout/MainConsoleStatusBar";
import type { ExecutionTierSnapshot, SystemHealthResponse } from "@/lib/types";

function mockTier(partial?: Partial<ExecutionTierSnapshot>): ExecutionTierSnapshot {
  return {
    schema_version: 1,
    deployment: "local",
    app_env: "local",
    production: false,
    trading_plane: "shadow",
    execution_mode: "shadow",
    bitget_demo_enabled: true,
    live_broker_enabled: true,
    live_order_submission_enabled: false,
    automated_live_orders_enabled: false,
    strategy_execution_mode: "manual",
    ...partial,
  };
}

function mockHealth(partial?: Partial<SystemHealthResponse>): SystemHealthResponse {
  return {
    server_ts_ms: Date.now(),
    symbol: "BTCUSDT",
    execution: {
      execution_mode: "shadow",
      strategy_execution_mode: "manual",
      paper_path_active: true,
      shadow_trade_enable: true,
      shadow_path_active: true,
      live_trade_enable: false,
      live_order_submission_enabled: false,
    },
    database: "ok",
    data_freshness: {
      last_candle_ts_ms: Date.now(),
      last_signal_ts_ms: Date.now(),
      last_news_ts_ms: Date.now(),
    },
    redis: "ok",
    stream_lengths_top: [],
    services: [{ name: "live-broker", status: "ok", configured: true }],
    ops: {
      monitor: { open_alert_count: 0 },
      alert_engine: { outbox_pending: 0, outbox_failed: 0, outbox_sending: 0 },
      live_broker: {
        latest_reconcile_status: "clean",
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
    warnings: [],
    ...partial,
  };
}

describe("MainConsoleStatusBar", () => {
  it("rendert Betriebsmodus-Badge", () => {
    render(
      <MainConsoleStatusBar
        tier={mockTier({ trading_plane: "live", live_order_submission_enabled: true })}
        health={mockHealth()}
        healthError={false}
      />,
    );
    expect(screen.getByText(/Betriebsmodus:/i)).toBeInTheDocument();
    expect(screen.getByText(/Live bereit/i)).toBeInTheDocument();
  });

  it("rendert globalen Sicherheitsstatus", () => {
    render(
      <MainConsoleStatusBar
        tier={mockTier()}
        health={mockHealth({ aggregate: { level: "degraded", summary_de: "", primary_reason_codes: [] } })}
        healthError={false}
      />,
    );
    expect(screen.getByText(/Sicherheit:/i)).toBeInTheDocument();
    expect(screen.getByText(/Warnung/i)).toBeInTheDocument();
  });
});
