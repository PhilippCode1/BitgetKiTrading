import {
  derivePaperClosedTradeStats,
  paperSectionFetchErrorMessage,
  previewPaperJournalDetail,
} from "@/lib/paper-console";
import type { PaperTradeRow } from "@/lib/types";

describe("paper-console", () => {
  it("paperSectionFetchErrorMessage liefert Nachricht oder String", () => {
    expect(paperSectionFetchErrorMessage(new Error("x"))).toBe("x");
    expect(paperSectionFetchErrorMessage("timeout")).toBe("timeout");
  });

  it("previewPaperJournalDetail kürzt lange JSON-Strings", () => {
    const long = { a: "x".repeat(300) };
    const s = previewPaperJournalDetail(long, 50);
    expect(s.length).toBeLessThanOrEqual(50);
    expect(s.endsWith("…")).toBe(true);
  });

  it("derivePaperClosedTradeStats zählt nur Trades mit Abschluss und PnL", () => {
    const rows: PaperTradeRow[] = [
      {
        position_id: "1",
        symbol: "BTCUSDT",
        side: "long",
        qty_base: "1",
        entry_price_avg: "1",
        closed_ts_ms: 100,
        state: "closed",
        pnl_net_usdt: 10,
        fees_total_usdt: 0,
        funding_total_usdt: 0,
        direction_correct: null,
        reason_closed: null,
        meta: {},
      },
      {
        position_id: "2",
        symbol: "BTCUSDT",
        side: "short",
        qty_base: "1",
        entry_price_avg: "1",
        closed_ts_ms: 200,
        state: "closed",
        pnl_net_usdt: -3,
        fees_total_usdt: 0,
        funding_total_usdt: 0,
        direction_correct: null,
        reason_closed: null,
        meta: {},
      },
      {
        position_id: "3",
        symbol: "ETHUSDT",
        side: "long",
        qty_base: "1",
        entry_price_avg: "1",
        closed_ts_ms: null,
        state: "open",
        pnl_net_usdt: null,
        fees_total_usdt: null,
        funding_total_usdt: null,
        direction_correct: null,
        reason_closed: null,
        meta: {},
      },
    ];
    const s = derivePaperClosedTradeStats(rows);
    expect(s.closedCount).toBe(2);
    expect(s.wins).toBe(1);
    expect(s.losses).toBe(1);
    expect(s.pnlSum).toBe(7);
    expect(s.winRatePercent).toBe(50);
  });
});
