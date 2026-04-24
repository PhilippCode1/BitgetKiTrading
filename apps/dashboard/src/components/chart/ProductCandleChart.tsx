"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
} from "lightweight-charts";
import type {
  CandlestickData,
  HistogramData,
  Time,
} from "lightweight-charts";

import {
  ProductChartFrame,
  type ProductChartOverlay,
} from "@/components/chart/ProductChartFrame";
import {
  applyLlmChartLayer,
  clearLlmChartLayer,
  type LlmChartBaselineHandle,
  type LlmChartPriceLineHandle,
} from "@/components/live/overlays/applyLlmChartLayer";
import {
  applyStrategyOverlayPriceLines,
  clearStrategyOverlayPriceLines,
  type StrategyOverlayPriceLineHandle,
} from "@/components/live/overlays/applyStrategyOverlayPriceLines";
import type { LlmFilledPriceZone } from "@/lib/chart/llm-chart-annotations";
import {
  buildLlmZonePopoverText,
  candleStatsFromBars,
  chartTimeToUnixSeconds,
  sanitizeLlmChartAnnotations,
} from "@/lib/chart/llm-chart-annotations";
import {
  mapProductCandlesForLightweight,
  type ProductCandleBar,
} from "@/lib/chart/map-candles";
import {
  type PayloadCandleClose,
  parsePayloadCandleClose,
  TICKER_LABEL_THROTTLE_MS,
} from "@/lib/chart/payload-candle-close";
import {
  buildProductChartOptions,
  PRODUCT_CHART_COLORS,
} from "@/lib/chart/product-chart-theme";
import type { StrategyOverlayLayerId } from "@/lib/chart/strategy-overlay-model";

export type ProductCandleChartHandle = {
  /**
   * Kerze direkt in die Series (lightweight-charts) schreiben — ohne Parent-State.
   * Akzeptiert Schema payload_candle_close; alternative Aliase per parsePayloadCandleClose.
   */
  applyCandleClose: (payload: PayloadCandleClose | unknown) => void;
};

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
  /** Letzter Schlusskurs als Pill (max. alle {@link TICKER_LABEL_THROTTLE_MS} ms) */
  showThrottledLastClosePill?: boolean;
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
  /** KI-Begruendung (z. B. strategy_explanation_de) — Sanitize-Rollen + Popover-Text. */
  llmChartRationaleDe?: string | null;
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
 * Imperative Live-Updates: ref.applyCandleClose — ohne vollstaendige React-Re-Render pro Tick.
 */
export const ProductCandleChart = forwardRef<
  ProductCandleChartHandle,
  Props
>(function ProductCandleChart(
  {
    candles,
    showVolume = true,
    showThrottledLastClosePill = false,
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
    llmChartRationaleDe = null,
  },
  ref,
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const strategyOverlayHandlesRef = useRef<StrategyOverlayPriceLineHandle[]>(
    [],
  );
  const llmPriceHandlesRef = useRef<LlmChartPriceLineHandle[]>([]);
  const llmLineSeriesRef = useRef<ISeriesApi<"Line">[]>([]);
  const llmBaselineSeriesRef = useRef<LlmChartBaselineHandle[]>([]);
  const llmHitZonesRef = useRef<
    ReadonlyArray<{ zone: LlmFilledPriceZone; text: string }>
  >([]);
  const [llmZonePopover, setLlmZonePopover] = useState<{
    x: number;
    y: number;
    text: string;
  } | null>(null);
  const strategyOverlayPropRef = useRef(strategyPriceOverlay);
  strategyOverlayPropRef.current = strategyPriceOverlay;
  const crosshairHintRef = useRef(onStrategyCrosshairHint);
  crosshairHintRef.current = onStrategyCrosshairHint;
  const onReadyRef = useRef(onReady);
  onReadyRef.current = onReady;

  /** Fuer schnelle Prefix-Vergleiche: letzte bekannte Candles-Prop-Referenzen. */
  const lastCandlesPropsRef = useRef<readonly ProductCandleBar[] | null>(null);
  const showVolumeRef = useRef(showVolume);
  showVolumeRef.current = showVolume;

  const [throttledLabelClose, setThrottledLabelClose] = useState<
    number | null
  >(null);
  const lastLabelFlushAtRef = useRef(0);
  const labelTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const labelPendingRef = useRef<number | null>(null);

  const nowMs = () =>
    globalThis.performance?.now?.() ?? Date.now();

  const scheduleThrottledLabel = useCallback(
    (close: number) => {
      if (!showThrottledLastClosePill) {
        return;
      }
      labelPendingRef.current = close;
      if (labelTimerRef.current != null) {
        return;
      }
      const t = nowMs();
      if (
        lastLabelFlushAtRef.current === 0 ||
        t - lastLabelFlushAtRef.current >= TICKER_LABEL_THROTTLE_MS
      ) {
        if (labelPendingRef.current != null) {
          setThrottledLabelClose(labelPendingRef.current);
        }
        lastLabelFlushAtRef.current = t;
        return;
      }
      labelTimerRef.current = setTimeout(() => {
        labelTimerRef.current = null;
        if (labelPendingRef.current != null) {
          setThrottledLabelClose(labelPendingRef.current);
        }
        lastLabelFlushAtRef.current = nowMs();
      }, TICKER_LABEL_THROTTLE_MS - (t - lastLabelFlushAtRef.current));
    },
    [showThrottledLastClosePill],
  );

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

  const applyPayloadToChart = useCallback(
    (p: PayloadCandleClose) => {
      const series = candleSeriesRef.current;
      if (!series) {
        return;
      }
      const tSec = Math.trunc(p.start_ts_ms / 1000) as Time;
      const cdl: CandlestickData = {
        time: tSec,
        open: p.open,
        high: p.high,
        low: p.low,
        close: p.close,
      };
      series.update(cdl);
      if (showVolumeRef.current) {
        const v = volumeSeriesRef.current;
        if (v) {
          const vol = p.usdt_vol ?? p.quote_vol ?? 0;
          const up = p.close >= p.open;
          const hist: HistogramData = {
            time: tSec,
            value: vol,
            color: up
              ? PRODUCT_CHART_COLORS.volumeUp
              : PRODUCT_CHART_COLORS.volumeDown,
          };
          v.update(hist);
        }
      }
      scheduleThrottledLabel(p.close);
    },
    [scheduleThrottledLabel],
  );

  useImperativeHandle(
    ref,
    () => ({
      applyCandleClose: (raw: unknown) => {
        const p = parsePayloadCandleClose(raw);
        if (p) {
          applyPayloadToChart(p);
        }
      },
    }),
    [applyPayloadToChart],
  );

  useEffect(() => {
    if (!mountChart) {
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
      return;
    }
    const el = containerRef.current;
    if (!el) {
      return;
    }

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
      if (!containerRef.current || !chartRef.current) {
        return;
      }
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
        llmBaselineSeriesRef.current,
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
    if (!series || !chart) {
      return;
    }
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
        if (live.visible[line.id] === false) {
          continue;
        }
        const cy = series.priceToCoordinate(line.price);
        if (cy == null) {
          continue;
        }
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
    if (!series) {
      return;
    }

    const m = mapped;
    const prev = lastCandlesPropsRef.current;
    if (m.candles.length === 0) {
      series.setData([]);
      if (vol && showVolume) {
        vol.setData([]);
      }
      lastCandlesPropsRef.current = candles;
      if (candles.length === 0) {
        if (labelTimerRef.current) {
          clearTimeout(labelTimerRef.current);
          labelTimerRef.current = null;
        }
        setThrottledLabelClose(null);
        lastLabelFlushAtRef.current = 0;
        labelPendingRef.current = null;
      }
      return;
    }

    if (
      prev != null &&
      prev.length > 0 &&
      candles.length > 0 &&
      candles.length === prev.length
    ) {
      let samePrefix = true;
      for (let i = 0; i < candles.length - 1; i++) {
        if (candles[i] !== prev[i]) {
          samePrefix = false;
          break;
        }
      }
      if (samePrefix && m.candles.length > 0) {
        const lastC = m.candles[m.candles.length - 1]!;
        series.update(lastC);
        if (vol && showVolume && m.volume.length) {
          vol.update(m.volume[m.volume.length - 1]!);
        }
        lastCandlesPropsRef.current = candles;
        scheduleThrottledLabel(lastC.close);
        if (fitContentOnData) {
          chartRef.current?.timeScale().fitContent();
        }
        return;
      }
    }

    series.setData(m.candles);
    if (vol && showVolume) {
      vol.setData(m.volume);
    }
    lastCandlesPropsRef.current = candles;
    const end = mapped.candles[mapped.candles.length - 1];
    if (end) {
      scheduleThrottledLabel(end.close);
    }
    if (fitContentOnData && m.candles.length > 0) {
      chartRef.current?.timeScale().fitContent();
    }
  }, [mapped, candles, showVolume, fitContentOnData, scheduleThrottledLabel]);

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
        llmBaselineSeriesRef.current,
      );
      llmHitZonesRef.current = [];
      return;
    }
    if (!llmChartLayerEnabled) {
      clearLlmChartLayer(
        chart,
        series,
        llmPriceHandlesRef.current,
        llmLineSeriesRef.current,
        llmBaselineSeriesRef.current,
      );
      llmHitZonesRef.current = [];
      return;
    }
    const stats = candleStatsFromBars(candles);
    const model = sanitizeLlmChartAnnotations(
      llmChartAnnotationsRaw,
      stats,
      { rationaleHint: llmChartRationaleDe?.trim() || undefined },
    );
    llmHitZonesRef.current = model.filledZones.map((z) => ({
      zone: z,
      text: buildLlmZonePopoverText(z, llmChartRationaleDe),
    }));
    applyLlmChartLayer(
      chart,
      series,
      model,
      llmPriceHandlesRef.current,
      llmLineSeriesRef.current,
      llmBaselineSeriesRef.current,
    );
    return () => {
      clearLlmChartLayer(
        chart,
        series,
        llmPriceHandlesRef.current,
        llmLineSeriesRef.current,
        llmBaselineSeriesRef.current,
      );
    };
  }, [
    llmChartIntegration,
    llmChartLayerEnabled,
    llmChartAnnotationsRaw,
    llmChartRationaleDe,
    candles.length,
    candles,
  ]);

  useEffect(() => {
    const chart = chartRef.current;
    const series = candleSeriesRef.current;
    if (!chart || !series) {
      return;
    }
    if (!llmChartIntegration || !llmChartLayerEnabled) {
      setLlmZonePopover(null);
      return;
    }

    const onMove = (param: {
      point?: { x: number; y: number } | null;
      time?: Time;
    }) => {
      if (!param.point) {
        setLlmZonePopover(null);
        return;
      }
      if (param.time === undefined) {
        setLlmZonePopover(null);
        return;
      }
      const tU = chartTimeToUnixSeconds(param.time);
      if (tU == null) {
        setLlmZonePopover(null);
        return;
      }
      const price = series.coordinateToPrice(param.point.y);
      if (price == null) {
        setLlmZonePopover(null);
        return;
      }
      for (let i = llmHitZonesRef.current.length - 1; i >= 0; i -= 1) {
        const row = llmHitZonesRef.current[i]!;
        const z = row.zone;
        const t0u = chartTimeToUnixSeconds(z.time0);
        const t1u = chartTimeToUnixSeconds(z.time1);
        if (t0u == null || t1u == null) {
          continue;
        }
        const tMin = Math.min(t0u, t1u);
        const tMax = Math.max(t0u, t1u);
        if (tU < tMin || tU > tMax) {
          continue;
        }
        const pHi = Math.max(z.priceHigh, z.priceLow);
        const pLo = Math.min(z.priceHigh, z.priceLow);
        if (price < pLo || price > pHi) {
          continue;
        }
        setLlmZonePopover({
          x: param.point.x,
          y: param.point.y,
          text: row.text,
        });
        return;
      }
      setLlmZonePopover(null);
    };

    chart.subscribeCrosshairMove(onMove);
    return () => {
      chart.unsubscribeCrosshairMove(onMove);
      setLlmZonePopover(null);
    };
  }, [llmChartIntegration, llmChartLayerEnabled, llmChartAnnotationsRaw, candles]);

  const frameMessage =
    overlay === "error"
      ? errorMessage
      : overlay === "empty"
        ? (emptyMessage ?? null)
        : null;

  const showPill =
    showThrottledLastClosePill && throttledLabelClose != null && !errorMessage;

  return (
    <ProductChartFrame
      overlay={overlay}
      message={frameMessage}
      className={`product-chart-frame--candles ${className ?? ""}`.trim()}
      minHeight={height}
      ariaLabel={ariaLabel}
    >
      <div className="product-chart-frame__plot-wrap">
        {showPill ? (
          <span
            className="product-chart-frame__last-tick"
            title=""
            aria-hidden
          >
            {throttledLabelClose}
          </span>
        ) : null}
        <div
          ref={containerRef}
          className="product-chart-frame__plot"
          style={{ width: "100%", height: `${height}px` }}
        />
        {llmZonePopover ? (
          <div
            className="llm-chart-zone-popover"
            role="tooltip"
            style={{ left: llmZonePopover.x, top: llmZonePopover.y }}
          >
            {llmZonePopover.text}
          </div>
        ) : null}
      </div>
    </ProductChartFrame>
  );
});

ProductCandleChart.displayName = "ProductCandleChart";

export type { PayloadCandleClose } from "@/lib/chart/payload-candle-close";
export { TICKER_LABEL_THROTTLE_MS } from "@/lib/chart/payload-candle-close";
