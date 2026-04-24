import {
  liveCandleFromPayload,
  parsePayloadCandleClose,
} from "@/lib/chart/payload-candle-close";

describe("parsePayloadCandleClose", () => {
  it("mappt Schema-Felder 1:1", () => {
    const p = parsePayloadCandleClose({
      start_ts_ms: 1_700_000_000_000,
      open: 1,
      high: 2,
      low: 0.5,
      close: 1.5,
      usdt_vol: 100,
    });
    expect(p).toEqual({
      start_ts_ms: 1_700_000_000_000,
      open: 1,
      high: 2,
      low: 0.5,
      close: 1.5,
      usdt_vol: 100,
    });
  });

  it("konvertiert Non-Integer start_ts_ms via trunc", () => {
    const p = parsePayloadCandleClose({
      start_ts_ms: 1_700_000_000_500.2,
      open: 1,
      high: 1,
      low: 1,
      close: 1,
    });
    expect(p?.start_ts_ms).toBe(1_700_000_000_500);
  });

  it("erkennt LiveCandle-Shape (time_s)", () => {
    const p = parsePayloadCandleClose({
      time_s: 1_700_000_000,
      open: 1,
      high: 2,
      low: 0.5,
      close: 1.2,
      volume_usdt: 9,
    });
    expect(p).toEqual({
      start_ts_ms: 1_700_000_000_000,
      open: 1,
      high: 2,
      low: 0.5,
      close: 1.2,
      usdt_vol: 9,
    });
  });

  it("liveCandleFromPayload stellt time_s in Sekunden her", () => {
    const p = {
      start_ts_ms: 1_700_000_123_000,
      open: 1,
      high: 1,
      low: 1,
      close: 1,
    };
    const b = liveCandleFromPayload(p);
    expect(b.time_s).toBe(1_700_000_123);
  });
});
