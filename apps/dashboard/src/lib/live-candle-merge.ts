import type { LiveCandle } from "@/lib/types";

const MAX_CANDLES = 2000;

/**
 * Fuegt eine Kerze in eine aufsteigend sortierte Liste ein: gleiche time_s ersetzen,
 * neue Zeit hinzufuegen, auf Max-Laenge stutzen.
 */
export function mergeCandle(list: LiveCandle[], bar: LiveCandle): LiveCandle[] {
  const next = [...list];
  const i = next.findIndex((c) => c.time_s === bar.time_s);
  if (i >= 0) {
    next[i] = bar;
  } else {
    next.push(bar);
  }
  next.sort((a, b) => a.time_s - b.time_s);
  if (next.length > MAX_CANDLES) {
    return next.slice(-MAX_CANDLES);
  }
  return next;
}

/**
 * REST-Historie (tsdb) mit zwischenzeitlich gepufferten SSE-Events: keine Luecke, keine
 * doppelte Zeit-Identitaet (spaeteres Event gewinnt bei gleichem time_s ab lastRest time_s).
 */
export function mergeRestCandlesWithSseBuffer(
  rest: readonly LiveCandle[],
  sseBuffer: readonly LiveCandle[],
): LiveCandle[] {
  const lastTime = rest.length > 0 ? rest[rest.length - 1]!.time_s : -Number.MAX_SAFE_INTEGER;
  let out: LiveCandle[] = rest.length > 0 ? [...rest] : [];
  for (const b of sseBuffer) {
    if (b.time_s < lastTime) {
      continue;
    }
    out = mergeCandle(out, b);
  }
  return out;
}
