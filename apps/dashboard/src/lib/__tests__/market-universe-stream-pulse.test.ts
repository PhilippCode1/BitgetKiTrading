import {
  effectivePipelineLagMs,
  pipelineLagBucket,
  vpinWarningLevel,
} from "@/lib/market-universe-stream-pulse";

describe("market-universe-stream-pulse", () => {
  it("nimmt pipeline_lag_ms bevorzugt", () => {
    const lag = effectivePipelineLagMs({ pipeline_lag_ms: 120 });
    expect(lag).toBe(120);
  });

  it("leitet Lag aus exchange/processed ab", () => {
    const lag = effectivePipelineLagMs({
      exchange_ts_ms: 1000,
      processed_ts_ms: 1600,
    });
    expect(lag).toBe(600);
  });

  it("bucket-Farben nach Schwelle", () => {
    expect(pipelineLagBucket(200)).toBe("ok");
    expect(pipelineLagBucket(800)).toBe("warn");
    expect(pipelineLagBucket(3000)).toBe("bad");
    expect(pipelineLagBucket(null)).toBe("unknown");
  });

  it("vpin warn level", () => {
    expect(vpinWarningLevel(0.5)).toBe("none");
    expect(vpinWarningLevel(0.75)).toBe("caution");
    expect(vpinWarningLevel(0.9)).toBe("halt");
  });
});
