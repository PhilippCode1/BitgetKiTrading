/**
 * Operatorkonsole / Paper / Live-Broker: TanStack-Query-Keys und SSE-Payload-Logik.
 * BFF-Stream: Gateway mappt `trade_opened` | `trade_updated` | `trade_closed` (Schema payload_trade_lifecycle) auf Event `paper` [event_type + payload im JSON-Body des SSE-Frames].
 */

import type { QueryClient } from "@tanstack/react-query";

import {
  fetchLiveBrokerOrders,
  fetchLiveState,
  fetchPaperOpen,
} from "@/lib/api";
import type { LiveStateResponse, SystemHealthResponse } from "@/lib/types";

export const SYSTEM_HEALTH_QUERY_KEY = ["system", "health"] as const;

export function liveStateQueryKey(
  symbol: string,
  timeframe: string,
): readonly [string, string, string, string] {
  return ["live", "state", symbol, timeframe];
}

export function paperOpenQueryKey(
  symbol: string | null | undefined,
): readonly [string, string, string, string] {
  const s = (symbol ?? "all").trim() || "all";
  return ["paper", "positions", "open", s];
}

export const liveBrokerOrdersQueryKey = ["live-broker", "orders", "recent"] as const;

export function isPaperSseForTradeLifecycle(raw: unknown): boolean {
  if (raw == null || typeof raw !== "object" || Array.isArray(raw)) {
    return false;
  }
  const o = raw as Record<string, unknown>;
  const et = typeof o.event_type === "string" ? o.event_type : "";
  if (
    et === "trade_opened" ||
    et === "trade_updated" ||
    et === "trade_closed"
  ) {
    return true;
  }
  const pl = o.payload;
  if (pl && typeof pl === "object" && pl !== null && "lifecycle_phase" in pl) {
    const ph = (pl as { lifecycle_phase?: string }).lifecycle_phase;
    if (ph === "POSITION_UPDATE" || ph === "ORDER_FILLED") {
      return true;
    }
  }
  return false;
}

/**
 * `GET /v1/system/health` — Safety Latch (Prompt 21) blockiert sinnvolle Automatik-Interaktion.
 */
export function isLiveBrokerGlobalHaltFromHealth(
  health: SystemHealthResponse | null | undefined,
): boolean {
  if (!health?.ops?.live_broker) return false;
  return health.ops.live_broker.safety_latch_active === true;
}

type FetchStateParams = Readonly<{
  symbol: string;
  timeframe: string;
  limit?: number;
}>;

/**
 * Liest Live-State + Paper-Offene + Brooker-Orders und legt Caches (setQueryData) an — ohne sichtbares Leeren.
 */
export async function fetchAndApplyTradeLifecycleCaches(
  queryClient: QueryClient,
  params: FetchStateParams,
): Promise<LiveStateResponse> {
  const { symbol, timeframe, limit = 500 } = params;
  const live = await fetchLiveState({ symbol, timeframe, limit });
  queryClient.setQueryData(liveStateQueryKey(symbol, timeframe), live);

  const [p, o] = await Promise.allSettled([
    fetchPaperOpen(symbol),
    fetchLiveBrokerOrders(),
  ]);
  if (p.status === "fulfilled") {
    queryClient.setQueryData(paperOpenQueryKey(symbol), p.value);
  }
  if (o.status === "fulfilled") {
    queryClient.setQueryData(liveBrokerOrdersQueryKey, o.value);
  }
  return live;
}

export function orderStatusCountsNonEmpty(
  counts: Record<string, number> | null | undefined,
): boolean {
  if (!counts || typeof counts !== "object") return false;
  return Object.keys(counts).length > 0;
}

export function prettyJsonLine(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

export function recordHasKeys(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object")
    return Object.keys(value as Record<string, unknown>).length > 0;
  return true;
}
