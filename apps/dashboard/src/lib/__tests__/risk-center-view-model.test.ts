import {
  buildAssetRiskRows,
  computeLiveBlockers,
  computeOverallStatus,
  computeRiskOverviewFromRuntime,
  portfolioRiskSummary,
} from "@/lib/risk-center-view-model";
import type {
  LiveBrokerRuntimeItem,
  MarketUniverseInstrumentItem,
  SignalRecentItem,
} from "@/lib/types";

const runtimeBase: LiveBrokerRuntimeItem = {
  reconcile_snapshot_id: "snap",
  status: "ok",
  execution_mode: "live",
  runtime_mode: "live",
  strategy_execution_mode: "auto",
  upstream_ok: true,
  paper_path_active: true,
  shadow_trade_enable: true,
  shadow_enabled: true,
  shadow_path_active: true,
  live_trade_enable: true,
  live_submission_enabled: true,
  live_order_submission_enabled: true,
  decision_counts: {},
  details: {},
  order_status_counts: {},
  active_kill_switches: [],
  operator_live_submission: {
    lane: "live_lane_ready",
    reasons: [],
    safety: { kill_switch_count: 0, safety_latch_active: false },
    exchange: { tradable: true, mode: "normal" },
  } as any,
  created_ts: null,
};

const signalBase: SignalRecentItem = {
  signal_id: "sig-1",
  symbol: "BTCUSDT",
  timeframe: "5m",
  direction: "long",
  signal_class: "std",
  decision_state: "open",
  signal_strength_0_100: 60,
  probability_0_1: 0.61,
  analysis_ts_ms: 1_700_000_000_000,
  created_ts: null,
  outcome_badge: null,
};

const instrumentBase: MarketUniverseInstrumentItem = {
  schema_version: "1",
  venue: "bitget",
  market_family: "futures",
  symbol: "BTCUSDT",
  canonical_instrument_id: "bitget:linear:BTCUSDT",
  category_key: "linear",
  margin_account_mode: "cross",
  metadata_source: "test",
  metadata_verified: true,
  inventory_visible: true,
  analytics_eligible: true,
  paper_shadow_eligible: true,
  live_execution_enabled: true,
  execution_disabled: false,
  supports_funding: true,
  supports_open_interest: true,
  supports_long_short: true,
  supports_shorting: true,
  supports_reduce_only: true,
  supports_leverage: true,
  uses_spot_public_market_data: false,
  trading_status: "live",
  trading_enabled: true,
  subscribe_enabled: true,
  symbol_aliases: [],
  supported_margin_coins: [],
  raw_metadata: {},
};

describe("risk-center-view-model", () => {
  it("blockiert Portfolio bei Exposure-Ueberschreitung", () => {
    const runtime = {
      ...runtimeBase,
      details: {
        risk_account_snapshot: {
          portfolio_risk_json: {
            direction_net_exposure_0_1: 0.91,
            live_block_reasons_json: ["portfolio_live_direction_concentration_exceeded"],
          },
        },
      },
    };
    const summary = portfolioRiskSummary({ runtime, decisions: [], orders: [] });
    expect(summary.liveBlockReasons.join(" ")).toContain("portfolio_live_direction_concentration_exceeded");
  });

  it("Asset-Tier 4/5 zeigt Live blockiert", () => {
    const row = buildAssetRiskRows({
      instruments: [instrumentBase],
      signals: [{ ...signalBase, asset_risk_tier: "Tier 5", trade_action: "allow_trade" } as any],
    })[0];
    expect(row.maxMode).toBe("Paper");
    expect(row.blockReasons.join(" ")).toContain("asset quarantined");
  });

  it("stale snapshot wird als Blocker markiert", () => {
    const blockers = computeLiveBlockers({
      health: null,
      runtime: runtimeBase,
      liveSignal: null,
      killSwitchCount: 0,
      decisions: [],
    });
    expect(blockers).toContain("stale data");
    expect(computeOverallStatus(blockers)).toBe("blockiert");
  });

  it("drawdown Warnung ist sichtbar", () => {
    const out = computeRiskOverviewFromRuntime({
      ...runtimeBase,
      details: { risk_account_snapshot: { account_drawdown_0_1: 0.14 } },
    });
    expect(out.drawdown).toBe("14.0%");
  });

  it("Kill-Switch und Safety-Latch werden sichtbar", () => {
    const blockers = computeLiveBlockers({
      health: null,
      runtime: { ...runtimeBase, safety_latch_active: true },
      liveSignal: { signal_id: "x", direction: "long", signal_strength_0_100: 1, probability_0_1: 0.5, signal_class: "a", risk_warnings_json: [] } as any,
      killSwitchCount: 1,
      decisions: [],
    });
    expect(blockers).toContain("kill switch");
    expect(blockers).toContain("safety latch");
  });

  it("deutsche Blockgruende in Asset-Tabelle", () => {
    const row = buildAssetRiskRows({
      instruments: [instrumentBase],
      signals: [{ ...signalBase, live_execution_block_reasons_json: ["stale candles"] }],
    })[0];
    expect(row.blockReasons.join(" ")).toContain("stale data");
  });
});
