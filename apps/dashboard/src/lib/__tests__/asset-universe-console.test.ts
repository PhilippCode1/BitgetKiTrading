import {
  buildAssetUniverseConsoleRows,
  type AssetConsoleRow,
} from "@/lib/asset-universe-console";
import type { MarketUniverseInstrumentItem } from "@/lib/types";

function baseInstrument(
  symbol: string,
  patch: Partial<MarketUniverseInstrumentItem> = {},
): MarketUniverseInstrumentItem {
  return {
    schema_version: "1",
    venue: "bitget",
    market_family: "futures",
    symbol,
    canonical_instrument_id: `cid:${symbol}`,
    category_key: "fut:main",
    product_type: "USDT-FUTURES",
    margin_coin: "USDT",
    margin_account_mode: "cross",
    base_coin: "BTC",
    quote_coin: "USDT",
    settle_coin: "USDT",
    metadata_source: "discovery",
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
    trading_status: "active",
    trading_enabled: true,
    subscribe_enabled: true,
    symbol_aliases: [],
    price_tick_size: "0.1",
    quantity_step: "0.001",
    quantity_min: "0.001",
    quantity_max: "100",
    market_order_quantity_max: "100",
    min_notional_quote: "5",
    leverage_min: 1,
    leverage_max: 10,
    funding_interval_hours: 8,
    symbol_type: "perp",
    supported_margin_coins: ["USDT"],
    price_precision: 1,
    quantity_precision: 3,
    session_metadata: {},
    raw_metadata: {
      risk_tier: "TIER_1",
      liquidity_score_0_1: 0.9,
      spread_bps: 4,
      slippage_bps_estimate: 6,
      funding_rate_bps: 2,
      open_interest: 1200000,
      strategy_evidence_ready: true,
    },
    refresh_ts_ms: Date.now(),
    ...patch,
  };
}

function firstRow(items: MarketUniverseInstrumentItem[]): AssetConsoleRow {
  return buildAssetUniverseConsoleRows(items)[0] as AssetConsoleRow;
}

describe("asset-universe-console", () => {
  it("asset unbekannt -> live blockiert", () => {
    const row = firstRow([
      baseInstrument("XUNKUSDT", { trading_status: "unknown", live_execution_enabled: false }),
    ]);
    expect(row.liveReady).toBe(false);
    expect(row.modeAllowed).not.toBe("Live bereit");
    expect(row.blockReasons.join(" ")).toContain("unbekannt");
  });

  it("asset delisted/suspended -> live blockiert", () => {
    const delisted = firstRow([baseInstrument("XDELUSDT", { trading_status: "delisted" })]);
    const suspended = firstRow([baseInstrument("XSUSUSDT", { trading_status: "suspended" })]);
    expect(delisted.liveReady).toBe(false);
    expect(suspended.liveReady).toBe(false);
    expect(delisted.assetTier).toBe(5);
    expect(suspended.assetTier).toBe(5);
  });

  it("futures ohne ProductType -> live blockiert", () => {
    const row = firstRow([baseInstrument("XNOPRODUSDT", { product_type: null })]);
    expect(row.liveReady).toBe(false);
    expect(row.blockReasons.join(" ")).toContain("ProductType");
  });

  it("ohne Tick/Lot/Precision -> live blockiert", () => {
    const row = firstRow([
      baseInstrument("XNOPRECUSDT", {
        price_tick_size: null,
        quantity_step: null,
        price_precision: null,
        quantity_precision: null,
      }),
    ]);
    expect(row.liveReady).toBe(false);
    expect(row.blockReasons.join(" ")).toContain("Praezisionsdaten");
  });

  it("schlechte Datenqualitaet -> live blockiert", () => {
    const row = firstRow([
      baseInstrument("XLOWQUSDT", { metadata_verified: false }),
    ]);
    expect(row.liveReady).toBe(false);
    expect(row.dataQuality).not.toBe("ok");
  });

  it("hohe Slippage -> live blockiert", () => {
    const row = firstRow([
      baseInstrument("XHISLIPUSDT", {
        raw_metadata: {
          risk_tier: "TIER_1",
          liquidity_score_0_1: 0.9,
          spread_bps: 5,
          slippage_bps_estimate: 120,
          strategy_evidence_ready: true,
        },
      }),
    ]);
    expect(row.liveReady).toBe(false);
    expect(row.blockReasons.join(" ")).toContain("Slippage");
  });

  it("zeigt Blockgruende deutsch", () => {
    const row = firstRow([
      baseInstrument("XDEUSDT", { metadata_verified: false }),
    ]);
    expect(row.blockReasons.length).toBeGreaterThan(0);
    expect(row.blockReasons[0]).toMatch(/[A-Za-zäöüÄÖÜ]/);
  });

  it("kein Asset zeigt Live bereit ohne Evidence", () => {
    const row = firstRow([
      baseInstrument("XNOEVIUSDT", {
        raw_metadata: {
          risk_tier: "TIER_1",
          liquidity_score_0_1: 0.95,
          spread_bps: 3,
          slippage_bps_estimate: 4,
          strategy_evidence_ready: false,
        },
      }),
    ]);
    expect(row.modeAllowed).not.toBe("Live bereit");
    expect(row.liveReady).toBe(false);
  });
});
