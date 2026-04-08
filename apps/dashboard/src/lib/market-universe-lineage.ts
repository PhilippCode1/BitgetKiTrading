import type {
  MarketUniverseInstrumentItem,
  SystemHealthResponse,
  SystemHealthServiceItem,
} from "@/lib/types";

/** Kernsymbole fuer Transparenz-Zeile (Gateway/Bitget-Standard). */
export const MARKET_UNIVERSE_CORE_SYMBOLS: readonly string[] = [
  "BTCUSDT",
  "ETHUSDT",
];

export function serviceByName(
  services: SystemHealthServiceItem[] | undefined,
  name: string,
): SystemHealthServiceItem | null {
  if (!services?.length) return null;
  return services.find((s) => s.name === name) ?? null;
}

export function findInstrumentBySymbol(
  instruments: readonly MarketUniverseInstrumentItem[],
  symbol: string,
): MarketUniverseInstrumentItem | null {
  const u = symbol.trim().toUpperCase();
  const direct = instruments.find((i) => i.symbol.toUpperCase() === u);
  if (direct) return direct;
  return (
    instruments.find((i) =>
      i.symbol_aliases.some((a) => a.toUpperCase() === u),
    ) ?? null
  );
}

/** Kurztext aus market-stream /health bitget_ws_stream (ohne Secrets). */
export function summarizeWsTelemetry(
  raw: Record<string, unknown> | undefined,
): string {
  if (!raw || typeof raw !== "object") return "";
  const parts: string[] = [];
  for (const k of [
    "connected",
    "connection_state",
    "state",
    "ready",
    "subscriptions",
    "subscription_count",
  ]) {
    if (k in raw && raw[k] != null && raw[k] !== "")
      parts.push(`${k}=${String(raw[k]).slice(0, 48)}`);
  }
  if (parts.length) return parts.slice(0, 5).join(", ");
  try {
    return JSON.stringify(raw).slice(0, 160);
  } catch {
    return "";
  }
}

export function formatServiceStatus(s: SystemHealthServiceItem | null): string {
  if (!s) return "";
  const bits = [
    s.status,
    s.ready === false ? "not_ready" : null,
    s.note,
    s.detail,
  ]
    .filter(Boolean)
    .map(String);
  return bits.join(" · ").slice(0, 220);
}

export type MarketUniverseLineageBuildInput = Readonly<{
  health: SystemHealthResponse | null;
  instruments: readonly MarketUniverseInstrumentItem[];
  lastCandleTsMs: number | null;
  lastSignalTsMs: number | null;
}>;

export type CoreSymbolRow = Readonly<{
  symbol: string;
  inRegistry: boolean;
  liveEnabled: boolean;
  subscribeEnabled: boolean;
  tradingEnabled: boolean;
  tradingStatus: string;
}>;

export function buildCoreSymbolRows(
  instruments: readonly MarketUniverseInstrumentItem[],
  coreSymbols: readonly string[] = MARKET_UNIVERSE_CORE_SYMBOLS,
): CoreSymbolRow[] {
  return coreSymbols.map((symbol) => {
    const inst = findInstrumentBySymbol(instruments, symbol);
    return {
      symbol,
      inRegistry: Boolean(inst),
      liveEnabled: Boolean(inst?.live_execution_enabled),
      subscribeEnabled: Boolean(inst?.subscribe_enabled),
      tradingEnabled: Boolean(inst?.trading_enabled),
      tradingStatus: inst?.trading_status ?? "—",
    };
  });
}
