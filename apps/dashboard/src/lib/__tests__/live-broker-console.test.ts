import {
  isLiveBrokerGlobalHaltFromHealth,
  isPaperSseForTradeLifecycle,
  orderStatusCountsNonEmpty,
  prettyJsonLine,
  recordHasKeys,
} from "@/lib/live-broker-console";

describe("live-broker-console", () => {
  it("prettyJsonLine formatiert ein Objekt", () => {
    expect(prettyJsonLine({ a: 1 })).toContain('"a"');
    expect(prettyJsonLine({ a: 1 })).toContain("1");
  });

  it("recordHasKeys erkennt leere Objekte und Arrays", () => {
    expect(recordHasKeys({})).toBe(false);
    expect(recordHasKeys([])).toBe(false);
    expect(recordHasKeys({ x: 1 })).toBe(true);
    expect(recordHasKeys([1])).toBe(true);
  });

  it("orderStatusCountsNonEmpty", () => {
    expect(orderStatusCountsNonEmpty(undefined)).toBe(false);
    expect(orderStatusCountsNonEmpty({})).toBe(false);
    expect(orderStatusCountsNonEmpty({ open: 2 })).toBe(true);
  });

  it("isPaperSseForTradeLifecycle erkennt trade_* und lifecycle_phase", () => {
    expect(isPaperSseForTradeLifecycle({ event_type: "trade_opened" })).toBe(
      true,
    );
    expect(
      isPaperSseForTradeLifecycle({
        event_type: "x",
        payload: { lifecycle_phase: "ORDER_FILLED" },
      }),
    ).toBe(true);
    expect(
      isPaperSseForTradeLifecycle({
        payload: { lifecycle_phase: "POSITION_UPDATE" },
      }),
    ).toBe(true);
    expect(isPaperSseForTradeLifecycle({ event_type: "ping" })).toBe(false);
  });

  it("isLiveBrokerGlobalHaltFromHealth", () => {
    expect(isLiveBrokerGlobalHaltFromHealth(undefined)).toBe(false);
    expect(
      isLiveBrokerGlobalHaltFromHealth({
        server_ts_ms: 0,
        symbol: "x",
        database: "ok",
        redis: "ok",
        data_freshness: {
          last_candle_ts_ms: null,
          last_signal_ts_ms: null,
          last_news_ts_ms: null,
        },
        services: [],
        stream_lengths_top: [],
        warnings: [],
        execution: {
          execution_mode: "x",
          strategy_execution_mode: "x",
          paper_path_active: true,
          shadow_trade_enable: false,
          shadow_path_active: false,
          live_trade_enable: false,
          live_order_submission_enabled: false,
        },
        ops: {
          monitor: { open_alert_count: 0 },
          alert_engine: {
            outbox_pending: 0,
            outbox_failed: 0,
            outbox_sending: 0,
          },
          live_broker: {
            latest_reconcile_status: null,
            latest_reconcile_created_ts: null,
            latest_reconcile_age_ms: null,
            latest_reconcile_drift_total: 0,
            active_kill_switch_count: 0,
            safety_latch_active: true,
            last_fill_created_ts: null,
            last_fill_age_ms: null,
            critical_audit_count_24h: 0,
            order_status_counts: {},
          },
        },
      } as import("@/lib/types").SystemHealthResponse),
    ).toBe(true);
  });
});
