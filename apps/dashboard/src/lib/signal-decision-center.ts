import { summarizeReasonsJsonForUi } from "@/lib/signal-explain-display";
import type { SignalDetail, SignalRecentItem } from "@/lib/types";

const ACTION_LABELS: Record<string, string> = {
  allow_trade: "Trade erlaubt",
  do_not_trade: "Kein Trade",
  review_required: "Pruefung noetig",
  blocked: "Blockiert",
};

const DE_REASON_MAP: Array<[RegExp, string]> = [
  [/stale|veraltet/i, "Marktdaten sind veraltet."],
  [/no[_ -]?candles|keine kerzen|no candles/i, "Keine Marktdaten verfuegbar."],
  [/quarant/i, "Asset in Quarantaene."],
  [/liquid/i, "Liquiditaet unzureichend."],
  [/spread/i, "Spread zu hoch."],
  [/risk|governor|policy/i, "Risk-Governor blockiert den Live-Pfad."],
  [/exchange|bitget|upstream/i, "Boersenpfad nicht stabil erreichbar."],
];

function toReasonString(value: unknown): string {
  if (typeof value === "string") return value.trim();
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const o = value as Record<string, unknown>;
    const candidate = o.reason ?? o.message ?? o.code;
    if (typeof candidate === "string") return candidate.trim();
  }
  return String(value ?? "").trim();
}

function toGermanReason(raw: string): string {
  if (!raw) return "Unbekannter Blockgrund.";
  for (const [re, text] of DE_REASON_MAP) {
    if (re.test(raw)) return text;
  }
  return raw;
}

export function tradeActionLabelDe(action: string | null | undefined): string {
  const key = (action ?? "").trim().toLowerCase();
  if (!key) return "Nicht gesetzt";
  return ACTION_LABELS[key] ?? key;
}

export function summarizeBlockReasonsDe(
  reasons: unknown,
  maxItems = 3,
): string[] {
  const rawItems = Array.isArray(reasons)
    ? reasons.slice(0, maxItems).map(toReasonString)
    : summarizeReasonsJsonForUi(reasons, maxItems);
  const mapped = rawItems
    .map((x) => toGermanReason(x))
    .filter((x) => x.length > 0);
  return mapped.length > 0 ? mapped : ["Keine Blockgruende gemeldet."];
}

export function signalRiskStatusDe(signal: SignalRecentItem): string {
  const blocks = Array.isArray(signal.live_execution_block_reasons_json)
    ? signal.live_execution_block_reasons_json.length
    : 0;
  if (signal.live_execution_clear_for_real_money === true && blocks === 0) {
    return "Live-freigabefaehig";
  }
  if (signal.trade_action?.toLowerCase() === "do_not_trade") {
    return "Risk: do_not_trade";
  }
  if (blocks > 0) return `Live blockiert (${blocks})`;
  return "Freigabe unklar";
}

export function signalDataAgeDe(
  analysisTsMs: number,
  nowTsMs: number = Date.now(),
): string {
  if (!Number.isFinite(analysisTsMs) || analysisTsMs <= 0) return "unbekannt";
  const diffMs = Math.max(0, nowTsMs - analysisTsMs);
  const sec = Math.floor(diffMs / 1000);
  if (sec < 60) return `vor ${sec}s`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `vor ${min}m`;
  const h = Math.floor(min / 60);
  return `vor ${h}h`;
}

function metaValue(meta: Record<string, unknown> | null, key: string): string {
  if (!meta) return "—";
  const v = meta[key];
  if (v == null) return "—";
  return String(v);
}

export function signalDetailAssetTierDe(detail: SignalDetail): string {
  const meta = (detail.instrument_metadata ?? null) as Record<string, unknown> | null;
  return metaValue(meta, "asset_tier");
}

export function signalDetailDataQualityDe(detail: SignalDetail): string {
  const meta = (detail.instrument_metadata ?? null) as Record<string, unknown> | null;
  const fromMeta = metaValue(meta, "data_quality_status");
  if (fromMeta !== "—") return fromMeta;
  if (detail.instrument_metadata_verified === true) return "verifiziert";
  if (detail.instrument_metadata_verified === false) return "nicht verifiziert";
  return "unbekannt";
}

export function signalDetailLiquidityDe(detail: SignalDetail): string {
  const meta = (detail.instrument_metadata ?? null) as Record<string, unknown> | null;
  const liq = metaValue(meta, "liquidity_status");
  if (liq !== "—") return liq;
  const spread = metaValue(meta, "spread_band");
  if (spread !== "—") return `Spread-Band ${spread}`;
  return "unbekannt";
}

export function signalDetailLiveReleaseDe(detail: SignalDetail): string {
  const action = (detail.trade_action ?? "").toLowerCase();
  const blocks = Array.isArray(detail.live_execution_block_reasons_json)
    ? detail.live_execution_block_reasons_json.length
    : 0;
  if (detail.live_execution_clear_for_real_money && blocks === 0) {
    return "Live freigabefaehig";
  }
  if (action === "do_not_trade" || action === "blocked") return "Live blockiert";
  if (blocks > 0) return `Live blockiert (${blocks})`;
  return "Live nicht freigegeben";
}
