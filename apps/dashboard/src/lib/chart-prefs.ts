import { normalizeTradeSymbolInput } from "@/lib/resolve-trade-symbol";

/** Persistente Konsole: letztes Symbol/Zeitfenster fuer Charts (nicht HttpOnly — nur UI-Defaults). */
export const CHART_SYMBOL_COOKIE = "bitget_console_chart_symbol";
export const CHART_TIMEFRAME_COOKIE = "bitget_console_chart_tf";

export const CHART_PREF_COOKIE_MAX_AGE = 60 * 60 * 24 * 400;

const ALLOWED_TF = new Set(["1m", "5m", "15m", "1h", "4h", "1d"]);

export function normalizeChartTimeframe(
  raw: string | null | undefined,
): string | null {
  const s = (raw ?? "").trim().toLowerCase();
  if (!s) return null;
  const compact = s.replace(/\s+/g, "");
  return ALLOWED_TF.has(compact) ? compact : null;
}

export function normalizeChartSymbolCookie(
  raw: string | null | undefined,
): string | null {
  const n = normalizeTradeSymbolInput(raw ?? "");
  return n.length >= 4 ? n : null;
}

export function mergeConsoleChartSearch(
  pathname: string,
  base: Record<string, string | undefined>,
  patch: Partial<{ symbol: string; timeframe: string }>,
): string {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(base)) {
    if (v === undefined || v === "") continue;
    u.set(k, v);
  }
  if (patch.symbol !== undefined) u.set("symbol", patch.symbol);
  if (patch.timeframe !== undefined) u.set("timeframe", patch.timeframe);
  const q = u.toString();
  return q ? `${pathname}?${q}` : pathname;
}
