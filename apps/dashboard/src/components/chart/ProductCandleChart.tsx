"use client";

import { useEffect, useMemo, useRef } from "react";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
} from "lightweight-charts";

import {
  ProductChartFrame,
  type ProductChartOverlay,
} from "@/components/chart/ProductChartFrame";
import {
  applyLlmChartLayer,
  clearLlmChartLayer,
  type LlmChartPriceLineHandle,
} from "@/components/live/overlays/applyLlmChartLayer";
import {
  applyStrategyOverlayPriceLines,
  clearStrategyOverlayPriceLines,
  type StrategyOverlayPriceLineHandle,
} from "@/components/live/overlays/applyStrategyOverlayPriceLines";
import {
  candleStatsFromBars,
  sanitizeLlmChartAnnotations,
} from "@/lib/chart/llm-chart-annotations";
import {
  mapProductCandlesForLightweight,
  type ProductCandleBar,
} from "@/lib/chart/map-candles";
import {
  buildProductChartOptions,
  PRODUCT_CHART_COLORS,
} from "@/lib/chart/product-chart-theme";
import type { StrategyOverlayLayerId } from "@/lib/chart/strategy-overlay-model";

export type ProductCandleChartReadyContext = Readonly<{
  chart: IChartApi;
  candleSeries: ISeriesApi<"Candlestick">;
  volumeSeries: ISeriesApi<"Histogram"> | null;
}>;

export type ProductStrategyOverlayLine = Readonly<{
  id: StrategyOverlayLayerId;
  price: number;
  axisLabel: string;
  hint: string;
}>;

export type ProductStrategyPriceOverlayProps = Readonly<{
  lines: readonly ProductStrategyOverlayLine[];
  visible: Readonly<Partial<Record<StrategyOverlayLayerId, boolean>>>;
  enabled: boolean;
}>;

type Props = Readonly<{
  candles: readonly ProductCandleBar[];
  showVolume?: boolean;
  loading?: boolean;
  errorMessage?: string | null;
  emptyMessage?: string | null;
  /** Wenn true: kein Leer-Overlay — Elternkomponente zeigt Hinweis (z. B. Live-Terminal). */
  hideEmptyOverlay?: boolean;
  className?: string;
  /** Chart-Hoehe in px */
  height?: number;
  fitContentOnData?: boolean;
  onReady?: (ctx: ProductCandleChartReadyContext) => void;
  ariaLabel?: string;
  /** Horizontale Strategie-Levels aus Gateway-Signal (Preise nur aus Backend-Feldern abgeleitet). */
  strategyPriceOverlay?: ProductStrategyPriceOverlayProps | null;
  /** Nahe-Linie-Hinweis beim Crosshair (Canvas hat keine nativen Tooltips auf Price-Lines). */
  onStrategyCrosshairHint?: (hint: string | null) => void;
  /**
   * Optional: KI-Chart-Annotationen (roh, schema chart_annotations_v1); Sanitize via
   * sanitizeLlmChartAnnotations. Surface-Policy: lib/chart/chart-intelligence (CHART_SURFACE_ALLOWLIST).
   * Nur aktiv wenn llmChartIntegration true.
   */
  llmChartAnnotationsRaw?: unknown;
  llmChartLayerEnabled?: boolean;
  /** Wenn false (Default), werden keine KI-Overlays gesetzt oder Marker geleert. */
  llmChartIntegration?: boolean;
}>;

function resolveOverlay(
  errorMessage: string | null | undefined,
  loading: boolean,
  candleCount: number,
  hideEmptyOverlay: boolean,
): ProductChartOverlay {
  if (errorMessage) return "error";
  if (loading && candleCount === 0) return "loading";
  if (!hideEmptyOverlay && !loading && candleCount === 0) return "empty";
  return "none";
}

/**
 * Kerzen + optionales Volumen (Histogramm), Crosshair/Zeitachse, Theme wie Konsole.
 * Ueber {@link onReady} koennen Overlays (News, Linien) andocken.
 */
export function ProductCandleChart({
  candles,
  showVolume = true,
  loading = false,
  errorMessage,
  emptyMessage,
  hideEmptyOverlay = false,
  className,
  height = 420,
  /** Bei true: nach jedem Daten-Update fitContent (fuer statische Seiten; Live-Stream eher false). */
  fitContentOnData = false,
  onReady,
  ariaLabel,
  strategyPriceOverlay = null,
  onStrategyCrosshairHint,
  llmChartAnnotationsRaw = null,
  llmChartLayerEnabled = true,
  llmChartIntegration = false,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const strategyOverlayHandlesRef = useRef<StrategyOverlayPriceLineHandle[]>(
    [],
  );
  const llmPriceHandlesRef = useRef<LlmChartPriceLineHandle[]>([]);
  const llmLineSeriesRef = useRef<ISeriesApi<"Line">[]>([]);
  const strategyOverlayPropRef = useRef(strategyPriceOverlay);
  strategyOverlayPropRef.current = strategyPriceOverlay;
  const crosshairHintRef = useRef(onStrategyCrosshairHint);
  crosshairHintRef.current = onStrategyCrosshairHint;
  const onReadyRef = useRef(onReady);
  onReadyRef.current = onReady;

  const overlay = useMemo(
    () =>
      resolveOverlay(errorMessage, loading, candles.length, hideEmptyOverlay),
    [errorMessage, loading, candles.length, hideEmptyOverlay],
  );

  const mapped = useMemo(
    () => mapProductCandlesForLightweight(candles),
    [candles],
  );

  const mountChart = !errorMessage;

  useEffect(() => {
    if (!mountChart) {
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
      return;
    }
    const el = containerRef.current;
    if (!el) return;

    const chart = createChart(el, {
      ...buildProductChartOptions(),
      width: el.clientWidth,
      height: el.clientHeight || height,
    });
    chartRef.current = chart;

    const candleSeries = chart.addCandlestickSeries({
      upColor: PRODUCT_CHART_COLORS.up,
      downColor: PRODUCT_CHART_COLORS.down,
      borderVisible: false,
      wickUpColor: PRODUCT_CHART_COLORS.up,
      wickDownColor: PRODUCT_CHART_COLORS.down,
    });
    candleSeries.priceScale().applyOptions({
      scaleMargins: showVolume
        ? { top: 0.08, bottom: 0.22 }
        : { top: 0.06, bottom: 0.06 },
    });
    candleSeriesRef.current = candleSeries;

    let volumeSeries: ISeriesApi<"Histogram"> | null = null;
    if (showVolume) {
      volumeSeries = chart.addHistogramSeries({
        color: PRODUCT_CHART_COLORS.volumeUp,
        priceFormat: { type: "volume" },
        priceScaleId: "",
      });
      volumeSeries
        .priceScale()
        .applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
      volumeSeriesRef.current = volumeSeries;
    } else {
      volumeSeriesRef.current = null;
    }

    onReadyRef.current?.({ chart, candleSeries, volumeSeries });

    const ro = new ResizeObserver(() => {
      if (!containerRef.current || !chartRef.current) return;
      const box = containerRef.current;
      chartRef.current.applyOptions({
        width: box.clientWidth,
        height: Math.max(box.clientHeight, 200),
      });
    });
    ro.observe(el);

    return () => {
      ro.disconnect();
      clearStrategyOverlayPriceLines(
        candleSeriesRef.current,
        strategyOverlayHandlesRef.current,
      );
      clearLlmChartLayer(
        chartRef.current,
        candleSeriesRef.current,
        llmPriceHandlesRef.current,
        llmLineSeriesRef.current,
      );
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
    };
  }, [mountChart, showVolume, height]);

  useEffect(() => {
    const series = candleSeriesRef.current;
    const chart = chartRef.current;
    if (!series || !chart) return;

    const o = strategyOverlayPropRef.current;
    const hintCb = crosshairHintRef.current;

    const clearHint = () => hintCb?.(null);

    if (!o?.enabled || o.lines.length === 0) {
      clearStrategyOverlayPriceLines(series, strategyOverlayHandlesRef.current);
      clearHint();
      return;
    }

    applyStrategyOverlayPriceLines(
      series,
      o.lines.map((l) => ({
        id: l.id,
        price: l.price,
        axisLabel: l.axisLabel,
      })),
      o.visible,
      strategyOverlayHandlesRef.current,
    );

    const onMove = (param: { point?: { y?: number } | null }) => {
      const live = strategyOverlayPropRef.current;
      if (!live?.enabled || live.lines.length === 0) {
        hintCb?.(null);
        return;
      }
      if (!param.point || param.point.y === undefined) {
        hintCb?.(null);
        return;
      }
      const y = param.point.y;
      let best: { dist: number; hint: string } | null = null;
      for (const line of live.lines) {
        if (live.visible[line.id] === false) continue;
        const cy = series.priceToCoordinate(line.price);
        if (cy == null) continue;
        const dist = Math.abs(cy - y);
        if (dist < 14 && (!best || dist < best.dist)) {
          best = { dist, hint: line.hint };
        }
      }
      hintCb?.(best?.hint ?? null);
    };

    chart.subscribeCrosshairMove(onMove);

    return () => {
      chart.unsubscribeCrosshairMove(onMove);
      clearStrategyOverlayPriceLines(series, strategyOverlayHandlesRef.current);
      clearHint();
    };
  }, [
    strategyPriceOverlay?.enabled,
    strategyPriceOverlay?.lines,
    strategyPriceOverlay?.visible,
  ]);

  useEffect(() => {
    const series = candleSeriesRef.current;
    const vol = volumeSeriesRef.current;
    if (!series) return;
    series.setData(mapped.candles);
    if (vol && showVolume) {
      vol.setData(mapped.volume);
    }
    if (fitContentOnData && mapped.candles.length > 0) {
      chartRef.current?.timeScale().fitContent();
    }
  }, [mapped, showVolume, fitContentOnData]);

  useEffect(() => {
    const chart = chartRef.current;
    const series = candleSeriesRef.current;
    if (!chart || !series) {
      return;
    }
    if (!llmChartIntegration) {
      clearLlmChartLayer(
        chart,
        series,
        llmPriceHandlesRef.current,
        llmLineSeriesRef.current,
      );
      return;
    }
    if (!llmChartLayerEnabled) {
      clearLlmChartLayer(
        chart,
        series,
        llmPriceHandlesRef.current,
        llmLineSeriesRef.current,
      );
      return;
    }
    const stats = candleStatsFromBars(candles);
    const model = sanitizeLlmChartAnnotations(llmChartAnnotationsRaw, stats);
    applyLlmChartLayer(
      chart,
      series,
      model,
      llmPriceHandlesRef.current,
      llmLineSeriesRef.current,
    );
    return () => {
      clearLlmChartLayer(
        chart,
        series,
        llmPriceHandlesRef.current,
        llmLineSeriesRef.current,
      );
    };
  }, [
    llmChartIntegration,
    llmChartLayerEnabled,
    llmChartAnnotationsRaw,
    candles.length,
    candles,
  ]);

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
      className={`product-chart-frame--candles ${className ?? ""}`.trim()}
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
