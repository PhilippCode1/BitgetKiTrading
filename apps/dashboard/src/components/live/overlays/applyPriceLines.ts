import type { ISeriesApi } from "lightweight-charts";

import type { LiveDrawing } from "@/lib/types";

export type PriceLineHandle = ReturnType<
  ISeriesApi<"Candlestick">["createPriceLine"]
>;

export function clearPriceLines(
  series: ISeriesApi<"Candlestick">,
  handles: PriceLineHandle[],
): void {
  for (const h of handles) {
    try {
      series.removePriceLine(h);
    } catch {
      /* ignore */
    }
  }
  handles.length = 0;
}

export function applyPriceLines(
  series: ISeriesApi<"Candlestick">,
  drawings: LiveDrawing[],
  handles: PriceLineHandle[],
): void {
  clearPriceLines(series, handles);
  for (const d of drawings) {
    for (const pl of d.price_lines) {
      const line = series.createPriceLine({
        price: pl.price,
        title: pl.title.slice(0, 24),
        color: pl.color,
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
      });
      handles.push(line);
    }
  }
}
