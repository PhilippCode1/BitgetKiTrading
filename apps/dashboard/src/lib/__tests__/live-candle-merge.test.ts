import {
  mergeCandle,
  mergeRestCandlesWithSseBuffer,
} from "@/lib/live-candle-merge";
import type { LiveCandle } from "@/lib/types";

const bar = (time_s: number, close: number): LiveCandle => ({
  time_s,
  open: close,
  high: close,
  low: close,
  close,
  volume_usdt: 0,
});

describe("mergeRestCandlesWithSseBuffer", () => {
  it("fuegt nur Events ab einschliesslich letzter REST-Kerze ein", () => {
    const rest: LiveCandle[] = [bar(100, 1), bar(200, 2), bar(300, 3)];
    const buffer: LiveCandle[] = [bar(150, 9), bar(300, 3.1), bar(400, 4)];
    const m = mergeRestCandlesWithSseBuffer(rest, buffer);
    expect(m.map((c) => c.time_s)).toEqual([100, 200, 300, 400]);
    expect(m.find((c) => c.time_s === 300)!.close).toBe(3.1);
    expect(m.find((c) => c.time_s === 400)!.close).toBe(4);
  });

  it("REST leer: wendet gepufferten Strom voll an", () => {
    const m = mergeRestCandlesWithSseBuffer([], [bar(10, 1), bar(20, 2)]);
    expect(m).toEqual([bar(10, 1), bar(20, 2)]);
  });
});

describe("mergeCandle", () => {
  it("aktualisiert eine bestehende Zeitstufe", () => {
    const a = [bar(1, 1)];
    const b = mergeCandle(a, bar(1, 1.5));
    expect(b).toEqual([bar(1, 1.5)]);
  });
});
