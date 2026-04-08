import type { IChartApi, ISeriesApi, Time } from "lightweight-charts";

import { PRODUCT_CHART_COLORS } from "@/lib/chart/product-chart-theme";
import type { SanitizedLlmChartAnnotations } from "@/lib/chart/llm-chart-annotations";

export type LlmChartPriceLineHandle = ReturnType<
  ISeriesApi<"Candlestick">["createPriceLine"]
>;

function safeRemovePriceLine(
  series: ISeriesApi<"Candlestick">,
  h: LlmChartPriceLineHandle,
): void {
  try {
    series.removePriceLine(h);
  } catch {
    /* ignore */
  }
}

function safeRemoveSeries(chart: IChartApi, s: ISeriesApi<"Line">): void {
  try {
    chart.removeSeries(s);
  } catch {
    /* ignore */
  }
}

export function clearLlmChartLayer(
  chart: IChartApi | null,
  candleSeries: ISeriesApi<"Candlestick"> | null,
  priceLineHandles: LlmChartPriceLineHandle[],
  lineSeries: ISeriesApi<"Line">[],
): void {
  if (candleSeries) {
    for (const h of priceLineHandles) {
      safeRemovePriceLine(candleSeries, h);
    }
  }
  priceLineHandles.length = 0;
  if (chart) {
    for (const s of lineSeries) {
      safeRemoveSeries(chart, s);
    }
  }
  lineSeries.length = 0;
  try {
    candleSeries?.setMarkers([]);
  } catch {
    /* ignore */
  }
}

/**
 * Zeichnet den KI-Chart-Layer. Fehler pro Element werden verschluckt, damit der Chart stabil bleibt.
 */
export function applyLlmChartLayer(
  chart: IChartApi,
  candleSeries: ISeriesApi<"Candlestick">,
  model: SanitizedLlmChartAnnotations,
  priceLineHandles: LlmChartPriceLineHandle[],
  lineSeries: ISeriesApi<"Line">[],
): void {
  clearLlmChartLayer(chart, candleSeries, priceLineHandles, lineSeries);

  for (const line of model.horizontalLines) {
    try {
      const h = candleSeries.createPriceLine({
        price: line.price,
        title: (line.label ?? "KI").slice(0, 26),
        color: PRODUCT_CHART_COLORS.llmLine,
        lineWidth: 1,
        lineStyle: line.lineStyle,
        axisLabelVisible: true,
      });
      priceLineHandles.push(h);
    } catch {
      /* skip invalid */
    }
  }

  for (const band of model.priceBands) {
    const base = (band.label ?? "KI Zone").slice(0, 20);
    for (const [price, suffix] of [
      [band.priceHigh, " max"],
      [band.priceLow, " min"],
    ] as const) {
      try {
        const h = candleSeries.createPriceLine({
          price,
          title: `${base}${suffix}`.slice(0, 26),
          color: PRODUCT_CHART_COLORS.llmLineMuted,
          lineWidth: 1,
          lineStyle: band.lineStyle,
          axisLabelVisible: true,
        });
        priceLineHandles.push(h);
      } catch {
        /* skip */
      }
    }
  }

  try {
    if (model.markers.length > 0) {
      candleSeries.setMarkers(model.markers);
    }
  } catch {
    try {
      candleSeries.setMarkers([]);
    } catch {
      /* ignore */
    }
  }

  const addLineSeries = (opts: {
    points: { time: Time; value: number }[];
    lineStyle: 0 | 1 | 2 | 3;
    color: string;
    lineWidth: 1 | 2 | 3 | 4;
  }): void => {
    if (opts.points.length < 2) return;
    try {
      const s = chart.addLineSeries({
        color: opts.color,
        lineWidth: opts.lineWidth,
        lineStyle: opts.lineStyle,
        lastValueVisible: false,
        priceLineVisible: false,
      });
      s.setData(opts.points);
      lineSeries.push(s);
    } catch {
      /* skip */
    }
  };

  for (const seg of model.lineSegments) {
    addLineSeries({
      points: seg.points,
      lineStyle: seg.lineStyle,
      color: PRODUCT_CHART_COLORS.llmLine,
      lineWidth: 2,
    });
  }

  for (const vr of model.verticalRules) {
    addLineSeries({
      points: vr.points,
      lineStyle: vr.lineStyle,
      color: PRODUCT_CHART_COLORS.llmLineMuted,
      lineWidth: 1,
    });
  }

  for (const ur of model.uncertaintyRegions) {
    addLineSeries({
      points: ur.points,
      lineStyle: 2,
      color: PRODUCT_CHART_COLORS.llmLineMuted,
      lineWidth: 1,
    });
  }
}
