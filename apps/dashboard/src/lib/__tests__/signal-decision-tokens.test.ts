import {
  blockReasonTokens,
  signalAssetTierToken,
  signalDataAgeToken,
  signalLiveReleaseToken,
  signalRiskStatusToken,
  tradeActionToken,
} from "@/lib/signal-decision-tokens";
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

describe("signal-decision-tokens", () => {
  it("liefert do_not_trade als i18n-Token", () => {
    expect(tradeActionToken("do_not_trade")).toEqual({
      key: "do_not_trade",
      fallback: "do not trade",
    });
  });

  it("mappt Blockgruende auf stabile Token-Keys", () => {
    const tokens = blockReasonTokens(["stale candles", "quarantine"]);
    expect(tokens[0]?.key).toBe("stale");
    expect(tokens[0]?.fallback).toContain("veraltet");
    expect(tokens[1]?.key).toBe("quarantine");
    expect(tokens[1]?.fallback).toContain("Quarantaene");
  });

  it("LLM-Ausfall oder Block oeffnet keinen Live-freigabefaehig-Status", () => {
    const token = signalRiskStatusToken({
      ...recentBase,
      trade_action: "do_not_trade",
      live_execution_block_reasons_json: ["risk governor blocked"],
      live_execution_clear_for_real_money: false,
    });
    expect(token.key).toBe("do_not_trade");
  });

  it("Signal-Detail liefert Asset-Tier und Live-Status als Tokens", () => {
    const detail = {
      ...detailBase,
      instrument_metadata: { asset_tier: "Tier 3" },
      live_execution_clear_for_real_money: false,
      live_execution_block_reasons_json: ["policy"],
      trade_action: "blocked",
    };
    expect(signalAssetTierToken(detail)).toEqual({
      key: "passthrough",
      vars: { raw: "Tier 3" },
      fallback: "Tier 3",
    });
    expect(signalLiveReleaseToken(detail).key).toBe("live_blocked_any");
  });

  it("berechnet Datenalter als AgeToken", () => {
    expect(signalDataAgeToken(1_000, 61_000)).toEqual({
      key: "ageMinutes",
      vars: { count: 1 },
      fallback: "vor 1m",
    });
  });
});
