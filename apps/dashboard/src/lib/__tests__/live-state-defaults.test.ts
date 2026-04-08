import { emptyLiveStateResponse } from "@/lib/live-state-defaults";
import type { LiveStateResponse } from "@/lib/types";

describe("live-state-defaults", () => {
  it("erfüllt LiveStateResponse inkl. Pflichtfelder und Envelope", () => {
    const s: LiveStateResponse = emptyLiveStateResponse("BTCUSDT", "1m");
    expect(s.live_state_contract_version).toBe(0);
    expect(s.candles).toEqual([]);
    expect(s.latest_drawings).toEqual([]);
    expect(s.latest_news).toEqual([]);
    expect(s.data_lineage).toEqual([]);
    expect(s.market_freshness?.status).toBe("no_candles");
    expect(s.demo_data_notice?.reasons).toEqual([]);
    expect(s.status).toBe("degraded");
    expect(s.empty_state).toBe(true);
  });
});
