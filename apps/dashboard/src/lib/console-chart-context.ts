import { normalizeChartTimeframe } from "@/lib/chart-prefs";
import { resolveTradeSymbol } from "@/lib/resolve-trade-symbol";

/**
 * Einheitliche Ableitung von Chart-Symbol und -Zeitfenster aus URL + persistierten Prefs + Defaults.
 * Bevorzugt `urlSymbol` (z. B. `?symbol=ETHUSDT`) — damit u. a. GET /v1/market-universe/candles und
 * SSE stets das gewaehlte Asset nutzen, ohne implizit BTCUSDT.
 */
export function resolveConsoleChartSymbolTimeframe(
  input: Readonly<{
    urlSymbol?: string | null;
    urlTimeframe?: string | null;
    persistedSymbol: string | null;
    persistedTimeframe: string | null;
    defaultSymbol: string;
    defaultTimeframe?: string | null;
  }>,
): { chartSymbol: string; chartTimeframe: string } {
  const rawSym =
    input.urlSymbol?.trim() ||
    input.persistedSymbol?.trim() ||
    input.defaultSymbol;
  const chartSymbol = resolveTradeSymbol(rawSym);
  const chartTimeframe =
    normalizeChartTimeframe(input.urlTimeframe) ??
    normalizeChartTimeframe(input.persistedTimeframe) ??
    normalizeChartTimeframe(input.defaultTimeframe) ??
    "5m";
  return { chartSymbol, chartTimeframe };
}

/**
 * Symbol-Picker-Optionen: Facetten-Liste, Watchlist oder mindestens das aktive Symbol.
 */
export function resolveConsoleChartSymbolOptions(
  input: Readonly<{
    facetSymbols?: readonly string[] | null;
    watchlist: readonly string[];
    chartSymbol: string;
  }>,
): string[] {
  const fromFacets =
    input.facetSymbols && input.facetSymbols.length > 0
      ? [...input.facetSymbols]
      : null;
  const base = fromFacets ?? [...input.watchlist];
  const merged = Array.from(
    new Set([...base, input.chartSymbol].filter((s) => s.length > 0)),
  );
  return merged.length > 0 ? merged : [input.chartSymbol];
}
