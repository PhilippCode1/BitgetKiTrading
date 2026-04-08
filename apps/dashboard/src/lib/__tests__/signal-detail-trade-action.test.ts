import { resolveTradeActionI18n } from "@/lib/signal-detail-trade-action";

describe("resolveTradeActionI18n", () => {
  it("maps empty to unset key", () => {
    expect(resolveTradeActionI18n(null)).toEqual({
      key: "pages.signalsDetail.tradeActions.unset",
    });
    expect(resolveTradeActionI18n("  ")).toEqual({
      key: "pages.signalsDetail.tradeActions.unset",
    });
  });

  it("normalizes hyphens and case for known actions", () => {
    expect(resolveTradeActionI18n("DO-NOT-TRADE")).toEqual({
      key: "pages.signalsDetail.tradeActions.doNotTrade",
    });
    expect(resolveTradeActionI18n("enter_long")).toEqual({
      key: "pages.signalsDetail.tradeActions.enterLong",
    });
  });

  it("returns unfamiliar with raw for unknown codes", () => {
    expect(resolveTradeActionI18n("custom_xyz")).toEqual({
      key: "pages.signalsDetail.tradeActions.unfamiliar",
      vars: { raw: "custom_xyz" },
    });
  });
});
