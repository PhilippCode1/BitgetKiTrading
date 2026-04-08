import type { ISeriesApi } from "lightweight-charts";

import { PRODUCT_CHART_COLORS } from "@/lib/chart/product-chart-theme";
import type { StrategyOverlayLayerId } from "@/lib/chart/strategy-overlay-model";

export type StrategyOverlayPriceLineHandle = ReturnType<
  ISeriesApi<"Candlestick">["createPriceLine"]
>;

const LAYER_STYLE: Record<
  StrategyOverlayLayerId,
  { color: string; lineStyle: 0 | 1 | 2 | 3; lineWidth: 1 | 2 | 3 | 4 }
> = {
  reference: {
    color: PRODUCT_CHART_COLORS.mutedLine,
    lineStyle: 2,
    lineWidth: 1,
  },
  stop_loss: { color: PRODUCT_CHART_COLORS.down, lineStyle: 0, lineWidth: 2 },
  take_profit_mfe: {
    color: PRODUCT_CHART_COLORS.up,
    lineStyle: 0,
    lineWidth: 2,
  },
  risk_mae: { color: "#c9a227", lineStyle: 2, lineWidth: 1 },
  stop_budget_max: {
    color: "rgba(224, 112, 112, 0.65)",
    lineStyle: 1,
    lineWidth: 1,
  },
  stop_min_executable: {
    color: "rgba(163, 154, 140, 0.9)",
    lineStyle: 1,
    lineWidth: 1,
  },
};

export function clearStrategyOverlayPriceLines(
  series: ISeriesApi<"Candlestick"> | null,
  handles: StrategyOverlayPriceLineHandle[],
): void {
  if (!series) {
    handles.length = 0;
    return;
  }
  for (const h of handles) {
    try {
      series.removePriceLine(h);
    } catch {
      /* ignore */
    }
  }
  handles.length = 0;
}

export function applyStrategyOverlayPriceLines(
  series: ISeriesApi<"Candlestick">,
  lines: ReadonlyArray<{
    id: StrategyOverlayLayerId;
    price: number;
    axisLabel: string;
  }>,
  visible: Readonly<Partial<Record<StrategyOverlayLayerId, boolean>>>,
  handles: StrategyOverlayPriceLineHandle[],
): void {
  clearStrategyOverlayPriceLines(series, handles);
  for (const line of lines) {
    if (visible[line.id] === false) continue;
    const st = LAYER_STYLE[line.id];
    const label = line.axisLabel.slice(0, 28);
    const h = series.createPriceLine({
      price: line.price,
      title: label,
      color: st.color,
      lineWidth: st.lineWidth,
      lineStyle: st.lineStyle,
      axisLabelVisible: true,
    });
    handles.push(h);
  }
}
