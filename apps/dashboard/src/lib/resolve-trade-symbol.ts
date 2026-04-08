import { publicEnv } from "@/lib/env";

/** Normalisiert UI-/URL-Eingaben zum Bitget-Symbolformat (z. B. btc-usdt → BTCUSDT). */
export function normalizeTradeSymbolInput(raw: string): string {
  return raw
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, "");
}

/**
 * Verhindert leere Symbol-Parameter (kaputte API-Aufrufe), wenn NEXT_PUBLIC_DEFAULT_SYMBOL
 * und Watchlist nicht gesetzt sind.
 */
export function resolveTradeSymbol(override?: string | null): string {
  const a = normalizeTradeSymbolInput(override ?? "");
  if (a) return a;
  const b = (publicEnv.defaultSymbol ?? "").trim();
  if (b) return b;
  return "BTCUSDT";
}
