import { summarizeReasonsJsonForUi } from "@/lib/signal-explain-display";
import type { SignalDetail, SignalRecentItem } from "@/lib/types";

/**
 * Saubere i18n-Schicht: Decision-Center-Helper liefern Code-Tokens statt
 * lokalisierter Strings. Das Frontend uebersetzt mit `t()` gegen die
 * Schluessel unter `pages.signalsDetail.decisionCenter.*` und
 * `signalsTable.dataAge`.
 *
 * Hintergrund: vorher gaben `signal-decision-center.ts`-Funktionen deutsche
 * Strings zurueck, die im UI per Regex-Mapping rueck-uebersetzt wurden.
 * Das ist fragil und i18n-unsicher.
 */

export type DecisionToken = {
  /** i18n-Key relativ zu `pages.signalsDetail.decisionCenter`. */
  key: string;
  /** Optionale Variablen fuer ICU/Format-Strings. */
  vars?: Record<string, string | number>;
  /** Fallback-Klartext, falls i18n-Key fehlt (Audit-Zeile, Log). */
  fallback: string;
};

export type AgeToken = {
  /** i18n-Key relativ zu `signalsTable`. */
  key: "ageSeconds" | "ageMinutes" | "ageHours" | "ageUnknown";
  vars?: { count: number };
  fallback: string;
};

const TRADE_ACTION_KEY: Record<string, string> = {
  allow_trade: "allow_trade",
  do_not_trade: "do_not_trade",
  review_required: "review_required",
  blocked: "blocked",
};

const REASON_KEY_RULES: Array<{ re: RegExp; key: string; fallback: string }> = [
  { re: /stale|veraltet/i, key: "stale", fallback: "Marktdaten sind veraltet." },
  {
    re: /no[_ -]?candles|keine kerzen|no candles/i,
    key: "no_candles",
    fallback: "Keine Marktdaten verfuegbar.",
  },
  { re: /quarant/i, key: "quarantine", fallback: "Asset in Quarantaene." },
  { re: /liquid/i, key: "liquidity", fallback: "Liquiditaet unzureichend." },
  { re: /spread/i, key: "spread", fallback: "Spread zu hoch." },
  {
    re: /risk|governor|policy/i,
    key: "governor",
    fallback: "Risk-Governor blockiert den Live-Pfad.",
  },
  {
    re: /exchange|bitget|upstream/i,
    key: "exchange",
    fallback: "Boersenpfad nicht stabil erreichbar.",
  },
];

function reasonToString(value: unknown): string {
  if (typeof value === "string") return value.trim();
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const o = value as Record<string, unknown>;
    const candidate = o.reason ?? o.message ?? o.code;
    if (typeof candidate === "string") return candidate.trim();
  }
  return String(value ?? "").trim();
}

export function tradeActionToken(action: string | null | undefined): DecisionToken {
  const key = (action ?? "").trim().toLowerCase();
  if (!key) {
    return { key: "not_set", fallback: "Nicht gesetzt" };
  }
  const mapped = TRADE_ACTION_KEY[key];
  if (mapped) {
    return {
      key: mapped,
      fallback: mapped.replace(/_/g, " "),
    };
  }
  return { key: "passthrough", vars: { raw: key }, fallback: key };
}

export function blockReasonTokens(reasons: unknown, maxItems = 3): DecisionToken[] {
  const rawItems = Array.isArray(reasons)
    ? reasons.slice(0, maxItems).map(reasonToString)
    : summarizeReasonsJsonForUi(reasons, maxItems);
  const out: DecisionToken[] = [];
  for (const raw of rawItems) {
    if (!raw) continue;
    let matched = false;
    for (const rule of REASON_KEY_RULES) {
      if (rule.re.test(raw)) {
        out.push({ key: rule.key, fallback: rule.fallback });
        matched = true;
        break;
      }
    }
    if (!matched) {
      out.push({ key: "passthrough", vars: { raw }, fallback: raw });
    }
  }
  if (out.length === 0) {
    return [{ key: "no_block_reasons", fallback: "Keine Blockgruende gemeldet." }];
  }
  return out;
}

export function signalRiskStatusToken(signal: SignalRecentItem): DecisionToken {
  const blocks = Array.isArray(signal.live_execution_block_reasons_json)
    ? signal.live_execution_block_reasons_json.length
    : 0;
  if (signal.live_execution_clear_for_real_money === true && blocks === 0) {
    return { key: "live_eligible", fallback: "Live-freigabefaehig" };
  }
  if ((signal.trade_action ?? "").toLowerCase() === "do_not_trade") {
    return { key: "do_not_trade", fallback: "Kein Trade" };
  }
  if (blocks > 0) {
    return {
      key: "live_blocked",
      vars: { count: blocks },
      fallback: `Live blockiert (${blocks})`,
    };
  }
  return { key: "release_unclear", fallback: "Freigabe unklar" };
}

export function signalLiveReleaseToken(detail: SignalDetail): DecisionToken {
  const action = (detail.trade_action ?? "").toLowerCase();
  const blocks = Array.isArray(detail.live_execution_block_reasons_json)
    ? detail.live_execution_block_reasons_json.length
    : 0;
  if (detail.live_execution_clear_for_real_money && blocks === 0) {
    return { key: "live_eligible", fallback: "Live freigabefaehig" };
  }
  if (action === "do_not_trade" || action === "blocked") {
    return { key: "live_blocked_any", fallback: "Live blockiert" };
  }
  if (blocks > 0) {
    return {
      key: "live_blocked",
      vars: { count: blocks },
      fallback: `Live blockiert (${blocks})`,
    };
  }
  return { key: "release_unclear", fallback: "Live nicht freigegeben" };
}

function metaToken(
  meta: Record<string, unknown> | null,
  key: string,
): { kind: "raw"; value: string } | null {
  if (!meta) return null;
  const v = meta[key];
  if (v == null) return null;
  const s = String(v).trim();
  if (!s) return null;
  return { kind: "raw", value: s };
}

export function signalAssetTierToken(detail: SignalDetail): DecisionToken {
  const meta = (detail.instrument_metadata ?? null) as Record<
    string,
    unknown
  > | null;
  const raw = metaToken(meta, "asset_tier");
  if (raw) {
    return { key: "passthrough", vars: { raw: raw.value }, fallback: raw.value };
  }
  return { key: "unknown", fallback: "unbekannt" };
}

export function signalDataQualityToken(detail: SignalDetail): DecisionToken {
  const meta = (detail.instrument_metadata ?? null) as Record<
    string,
    unknown
  > | null;
  const raw = metaToken(meta, "data_quality_status");
  if (raw) {
    return { key: "passthrough", vars: { raw: raw.value }, fallback: raw.value };
  }
  if (detail.instrument_metadata_verified === true) {
    return { key: "verified", fallback: "verifiziert" };
  }
  if (detail.instrument_metadata_verified === false) {
    return { key: "not_verified", fallback: "nicht verifiziert" };
  }
  return { key: "unknown", fallback: "unbekannt" };
}

export function signalLiquidityToken(detail: SignalDetail): DecisionToken {
  const meta = (detail.instrument_metadata ?? null) as Record<
    string,
    unknown
  > | null;
  const liq = metaToken(meta, "liquidity_status");
  if (liq) {
    return { key: "passthrough", vars: { raw: liq.value }, fallback: liq.value };
  }
  const spread = metaToken(meta, "spread_band");
  if (spread) {
    return {
      key: "spread_band",
      vars: { band: spread.value },
      fallback: `Spread-Band ${spread.value}`,
    };
  }
  return { key: "unknown", fallback: "unbekannt" };
}

export function signalDataAgeToken(
  analysisTsMs: number,
  nowTsMs: number = Date.now(),
): AgeToken {
  if (!Number.isFinite(analysisTsMs) || analysisTsMs <= 0) {
    return { key: "ageUnknown", fallback: "unbekannt" };
  }
  const diffMs = Math.max(0, nowTsMs - analysisTsMs);
  const sec = Math.floor(diffMs / 1000);
  if (sec < 60) {
    return { key: "ageSeconds", vars: { count: sec }, fallback: `vor ${sec}s` };
  }
  const min = Math.floor(sec / 60);
  if (min < 60) {
    return { key: "ageMinutes", vars: { count: min }, fallback: `vor ${min}m` };
  }
  const h = Math.floor(min / 60);
  return { key: "ageHours", vars: { count: h }, fallback: `vor ${h}h` };
}

/**
 * Bequemer Renderer fuer eine Translate-Funktion. Faellt auf den Fallback
 * zurueck, falls der i18n-Key nicht aufgeloest werden kann.
 */
export type TranslateLike = (
  key: string,
  vars?: Record<string, string | number | boolean>,
) => string;

export function renderDecisionToken(
  t: TranslateLike,
  scope: "pages.signalsDetail.decisionCenter" | "signalsTable",
  token: DecisionToken | AgeToken,
): string {
  const fullKey = `${scope}.${token.key}`;
  try {
    const translated = t(fullKey, token.vars);
    if (
      typeof translated === "string" &&
      translated.length > 0 &&
      translated !== fullKey
    ) {
      return translated;
    }
  } catch {
    // i18n provider fehlt — fallback
  }
  return token.fallback;
}
