import {
  buildOperatorSituationSummary,
  extractAccountDisplayRows,
  extractPaperPositionRiskRows,
  findBrokerishService,
  parseDriftFromRuntimeDetails,
} from "@/lib/operator-snapshot";

describe("parseDriftFromRuntimeDetails", () => {
  it("reads nested drift counts", () => {
    const d = parseDriftFromRuntimeDetails({
      drift: {
        total_count: 3,
        order: { local_only_count: 1, exchange_only_count: 2 },
        positions: { mismatch_count: 0 },
      },
    });
    expect(d.totalCount).toBe(3);
    expect(d.orderLocalOnly).toBe(1);
    expect(d.orderExchangeOnly).toBe(2);
    expect(d.positionMismatchCount).toBe(0);
  });

  it("handles null", () => {
    const d = parseDriftFromRuntimeDetails(null);
    expect(d.totalCount).toBeNull();
  });
});

describe("extractAccountDisplayRows", () => {
  it("pulls raw_data from first account snapshot", () => {
    const rows = extractAccountDisplayRows({
      recovery_state: {
        exchange_account_snapshots: [
          { raw_data: { marginRatio: "0.12", foo: 1 } },
        ],
      },
    });
    expect(rows.some((r) => r.label === "marginRatio")).toBe(true);
  });
});

describe("extractPaperPositionRiskRows", () => {
  it("collects known meta keys", () => {
    const rows = extractPaperPositionRiskRows([
      { isolated_margin: "10", liquidation_price: "42000" },
    ]);
    expect(rows.length).toBeGreaterThanOrEqual(1);
  });
});

describe("findBrokerishService", () => {
  it("prefers live-broker style names", () => {
    const hit = findBrokerishService([
      { name: "foo", status: "ok" },
      { name: "live-broker", status: "err" },
      { name: "other-broker", status: "ok" },
    ]);
    expect(hit?.name).toBe("live-broker");
  });

  it("falls back to broker substring", () => {
    const hit = findBrokerishService([
      { name: "ingest", status: "ok" },
      { name: "paper-broker-worker", status: "ok" },
    ]);
    expect(hit?.name).toBe("paper-broker-worker");
  });
});

describe("buildOperatorSituationSummary", () => {
  it("aggregates health, drift and kill-switch", () => {
    const s = buildOperatorSituationSummary({
      health: {
        execution: {
          execution_mode: "live",
          strategy_execution_mode: "promoted_only",
          live_trade_enable: true,
          live_order_submission_enabled: false,
        },
        database: "ok",
        services: [{ name: "live-broker", status: "ok" }],
        ops: {
          live_broker: {
            latest_reconcile_status: "ok",
            safety_latch_active: true,
          },
        },
      },
      killSwitchActiveCount: 2,
      onlineDrift: { effective_action: "warn", computed_at: "2026-01-01" },
      openMonitorAlerts: 3,
      recentDriftItemsCount: 5,
    });
    expect(s.executionMode).toBe("live");
    expect(s.liveSubmissionEnabled).toBe(false);
    expect(s.killSwitchActiveCount).toBe(2);
    expect(s.safetyLatchActive).toBe(true);
    expect(s.onlineDriftAction).toBe("warn");
    expect(s.brokerServiceName).toBe("live-broker");
    expect(s.databaseOk).toBe(true);
    expect(s.recentDriftEventCount).toBe(5);
  });

  it("tolerates null health", () => {
    const s = buildOperatorSituationSummary({
      health: null,
      killSwitchActiveCount: 0,
      onlineDrift: null,
      openMonitorAlerts: 0,
      recentDriftItemsCount: 0,
    });
    expect(s.executionMode).toBe("—");
    expect(s.databaseOk).toBe(false);
    expect(s.brokerServiceName).toBeNull();
  });
});
