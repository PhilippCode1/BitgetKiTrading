import {
  liveDataSurfaceToCommsPhase,
  liveDataSurfaceToExpectation,
} from "@/lib/system-communication";
import { buildLiveDataSurfaceModelFromLiveState } from "@/lib/live-data-surface-model";
import type { LiveStateResponse } from "@/lib/types";

const baseLive = {
  status: "ok" as const,
  message: null,
  empty_state: false,
  degradation_reason: null,
  next_step: null,
  live_state_contract_version: 1,
  symbol: "BTCUSDT",
  timeframe: "1m",
  server_ts_ms: 1_700_000_000_000,
  candles: [
    { time_s: 1, open: 1, high: 1, low: 1, close: 1, volume_usdt: 1 },
  ],
  latest_signal: null,
  latest_drawings: [],
  latest_news: [],
  paper_state: {
    open_positions: [],
    last_closed_trade: null,
    unrealized_pnl_usdt: 0,
    mark_price: null,
  },
  health: { db: "ok" as const, redis: "ok" as const },
  data_lineage: [
    {
      segment_id: "candles",
      label_de: "K",
      label_en: "K",
      has_data: true,
      producer_de: "p",
      producer_en: "p",
      why_empty_de: "",
      why_empty_en: "",
      next_step_de: "",
      next_step_en: "",
    },
  ],
  market_freshness: {
    status: "live" as const,
    timeframe: "1m",
    stale_warn_ms: 120_000,
    candle: {
      last_start_ts_ms: 1_700_000_000_000,
      last_ingest_ts_ms: 1_700_000_000_000,
      bar_duration_ms: 60_000,
      aligned_bucket_start_ms: 1_700_000_000_000,
      bar_lag_ms: 1000,
      ingest_age_ms: 500,
    },
    ticker: null,
  },
  demo_data_notice: { show_banner: false, reasons: [] },
} as unknown as LiveStateResponse;

describe("system-communication", () => {
  it("LIVE + execution paper → Phase partial + Erwartung Paper-Spur", () => {
    const m = buildLiveDataSurfaceModelFromLiveState({
      live: baseLive,
      executionVm: {
        source: "system_health",
        execution_mode: "paper",
        strategy_execution_mode: "paper",
        paper_path_active: true,
        shadow_trade_enable: false,
        shadow_path_active: false,
        live_trade_enable: false,
        live_order_submission_enabled: false,
        require_shadow_match_before_live: false,
      },
      fetchError: false,
      loading: false,
      candleCount: 1,
      surfaceKind: "market_chart",
    });
    expect(liveDataSurfaceToCommsPhase(m)).toBe("partial");
    expect(liveDataSurfaceToExpectation(m).expectationKey).toBe(
      "systemComms.expectation.execLanePaper",
    );
  });

  it("fetchFailed → blocked + fetchFailed-Erwartung", () => {
    const m = buildLiveDataSurfaceModelFromLiveState({
      live: null,
      executionVm: null,
      fetchError: true,
      loading: false,
      candleCount: 0,
      surfaceKind: "market_chart",
    });
    expect(liveDataSurfaceToCommsPhase(m)).toBe("blocked");
    expect(liveDataSurfaceToExpectation(m).expectationKey).toBe(
      "systemComms.expectation.fetchFailed",
    );
  });
});
