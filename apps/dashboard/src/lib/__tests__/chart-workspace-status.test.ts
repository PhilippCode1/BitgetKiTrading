import {
  buildDataQualityHint,
  buildLiquiditySpreadHint,
  chartWorkspaceAlertText,
  redactChartErrorDetail,
  resolveChartWorkspaceAlert,
} from "@/lib/chart-workspace-status";
import type { LiveFeatureSnapshot, LiveStateResponse } from "@/lib/types";

function stateBase(patch: Partial<LiveStateResponse> = {}): LiveStateResponse {
  return {
    read_envelope_contract_version: 1,
    status: "ok",
    symbol: "BTCUSDT",
    timeframe: "5m",
    server_ts_ms: Date.now(),
    live_state_contract_version: 1,
    candles: [{ time_s: 1, open: 1, high: 1, low: 1, close: 1, volume_usdt: 1 }],
    latest_signal: null,
    latest_feature: null,
    latest_news: [],
    latest_drawings: [],
    paper_state: null,
    health: { db: "ok", redis: "ok" },
    market_freshness: {
      status: "live",
      timeframe: "5m",
      stale_warn_ms: 1000,
      candle: null,
      ticker: null,
    },
    empty_state: false,
    message: null,
    next_step: null,
    data_lineage: [],
    online_drift: null,
    demo_data_notice: null,
    ...patch,
  } as unknown as LiveStateResponse;
}

describe("chart-workspace-status", () => {
  it("zeigt Alert bei fehlenden Candles", () => {
    const s = stateBase({ candles: [], market_freshness: { status: "no_candles" } as any });
    expect(resolveChartWorkspaceAlert(s, null)).toBe("no_candles_live_blocked");
    expect(chartWorkspaceAlertText("no_candles_live_blocked")).toContain("Keine Marktdaten");
  });

  it("zeigt Stale-Alert bei veralteten Daten", () => {
    const s = stateBase({ market_freshness: { status: "stale" } as any });
    expect(resolveChartWorkspaceAlert(s, null)).toBe("stale_live_blocked");
  });

  it("zeigt Quarantaene-Alert bei blockiertem Asset", () => {
    const s = stateBase({
      latest_signal: {
        signal_id: "s1",
        direction: "long",
        signal_strength_0_100: 50,
        probability_0_1: 0.5,
        signal_class: "info",
        instrument_metadata: { trading_status: "quarantined" },
        risk_warnings_json: [],
      } as any,
    });
    expect(resolveChartWorkspaceAlert(s, null)).toBe("asset_quarantined");
  });

  it("zeigt Bitget-Quelle nicht erreichbar bei Fetch-Fehler", () => {
    const s = stateBase();
    expect(resolveChartWorkspaceAlert(s, "network failed")).toBe("bitget_unreachable");
    expect(chartWorkspaceAlertText("bitget_unreachable")).toContain("Bitget-Datenquelle");
  });

  it("redacted Secrets in Error State", () => {
    const msg = redactChartErrorDetail("Authorization=Bearer abc.def token=123");
    expect(msg).toContain("authorization=***");
    expect(msg).toContain("token=***");
    expect(msg).not.toContain("abc.def");
  });

  it("liefert deutsche Empty/Hint-Texte fuer Datenqualitaet und Liquiditaet", () => {
    const feature: LiveFeatureSnapshot = {
      symbol: "BTCUSDT",
      timeframe: "5m",
      start_ts_ms: 1,
      computed_ts_ms: 2,
      spread_bps: 12,
      depth_to_bar_volume_ratio: 0.8,
      feature_quality_status: "degraded",
    };
    expect(buildDataQualityHint(feature)).toContain("Datenqualitaet");
    expect(buildLiquiditySpreadHint(feature)).toContain("Spread");
  });
});
