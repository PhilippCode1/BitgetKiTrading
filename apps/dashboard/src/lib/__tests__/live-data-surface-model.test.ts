import {
  buildLiveDataSurfaceModelFromLiveState,
  buildLiveDataSurfaceModelFromShadowLivePage,
  buildLiveDataSurfaceModelFromSignalsRead,
} from "@/lib/live-data-surface-model";
import type { LiveStateResponse, SignalsRecentResponse } from "@/lib/types";

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

describe("live-data-surface-model", () => {
  it("markiert Demo-Banner als PARTIAL", () => {
    const live = {
      ...baseLive,
      demo_data_notice: { show_banner: true, reasons: ["x"] },
    };
    const m = buildLiveDataSurfaceModelFromLiveState({
      live,
      executionVm: null,
      fetchError: false,
      loading: false,
      candleCount: 1,
      surfaceKind: "market_chart",
    });
    expect(m.primaryBadge).toBe("PARTIAL");
    expect(m.demoOrFixture).toBe(true);
  });

  it("Signalliste degraded → DEGRADED_READ", () => {
    const data = {
      items: [],
      limit: 50,
      status: "degraded" as const,
      message: "x",
      empty_state: true,
      degradation_reason: "r",
      next_step: "n",
      filters_active: false,
    } satisfies SignalsRecentResponse;
    const m = buildLiveDataSurfaceModelFromSignalsRead({
      data,
      executionVm: null,
      fetchFailed: false,
    });
    expect(m.primaryBadge).toBe("DEGRADED_READ");
    expect(m.surfaceKind).toBe("signals_list");
  });

  it("Shadow-Live: Teilfehler bei sonst LIVE → PARTIAL + Hinweis", () => {
    const m = buildLiveDataSurfaceModelFromShadowLivePage({
      health: null,
      live: baseLive,
      liveFetchFailed: false,
      sectionErrorCount: 2,
    });
    expect(m.primaryBadge).toBe("PARTIAL");
    expect(
      m.extraHintKeys.some((k) => k.key === "live.dataSituation.shadowPartialSections"),
    ).toBe(true);
    expect(m.affectedAreaKeys).toContain("live.dataSituation.areaShadowPanels");
  });
});
