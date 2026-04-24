import type { IChartApi, ISeriesApi, Time } from "lightweight-charts";

import type { LlmZoneRole } from "@/lib/chart/llm-chart-annotations";
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

function safeRemoveSeries(
  chart: IChartApi,
  s: ISeriesApi<"Line"> | ISeriesApi<"Baseline">,
): void {
  try {
    chart.removeSeries(s);
  } catch {
    /* ignore */
  }
}

function baselineOptionsForLlmRole(role: LlmZoneRole): {
  topLineColor: string;
  topFillColor1: string;
  topFillColor2: string;
  bottomLineColor: string;
  bottomFillColor1: string;
  bottomFillColor2: string;
} {
  switch (role) {
    case "resistance":
      return {
        topLineColor: PRODUCT_CHART_COLORS.llmZoneResistanceTopLine,
        topFillColor1: PRODUCT_CHART_COLORS.llmZoneResistanceTopFill1,
        topFillColor2: PRODUCT_CHART_COLORS.llmZoneResistanceTopFill2,
        bottomLineColor: "rgba(0,0,0,0)",
        bottomFillColor1: "rgba(0,0,0,0)",
        bottomFillColor2: "rgba(0,0,0,0)",
      };
    case "support":
      return {
        topLineColor: PRODUCT_CHART_COLORS.llmZoneSupportTopLine,
        topFillColor1: PRODUCT_CHART_COLORS.llmZoneSupportTopFill1,
        topFillColor2: PRODUCT_CHART_COLORS.llmZoneSupportTopFill2,
        bottomLineColor: "rgba(0,0,0,0)",
        bottomFillColor1: "rgba(0,0,0,0)",
        bottomFillColor2: "rgba(0,0,0,0)",
      };
    default:
      return {
        topLineColor: PRODUCT_CHART_COLORS.llmZoneNeutralTopLine,
        topFillColor1: PRODUCT_CHART_COLORS.llmZoneNeutralTopFill1,
        topFillColor2: PRODUCT_CHART_COLORS.llmZoneNeutralTopFill2,
        bottomLineColor: "rgba(0,0,0,0)",
        bottomFillColor1: "rgba(0,0,0,0)",
        bottomFillColor2: "rgba(0,0,0,0)",
      };
  }
}

export type LlmChartBaselineHandle = ISeriesApi<"Baseline">;

export function clearLlmChartLayer(
  chart: IChartApi | null,
  candleSeries: ISeriesApi<"Candlestick"> | null,
  priceLineHandles: LlmChartPriceLineHandle[],
  lineSeries: ISeriesApi<"Line">[],
  baselineSeries: LlmChartBaselineHandle[] = [],
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
    for (const b of baselineSeries) {
      safeRemoveSeries(chart, b);
    }
  }
  lineSeries.length = 0;
  baselineSeries.length = 0;
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
  baselineSeries: LlmChartBaselineHandle[],
): void {
  clearLlmChartLayer(
    chart,
    candleSeries,
    priceLineHandles,
    lineSeries,
    baselineSeries,
  );

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

  for (const zone of model.filledZones) {
    const pBase = Math.min(zone.priceHigh, zone.priceLow);
    const pTop = Math.max(zone.priceHigh, zone.priceLow);
    if (pTop <= pBase) {
      continue;
    }
    const col = baselineOptionsForLlmRole(zone.role);
    try {
      const s = chart.addBaselineSeries({
        baseValue: { type: "price", price: pBase },
        ...col,
        lineWidth: 1,
        lineVisible: true,
        lastValueVisible: false,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
      });
      s.setData([
        { time: zone.time0, value: pTop },
        { time: zone.time1, value: pTop },
      ]);
      baselineSeries.push(s);
    } catch {
      /* skip */
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
