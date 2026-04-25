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
import type {
  LiveBrokerOrderActionItem,
  LiveBrokerOrderItem,
  LiveBrokerRuntimeItem,
  LiveStateResponse,
  SystemHealthResponse,
} from "@/lib/types";

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

const SECRET_RX =
  /\bauthorization\b\s*[:=]\s*bearer\s+\S+|\b(authorization|bearer|token|secret|api[_-]?key|password)\b\s*[:=]\s*\S+/gi;

export function sanitizeBrokerErrorDetail(raw: string | null | undefined): string {
  if (!raw) return "";
  return raw.slice(0, 220).replace(SECRET_RX, "$1=***");
}

export function brokerLiveBlockers(params: {
  runtime: LiveBrokerRuntimeItem | null | undefined;
  health: SystemHealthResponse | null | undefined;
  orderCount: number;
}): string[] {
  const blockers: string[] = [];
  const { runtime, health } = params;
  if (!runtime) blockers.push("Live-Runtime fehlt");
  if (runtime?.safety_latch_active) blockers.push("Safety-Latch aktiv");
  if ((runtime?.active_kill_switches?.length ?? 0) > 0) blockers.push("Kill-Switch aktiv");
  const reconcile = health?.ops?.live_broker?.latest_reconcile_status ?? null;
  if (!reconcile || reconcile !== "ok") blockers.push("Reconcile nicht ok");
  if (runtime?.upstream_ok === false) blockers.push("Bitget Private Readiness gestört");
  return Array.from(new Set(blockers));
}

export function brokerLiveTradingStatus(params: {
  runtime: LiveBrokerRuntimeItem | null | undefined;
  health: SystemHealthResponse | null | undefined;
}): "ja" | "nein" | "blockiert" {
  const blockers = brokerLiveBlockers({
    runtime: params.runtime,
    health: params.health,
    orderCount: 0,
  });
  if (blockers.length > 0) return "blockiert";
  if (params.runtime?.live_trade_enable && params.runtime?.live_order_submission_enabled) {
    return "ja";
  }
  return "nein";
}

export function brokerUnknownStates(params: {
  runtime: LiveBrokerRuntimeItem | null | undefined;
  health: SystemHealthResponse | null | undefined;
}): string[] {
  const out: string[] = [];
  if (!params.runtime?.bitget_private_status) out.push("Bitget-Private-Status unbekannt");
  if (!params.health?.ops?.live_broker?.latest_reconcile_created_ts) {
    out.push("Reconcile-Zeitpunkt unbekannt");
  }
  if (params.runtime?.strategy_execution_mode == null) {
    out.push("Strategy-Execution-Modus unbekannt");
  }
  return out;
}

export function brokerLastOrderActionSummary(params: {
  orders: readonly LiveBrokerOrderItem[];
  orderActions: readonly LiveBrokerOrderActionItem[];
}): string {
  const lastOrder = params.orders[0];
  const lastAction = params.orderActions[0];
  if (!lastOrder && !lastAction) return "Keine Order/Action vorhanden";
  const orderPart = lastOrder
    ? `${lastOrder.symbol} ${lastOrder.status} (${lastOrder.last_action})`
    : "keine Order";
  const actionPart = lastAction
    ? `${lastAction.action} ${lastAction.http_status ?? "?"}`
    : "keine Action";
  return `${orderPart} · ${actionPart}`;
}
