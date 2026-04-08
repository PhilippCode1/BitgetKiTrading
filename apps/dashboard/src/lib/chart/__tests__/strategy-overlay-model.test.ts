import {
  buildStrategyOverlayModel,
  normalizeSignalDirection,
  resolveStrategyReferencePrice,
} from "@/lib/chart/strategy-overlay-model";
import type { LiveSignal } from "@/lib/types";

describe("strategy-overlay-model", () => {
  it("resolveStrategyReferencePrice prefers mark over ticker over close", () => {
    expect(
      resolveStrategyReferencePrice({
        markPrice: 100,
        tickerLast: 200,
        lastCandleClose: 300,
      }),
    ).toEqual({ price: 100, source: "mark_price" });
    expect(
      resolveStrategyReferencePrice({
        markPrice: null,
        tickerLast: 200,
        lastCandleClose: 300,
      }),
    ).toEqual({ price: 200, source: "ticker_last" });
    expect(
      resolveStrategyReferencePrice({
        markPrice: null,
        tickerLast: null,
        lastCandleClose: 300,
      }),
    ).toEqual({ price: 300, source: "last_candle_close" });
    expect(
      resolveStrategyReferencePrice({
        markPrice: null,
        tickerLast: null,
        lastCandleClose: null,
      }),
    ).toBeNull();
  });

  it("normalizeSignalDirection maps common aliases", () => {
    expect(normalizeSignalDirection("LONG")).toBe("long");
    expect(normalizeSignalDirection("buy")).toBe("long");
    expect(normalizeSignalDirection("Short")).toBe("short");
    expect(normalizeSignalDirection("unknown")).toBeNull();
  });

  it("buildStrategyOverlayModel derives long stop and MFE/MAE from backend ratios", () => {
    const ref = { price: 100_000, source: "mark_price" as const };
    const signal = {
      signal_id: "s1",
      direction: "long",
      signal_strength_0_100: 50,
      probability_0_1: 0.5,
      signal_class: "test",
      risk_warnings_json: [],
      stop_distance_pct: 0.01,
      expected_mfe_bps: 100,
      expected_mae_bps: 50,
    } as LiveSignal;

    const m = buildStrategyOverlayModel({ signal, reference: ref });
    expect(m.direction).toBe("long");
    const byId = Object.fromEntries(m.lines.map((l) => [l.id, l.price]));
    expect(byId.reference).toBe(100_000);
    expect(byId.stop_loss).toBeCloseTo(99_000, 6);
    expect(byId.take_profit_mfe).toBeCloseTo(101_000, 6);
    expect(byId.risk_mae).toBeCloseTo(99_500, 6);
  });

  it("buildStrategyOverlayModel derives short stop inversely", () => {
    const ref = { price: 50_000, source: "ticker_last" as const };
    const signal = {
      signal_id: "s2",
      direction: "short",
      signal_strength_0_100: 50,
      probability_0_1: 0.5,
      signal_class: "test",
      risk_warnings_json: [],
      stop_distance_pct: 0.004,
    } as LiveSignal;

    const m = buildStrategyOverlayModel({ signal, reference: ref });
    expect(m.direction).toBe("short");
    const stop = m.lines.find((l) => l.id === "stop_loss");
    expect(stop?.price).toBeCloseTo(50_200, 6);
  });

  it("omits directional lines when direction is unknown", () => {
    const ref = { price: 100, source: "last_candle_close" as const };
    const signal = {
      signal_id: "s3",
      direction: "flat",
      signal_strength_0_100: 0,
      probability_0_1: 0,
      signal_class: "test",
      risk_warnings_json: [],
      stop_distance_pct: 0.01,
    } as LiveSignal;

    const m = buildStrategyOverlayModel({ signal, reference: ref });
    expect(m.lines.map((l) => l.id)).toEqual(["reference"]);
  });
});
