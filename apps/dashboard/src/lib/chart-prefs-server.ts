import { cookies } from "next/headers";

import {
  CHART_SYMBOL_COOKIE,
  CHART_TIMEFRAME_COOKIE,
  normalizeChartSymbolCookie,
  normalizeChartTimeframe,
} from "@/lib/chart-prefs";

export async function readConsoleChartPrefs(): Promise<{
  symbol: string | null;
  timeframe: string | null;
}> {
  const c = await cookies();
  return {
    symbol: normalizeChartSymbolCookie(
      c.get(CHART_SYMBOL_COOKIE)?.value ?? null,
    ),
    timeframe: normalizeChartTimeframe(
      c.get(CHART_TIMEFRAME_COOKIE)?.value ?? null,
    ),
  };
}
