import {
  resolveConsoleChartSymbolOptions,
  resolveConsoleChartSymbolTimeframe,
} from "@/lib/console-chart-context";
import {
  consoleHref,
  mergeConsoleSearchParams,
  pickTruthyQueryFields,
} from "@/lib/console-url-params";
import {
  executionPathFromLiveBrokerRuntime,
  executionPathFromSystemHealth,
} from "@/lib/execution-path-view-model";
import type { LiveBrokerRuntimeItem, SystemHealthResponse } from "@/lib/types";

describe("resolveConsoleChartSymbolTimeframe", () => {
  it("prefers URL symbol over persisted", () => {
    const r = resolveConsoleChartSymbolTimeframe({
      urlSymbol: "ETHUSDT",
      urlTimeframe: "1h",
      persistedSymbol: "BTCUSDT",
      persistedTimeframe: "5m",
      defaultSymbol: "SOLUSDT",
      defaultTimeframe: "15m",
    });
    expect(r.chartSymbol).toMatch(/ETHUSDT/i);
    expect(r.chartTimeframe).toBe("1h");
  });

  it("falls back to persisted when URL empty", () => {
    const r = resolveConsoleChartSymbolTimeframe({
      urlSymbol: "",
      urlTimeframe: "",
      persistedSymbol: "BTCUSDT",
      persistedTimeframe: "4h",
      defaultSymbol: "SOLUSDT",
      defaultTimeframe: null,
    });
    expect(r.chartSymbol).toMatch(/BTCUSDT/i);
    expect(r.chartTimeframe).toBe("4h");
  });
});

describe("resolveConsoleChartSymbolOptions", () => {
  it("uses facets when provided", () => {
    const o = resolveConsoleChartSymbolOptions({
      facetSymbols: ["A", "B"],
      watchlist: ["C"],
      chartSymbol: "Z",
    });
    expect(o).toContain("A");
    expect(o).toContain("Z");
  });
});

describe("mergeConsoleSearchParams / consoleHref", () => {
  it("omits empty values", () => {
    const u = mergeConsoleSearchParams({ a: "1", b: "" }, { c: null, d: "x" });
    expect(u.toString()).toBe("a=1&d=x");
  });

  it("consoleHref builds path", () => {
    expect(
      consoleHref("/console/ops", { symbol: "BTCUSDT" }, { timeframe: "5m" }),
    ).toBe("/console/ops?symbol=BTCUSDT&timeframe=5m");
  });
});

describe("pickTruthyQueryFields", () => {
  it("filters strings", () => {
    expect(pickTruthyQueryFields({ a: "x", b: "", c: undefined })).toEqual({
      a: "x",
    });
  });
});

describe("executionPathFromSystemHealth", () => {
  it("maps execution block", () => {
    const health = {
      execution: {
        execution_mode: "paper",
        strategy_execution_mode: "auto",
        paper_path_active: true,
        shadow_trade_enable: false,
        shadow_path_active: false,
        live_trade_enable: false,
        live_order_submission_enabled: false,
      },
    } as unknown as SystemHealthResponse;
    const m = executionPathFromSystemHealth(health);
    expect(m?.execution_mode).toBe("paper");
    expect(m?.paper_path_active).toBe(true);
    expect(m?.source).toBe("system_health");
  });
});

describe("executionPathFromLiveBrokerRuntime", () => {
  it("includes broker-only fields", () => {
    const item = {
      status: "ok",
      execution_mode: "live",
      strategy_execution_mode: null,
      upstream_ok: true,
      paper_path_active: false,
      shadow_trade_enable: true,
      shadow_enabled: true,
      shadow_path_active: true,
      live_trade_enable: true,
      live_submission_enabled: true,
      live_order_submission_enabled: true,
      require_shadow_match_before_live: true,
      created_ts: "2026-01-01T00:00:00Z",
      operator_live_submission: {
        lane: "live_lane_ready",
        reasons_de: [],
        safety_kill_switch_count: 0,
        safety_latch_active: false,
      },
    } as unknown as LiveBrokerRuntimeItem;
    const m = executionPathFromLiveBrokerRuntime(item);
    expect(m?.source).toBe("live_broker_runtime");
    expect(m?.require_shadow_match_before_live).toBe(true);
    expect(m?.snapshot_ts).toBe("2026-01-01T00:00:00Z");
  });
});
