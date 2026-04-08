import { gatewayFetchErrorMessage } from "@/lib/gateway-fetch-errors";
import type { PaperTradeRow } from "@/lib/types";

/** @deprecated Prefer {@link gatewayFetchErrorMessage}; bleibt für bestehende Imports. */
export const paperSectionFetchErrorMessage = gatewayFetchErrorMessage;

/** Kurzvorschau für Journal-Detail-JSON (kein Scrollen in der Tabelle). */
export function previewPaperJournalDetail(
  detail: Record<string, unknown>,
  maxLen = 220,
): string {
  try {
    const s = JSON.stringify(detail);
    return s.length > maxLen ? `${s.slice(0, maxLen - 1)}…` : s;
  } catch {
    return "—";
  }
}

export type PaperClosedTradeStats = {
  closedCount: number;
  wins: number;
  losses: number;
  pnlSum: number;
  winRatePercent: number | null;
};

/** Nur Trades mit Abschlusszeit und PnL — konsistent mit der Performance-Karte. */
export function derivePaperClosedTradeStats(
  trades: readonly PaperTradeRow[],
): PaperClosedTradeStats {
  const closed = trades.filter(
    (row) => row.closed_ts_ms != null && row.pnl_net_usdt != null,
  );
  const wins = closed.filter((row) => (row.pnl_net_usdt ?? 0) > 0).length;
  const losses = closed.filter((row) => (row.pnl_net_usdt ?? 0) < 0).length;
  const pnlSum = closed.reduce((acc, row) => acc + (row.pnl_net_usdt ?? 0), 0);
  const winRatePercent =
    closed.length > 0 ? Math.round((wins / closed.length) * 1000) / 10 : null;
  return {
    closedCount: closed.length,
    wins,
    losses,
    pnlSum,
    winRatePercent,
  };
}
