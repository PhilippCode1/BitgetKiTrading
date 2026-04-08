import type { CandlestickData, HistogramData, Time } from "lightweight-charts";

import { PRODUCT_CHART_COLORS } from "@/lib/chart/product-chart-theme";

export type ProductCandleBar = Readonly<{
  time_s: number;
  open: number;
  high: number;
  low: number;
  close: number;
  /** Optional: USDT-Volumen (Live) oder anderes Mass — nur Anzeige */
  volume?: number;
  volume_usdt?: number;
}>;

export type MappedCandleVolume = Readonly<{
  candles: CandlestickData[];
  volume: HistogramData[];
}>;

function barVolume(bar: ProductCandleBar): number {
  if (typeof bar.volume_usdt === "number" && Number.isFinite(bar.volume_usdt)) {
    return bar.volume_usdt;
  }
  if (typeof bar.volume === "number" && Number.isFinite(bar.volume)) {
    return bar.volume;
  }
  return 0;
}

export function mapProductCandlesForLightweight(
  bars: readonly ProductCandleBar[],
): MappedCandleVolume {
  const candles: CandlestickData[] = [];
  const volume: HistogramData[] = [];
  for (const c of bars) {
    const t = c.time_s as Time;
    candles.push({
      time: t,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    });
    const v = barVolume(c);
    const up = c.close >= c.open;
    volume.push({
      time: t,
      value: v,
      color: up
        ? PRODUCT_CHART_COLORS.volumeUp
        : PRODUCT_CHART_COLORS.volumeDown,
    });
  }
  return { candles, volume };
}
