import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import {
  CHART_PREF_COOKIE_MAX_AGE,
  CHART_SYMBOL_COOKIE,
  CHART_TIMEFRAME_COOKIE,
  normalizeChartSymbolCookie,
  normalizeChartTimeframe,
} from "@/lib/chart-prefs";

type Body = { symbol?: unknown; timeframe?: unknown };

/**
 * Setzt Chart-Defaults fuer die Konsole (Symbol/Zeitfenster). Keine Secrets.
 */
export async function POST(req: Request) {
  let body: Body;
  try {
    body = (await req.json()) as Body;
  } catch {
    return NextResponse.json(
      { ok: false, error: "invalid_json" },
      { status: 400 },
    );
  }
  const cookieStore = await cookies();
  const sym =
    typeof body.symbol === "string"
      ? normalizeChartSymbolCookie(body.symbol)
      : null;
  const tf =
    typeof body.timeframe === "string"
      ? normalizeChartTimeframe(body.timeframe)
      : null;

  const base = {
    path: "/",
    maxAge: CHART_PREF_COOKIE_MAX_AGE,
    sameSite: "lax" as const,
    httpOnly: false,
  };

  if (sym) {
    cookieStore.set(CHART_SYMBOL_COOKIE, sym, base);
  }
  if (tf) {
    cookieStore.set(CHART_TIMEFRAME_COOKIE, tf, base);
  }

  return NextResponse.json({ ok: true, symbol: sym, timeframe: tf });
}
