import {
  emptyPaperJournalResponse,
  emptyPaperLedgerResponse,
  emptyPaperMetricsResponse,
  emptyPaperOpenResponse,
  emptyPaperTradesResponse,
} from "@/lib/paper-response-defaults";
import type {
  PaperJournalResponse,
  PaperLedgerResponse,
  PaperMetricsResponse,
  PaperOpenResponse,
  PaperTradesResponse,
} from "@/lib/types";

describe("paper-response-defaults", () => {
  it("erfüllt GatewayReadEnvelope + Pflicht-Payload pro Paper-Route", () => {
    const o: PaperOpenResponse = emptyPaperOpenResponse();
    expect(o.positions).toEqual([]);
    expect(o.status).toBe("ok");

    const tr: PaperTradesResponse = emptyPaperTradesResponse(12);
    expect(tr.trades).toEqual([]);
    expect(tr.limit).toBe(12);

    const m: PaperMetricsResponse = emptyPaperMetricsResponse();
    expect(m.account).toBeNull();
    expect(m.fees_total_usdt).toBe(0);
    expect(m.funding_total_usdt).toBe(0);
    expect(m.equity_curve).toEqual([]);
    expect(m.account_ledger_recent).toEqual([]);

    const j: PaperJournalResponse = emptyPaperJournalResponse(20);
    expect(j.events).toEqual([]);
    expect(j.limit).toBe(20);

    const l: PaperLedgerResponse = emptyPaperLedgerResponse(40);
    expect(l.entries).toEqual([]);
    expect(l.limit).toBe(40);
    expect(l.status).toBe("ok");
  });
});
