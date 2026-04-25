import type { MarketUniverseInstrumentItem } from "@/lib/types";

export type AssetStatus =
  | "aktiv"
  | "unbekannt"
  | "stale"
  | "delisted"
  | "suspended"
  | "quarantined";

export type AssetTier = 0 | 1 | 2 | 3 | 4 | 5;

export type AssetModeLabel =
  | "Paper"
  | "Shadow"
  | "Live blockiert"
  | "Live bereit";

export type AssetConsoleRow = Readonly<{
  symbol: string;
  instrumentId: string;
  marketFamily: "Spot" | "Margin" | "Futures" | "Unbekannt";
  productType: string;
  marginCoin: string;
  status: AssetStatus;
  dataQuality: string;
  liquidity: string;
  spread: string;
  fundingOi: string;
  riskTier: string;
  assetTier: AssetTier;
  modeAllowed: AssetModeLabel;
  blockReasons: string[];
  liveReady: boolean;
}>;

const HIGH_SLIPPAGE_BPS = 40;

function asNum(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "") {
    const n = Number(v);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function familyLabel(value: string): AssetConsoleRow["marketFamily"] {
  const v = value.toLowerCase();
  if (v.includes("spot")) return "Spot";
  if (v.includes("margin")) return "Margin";
  if (v.includes("future")) return "Futures";
  return "Unbekannt";
}

function mapStatus(item: MarketUniverseInstrumentItem): AssetStatus {
  const raw = (item.trading_status || "").toLowerCase();
  if (raw.includes("delist")) return "delisted";
  if (raw.includes("suspend")) return "suspended";
  if (raw.includes("stale")) return "stale";
  if (raw.includes("unknown") || !raw) return "unbekannt";
  if (!item.trading_enabled || !item.subscribe_enabled) return "quarantined";
  return "aktiv";
}

function riskTier(item: MarketUniverseInstrumentItem): string {
  const raw = (item.raw_metadata || {}) as Record<string, unknown>;
  const value = raw.risk_tier;
  if (typeof value === "string" && value.trim()) return value.trim().toUpperCase();
  return "TIER_0";
}

function spreadLabel(item: MarketUniverseInstrumentItem): string {
  const raw = (item.raw_metadata || {}) as Record<string, unknown>;
  const spread = asNum(raw.spread_bps);
  if (spread == null) return "unbekannt";
  return `${spread.toFixed(1)} bps`;
}

function dataQualityLabel(item: MarketUniverseInstrumentItem): string {
  if (!item.metadata_verified) return "niedrig";
  if (!item.refresh_ts_ms) return "unbekannt";
  const ageMs = Date.now() - item.refresh_ts_ms;
  if (ageMs > 1000 * 60 * 60 * 24) return "stale";
  return "ok";
}

function liquidityLabel(item: MarketUniverseInstrumentItem): string {
  const raw = (item.raw_metadata || {}) as Record<string, unknown>;
  const score = asNum(raw.liquidity_score_0_1);
  if (score == null) {
    if (item.supports_leverage && item.supports_shorting) return "mittel";
    return "unbekannt";
  }
  if (score >= 0.85) return "hoch";
  if (score >= 0.6) return "mittel";
  return "niedrig";
}

function fundingOiLabel(item: MarketUniverseInstrumentItem): string {
  if (!item.supports_funding && !item.supports_open_interest) return "n/a";
  const raw = (item.raw_metadata || {}) as Record<string, unknown>;
  const funding = asNum(raw.funding_rate_bps);
  const oi = asNum(raw.open_interest);
  const f = funding == null ? "Funding ?" : `Funding ${funding.toFixed(2)} bps`;
  const o = oi == null ? "OI ?" : `OI ${oi.toFixed(0)}`;
  return `${f} · ${o}`;
}

function blockReasons(item: MarketUniverseInstrumentItem): string[] {
  const reasons: string[] = [];
  const status = mapStatus(item);
  const family = familyLabel(item.market_family);
  const raw = (item.raw_metadata || {}) as Record<string, unknown>;
  const slippage = asNum(raw.slippage_bps_estimate);
  const hasEvidence = raw.strategy_evidence_ready === true;

  if (status === "unbekannt") reasons.push("Asset-Status ist unbekannt, Live bleibt blockiert.");
  if (status === "delisted") reasons.push("Asset ist delisted, Live ist gesperrt.");
  if (status === "suspended") reasons.push("Asset ist suspended, Live ist gesperrt.");
  if (status === "stale") reasons.push("Asset-Daten sind stale, Live bleibt blockiert.");
  if (status === "quarantined") reasons.push("Asset ist in Quarantaene, Live bleibt blockiert.");
  if (family === "Futures" && !item.product_type)
    reasons.push("Futures ohne ProductType sind fuer Live blockiert.");
  if (!item.price_tick_size || !item.quantity_step || item.price_precision == null || item.quantity_precision == null)
    reasons.push("Praezisionsdaten fehlen (Tick/Lot/Precision), Live bleibt blockiert.");
  if (dataQualityLabel(item) !== "ok")
    reasons.push("Datenqualitaet ist nicht ausreichend fuer Live.");
  if (liquidityLabel(item) === "niedrig")
    reasons.push("Liquiditaet ist zu niedrig, Live bleibt blockiert.");
  if (slippage != null && slippage > HIGH_SLIPPAGE_BPS)
    reasons.push("Slippage ist zu hoch, Live bleibt blockiert.");
  if (!hasEvidence)
    reasons.push("Kein Strategie-Evidence-Nachweis, Live bleibt blockiert.");

  return Array.from(new Set(reasons));
}

function assetTier(item: MarketUniverseInstrumentItem, reasons: string[]): AssetTier {
  const status = mapStatus(item);
  if (status === "delisted" || status === "suspended") return 5;
  if (status === "unbekannt" || status === "quarantined") return 0;
  if (liquidityLabel(item) === "niedrig") return 4;
  const rTier = riskTier(item);
  if (rTier === "TIER_1" && reasons.length === 0) return 1;
  if (rTier === "TIER_2") return 2;
  return 3;
}

function modeAllowed(item: MarketUniverseInstrumentItem, reasons: string[]): AssetModeLabel {
  if (reasons.length === 0 && item.live_execution_enabled) return "Live bereit";
  if (item.paper_shadow_eligible) return "Shadow";
  if (item.analytics_eligible) return "Paper";
  return "Live blockiert";
}

export function buildAssetUniverseConsoleRows(
  instruments: readonly MarketUniverseInstrumentItem[],
): AssetConsoleRow[] {
  return instruments.map((item) => {
    const reasons = blockReasons(item);
    return {
      symbol: item.symbol,
      instrumentId: item.canonical_instrument_id,
      marketFamily: familyLabel(item.market_family),
      productType: item.product_type ?? "—",
      marginCoin: item.margin_coin ?? "—",
      status: mapStatus(item),
      dataQuality: dataQualityLabel(item),
      liquidity: liquidityLabel(item),
      spread: spreadLabel(item),
      fundingOi: fundingOiLabel(item),
      riskTier: riskTier(item),
      assetTier: assetTier(item, reasons),
      modeAllowed: modeAllowed(item, reasons),
      blockReasons: reasons,
      liveReady: reasons.length === 0 && item.live_execution_enabled,
    };
  });
}
