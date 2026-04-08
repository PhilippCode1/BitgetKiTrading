"use client";

import { useEffect, useMemo, useRef } from "react";
import {
  createChart,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";

import {
  ProductChartFrame,
  type ProductChartOverlay,
} from "@/components/chart/ProductChartFrame";
import {
  buildProductChartOptions,
  PRODUCT_CHART_COLORS,
} from "@/lib/chart/product-chart-theme";

export type ProductLinePoint = Readonly<{
  time_s: number;
  value: number;
}>;

type Props = Readonly<{
  series: readonly ProductLinePoint[];
  loading?: boolean;
  errorMessage?: string | null;
  emptyMessage?: string | null;
  className?: string;
  height?: number;
  lineColor?: string;
  fitContentOnData?: boolean;
  ariaLabel?: string;
}>;

function resolveOverlay(
  errorMessage: string | null | undefined,
  loading: boolean,
  pointCount: number,
): ProductChartOverlay {
  if (errorMessage) return "error";
  if (loading && pointCount === 0) return "loading";
  if (!loading && pointCount === 0) return "empty";
  return "none";
}

/** Kompakte Zeitreihe (z. B. Equity-Kurve) mit gleichem Rahmen wie Kerzen-Chart. */
export function ProductLineChart({
  series,
  loading = false,
  errorMessage,
  emptyMessage,
  className,
  height = 200,
  lineColor = PRODUCT_CHART_COLORS.lineAccent,
  fitContentOnData = true,
  ariaLabel,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof createChart> | null>(null);
  const lineRef = useRef<ISeriesApi<"Line"> | null>(null);

  const overlay = useMemo(
    () => resolveOverlay(errorMessage, loading, series.length),
    [errorMessage, loading, series.length],
  );

  const mountChart = !errorMessage;

  useEffect(() => {
    if (!mountChart) {
      chartRef.current = null;
      lineRef.current = null;
      return;
    }
    const el = containerRef.current;
    if (!el) return;

    const chart = createChart(el, {
      ...buildProductChartOptions({
        rightPriceScale: { scaleMargins: { top: 0.12, bottom: 0.08 } },
      }),
      width: el.clientWidth,
      height: el.clientHeight || height,
    });
    chartRef.current = chart;
    const line = chart.addLineSeries({
      color: lineColor,
      lineWidth: 2,
      priceLineVisible: false,
    });
    lineRef.current = line;

    const ro = new ResizeObserver(() => {
      if (!containerRef.current || !chartRef.current) return;
      const box = containerRef.current;
      chartRef.current.applyOptions({
        width: box.clientWidth,
        height: Math.max(box.clientHeight, 120),
      });
    });
    ro.observe(el);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      lineRef.current = null;
    };
  }, [mountChart, height, lineColor]);

  useEffect(() => {
    const line = lineRef.current;
    if (!line) return;
    const data = series.map((p) => ({
      time: p.time_s as UTCTimestamp,
      value: p.value,
    }));
    line.setData(data);
    if (fitContentOnData && data.length > 0) {
      chartRef.current?.timeScale().fitContent();
    }
  }, [series, fitContentOnData]);

  const frameMessage =
    overlay === "error"
      ? errorMessage
      : overlay === "empty"
        ? (emptyMessage ?? null)
        : null;

  return (
    <ProductChartFrame
      overlay={overlay}
      message={frameMessage}
      className={`product-chart-frame--line ${className ?? ""}`.trim()}
      minHeight={height}
      ariaLabel={ariaLabel}
    >
      <div
        ref={containerRef}
        className="product-chart-frame__plot"
        style={{ width: "100%", height: `${height}px` }}
      />
    </ProductChartFrame>
  );
}
