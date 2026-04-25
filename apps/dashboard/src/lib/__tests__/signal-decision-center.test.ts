import {
  signalDataAgeDe,
  signalDetailAssetTierDe,
  signalDetailLiveReleaseDe,
  signalRiskStatusDe,
  summarizeBlockReasonsDe,
  tradeActionLabelDe,
} from "@/lib/signal-decision-center";
import type { SignalDetail, SignalRecentItem } from "@/lib/types";

const recentBase: SignalRecentItem = {
  signal_id: "sig-1",
  symbol: "BTCUSDT",
  timeframe: "5m",
  direction: "long",
  signal_class: "standard",
  decision_state: "open",
  signal_strength_0_100: 70,
  probability_0_1: 0.66,
  analysis_ts_ms: 1_700_000_000_000,
  created_ts: null,
  outcome_badge: null,
};

const detailBase: SignalDetail = {
  signal_id: "sig-1",
  symbol: "BTCUSDT",
  timeframe: "5m",
  direction: "long",
  signal_class: "standard",
  decision_state: "open",
  signal_strength_0_100: 70,
  probability_0_1: 0.66,
  regime_reasons_json: [],
  rejection_reasons_json: [],
  reasons_json: [],
  analysis_ts_ms: 1_700_000_000_000,
  created_ts: null,
  outcome_badge: null,
};

describe("signal-decision-center", () => {
  it("zeigt do_not_trade als deutsches Label", () => {
    expect(tradeActionLabelDe("do_not_trade")).toBe("Kein Trade");
  });

  it("mappt Blockgruende nach Deutsch", () => {
    const out = summarizeBlockReasonsDe(["stale candles", "quarantine"]);
    expect(out[0]).toContain("veraltet");
    expect(out[1]).toContain("Quarantaene");
  });

  it("LLM-Ausfall oder Block oeffnet keinen Trade-Status", () => {
    const status = signalRiskStatusDe({
      ...recentBase,
      trade_action: "do_not_trade",
      live_execution_block_reasons_json: ["risk governor blocked"],
      live_execution_clear_for_real_money: false,
    });
    expect(status).toContain("do_not_trade");
  });

  it("Signal-Detail liefert Asset-Tier und Live-Status", () => {
    const detail = {
      ...detailBase,
      instrument_metadata: { asset_tier: "Tier 3" },
      live_execution_clear_for_real_money: false,
      live_execution_block_reasons_json: ["policy"],
      trade_action: "blocked",
    };
    expect(signalDetailAssetTierDe(detail)).toBe("Tier 3");
    expect(signalDetailLiveReleaseDe(detail)).toContain("blockiert");
  });

  it("berechnet Datenalter robust", () => {
    expect(signalDataAgeDe(1_000, 61_000)).toBe("vor 1m");
  });
});
