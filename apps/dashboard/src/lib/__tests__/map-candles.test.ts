import { mapProductCandlesForLightweight } from "@/lib/chart/map-candles";

describe("mapProductCandlesForLightweight", () => {
  it("maps OHLC and volume_usdt", () => {
    const { candles, volume } = mapProductCandlesForLightweight([
      {
        time_s: 1700000000,
        open: 1,
        high: 2,
        low: 0.5,
        close: 1.5,
        volume_usdt: 1000,
      },
    ]);
    expect(candles).toHaveLength(1);
    expect(candles[0]).toMatchObject({
      open: 1,
      high: 2,
      low: 0.5,
      close: 1.5,
      time: 1700000000,
    });
    expect(volume[0].value).toBe(1000);
    expect(volume[0].color).toBeDefined();
  });

  it("uses volume field when volume_usdt missing", () => {
    const { volume } = mapProductCandlesForLightweight([
      { time_s: 1700000001, open: 1, high: 1, low: 1, close: 1, volume: 42 },
    ]);
    expect(volume[0].value).toBe(42);
  });

  it("colors volume by candle direction", () => {
    const up = mapProductCandlesForLightweight([
      { time_s: 1, open: 1, high: 2, low: 1, close: 2, volume: 1 },
    ]);
    const down = mapProductCandlesForLightweight([
      { time_s: 2, open: 2, high: 2, low: 1, close: 1, volume: 1 },
    ]);
    expect(up.volume[0].color).not.toBe(down.volume[0].color);
  });
});
