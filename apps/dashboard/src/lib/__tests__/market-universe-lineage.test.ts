import {
  buildCoreSymbolRows,
  findInstrumentBySymbol,
  MARKET_UNIVERSE_CORE_SYMBOLS,
  serviceByName,
  summarizeWsTelemetry,
} from "@/lib/market-universe-lineage";
import type {
  MarketUniverseInstrumentItem,
  SystemHealthServiceItem,
} from "@/lib/types";

const baseInst = (symbol: string): MarketUniverseInstrumentItem => ({
  schema_version: "1",
  venue: "bitget",
  market_family: "USDT-FUTURES",
  symbol,
  canonical_instrument_id: `c:${symbol}`,
  category_key: "c",
  margin_account_mode: "cross",
  metadata_source: "api",
  metadata_verified: true,
  inventory_visible: true,
  analytics_eligible: true,
  paper_shadow_eligible: true,
  live_execution_enabled: symbol === "BTCUSDT",
  execution_disabled: false,
  supports_funding: true,
  supports_open_interest: true,
  supports_long_short: true,
  supports_shorting: true,
  supports_reduce_only: true,
  supports_leverage: true,
  uses_spot_public_market_data: false,
  trading_status: "online",
  trading_enabled: true,
  subscribe_enabled: true,
  symbol_aliases: [],
  supported_margin_coins: [],
});

describe("market-universe-lineage", () => {
  it("findInstrumentBySymbol matcht Aliase", () => {
    const inst = baseInst("BTCUSDT");
    const list = [{ ...inst, symbol_aliases: ["btc_usdt"] }];
    expect(findInstrumentBySymbol(list, "BTCUSDT")?.symbol).toBe("BTCUSDT");
    expect(findInstrumentBySymbol(list, "btc_usdt")?.symbol).toBe("BTCUSDT");
    expect(findInstrumentBySymbol(list, "MISSING")).toBeNull();
  });

  it("buildCoreSymbolRows liefert Zeilen fuer Kernsymbole", () => {
    const rows = buildCoreSymbolRows(
      [baseInst("BTCUSDT"), baseInst("ETHUSDT")],
      MARKET_UNIVERSE_CORE_SYMBOLS,
    );
    expect(rows).toHaveLength(2);
    expect(rows[0]?.symbol).toBe("BTCUSDT");
    expect(rows[0]?.inRegistry).toBe(true);
    expect(rows[0]?.liveEnabled).toBe(true);
    expect(rows[1]?.symbol).toBe("ETHUSDT");
  });

  it("serviceByName findet Dienst", () => {
    const svc: SystemHealthServiceItem[] = [
      { name: "market-stream", status: "ok", configured: true },
    ];
    expect(serviceByName(svc, "market-stream")?.status).toBe("ok");
    expect(serviceByName(svc, "missing")).toBeNull();
  });

  it("summarizeWsTelemetry komprimiert Objekt", () => {
    expect(summarizeWsTelemetry({ connected: true, state: "open" })).toContain(
      "connected=true",
    );
    expect(summarizeWsTelemetry(undefined)).toBe("");
  });
});
