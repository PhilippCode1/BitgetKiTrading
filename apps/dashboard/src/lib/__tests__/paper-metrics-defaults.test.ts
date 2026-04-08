import { emptyPaperMetricsResponse } from "@/lib/paper-metrics-defaults";
import type { PaperMetricsResponse } from "@/lib/types";

describe("paper-metrics-defaults", () => {
  it("emptyPaperMetricsResponse erfuellt PaperMetricsResponse inkl. GatewayReadEnvelope", () => {
    const m: PaperMetricsResponse = emptyPaperMetricsResponse();
    expect(m.status).toBe("ok");
    expect(m.empty_state).toBe(false);
    expect(m.account).toBeNull();
    expect(m.equity_curve).toEqual([]);
    expect(m.account_ledger_recent).toEqual([]);
  });
});
