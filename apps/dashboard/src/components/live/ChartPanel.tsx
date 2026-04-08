"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ISeriesApi, Time } from "lightweight-charts";

import { StrategyOverlayLegendBar } from "@/components/chart/StrategyOverlayLegendBar";
import {
  ProductCandleChart,
  type ProductCandleChartReadyContext,
  type ProductStrategyPriceOverlayProps,
} from "@/components/chart/ProductCandleChart";
import { applyNewsMarkers } from "@/components/live/overlays/applyMarkers";
import {
  applyPriceLines,
  clearPriceLines,
  type PriceLineHandle,
} from "@/components/live/overlays/applyPriceLines";
import { useI18n } from "@/components/i18n/I18nProvider";
import {
  CHART_SURFACE_ALLOWLIST,
  buildStrategyMarkerOverlayBundle,
} from "@/lib/chart/chart-intelligence";
import {
  defaultStrategyLayerVisibility,
  type StrategyOverlayLayerId,
} from "@/lib/chart/strategy-overlay-model";
import type {
  LiveCandle,
  LiveDrawing,
  LiveNewsItem,
  LiveSignal,
} from "@/lib/types";

const TERMINAL_OVERLAY_ALLOW = CHART_SURFACE_ALLOWLIST.terminal;

type Props = {
  candles: LiveCandle[];
  drawings: LiveDrawing[];
  news: LiveNewsItem[];
  showDrawings: boolean;
  showNewsMarkers: boolean;
  strategyContext?: {
    signal: LiveSignal | null;
    markPrice: number | null;
    tickerLast: number | null;
  } | null;
};

/**
 * Live-Terminal: Kerzen inkl. Volumen ueber {@link ProductCandleChart}, Zeichnungen/News als Overlays.
 * Overlay-Faehigkeiten folgen {@link CHART_SURFACE_ALLOWLIST.terminal} plus Nutzer-Toggles.
 */
export function ChartPanel({
  candles,
  drawings,
  news,
  showDrawings,
  showNewsMarkers,
  strategyContext = null,
}: Props) {
  const { t } = useI18n();
  const [chartCtx, setChartCtx] =
    useState<ProductCandleChartReadyContext | null>(null);
  const priceLinesRef = useRef<PriceLineHandle[]>([]);
  const lineSeriesRef = useRef<ISeriesApi<"Line">[]>([]);
  const [strategyMaster, setStrategyMaster] = useState(true);
  const [layerVisible, setLayerVisible] = useState(
    defaultStrategyLayerVisibility,
  );
  const [crosshairHint, setCrosshairHint] = useState<string | null>(null);

  const onReady = useCallback((ctx: ProductCandleChartReadyContext) => {
    setChartCtx(ctx);
  }, []);

  const lastClose = candles.length ? candles[candles.length - 1]!.close : null;

  const strategyBundle = useMemo(() => {
    if (!strategyContext || !TERMINAL_OVERLAY_ALLOW.strategyPriceLevels) {
      return null;
    }
    return buildStrategyMarkerOverlayBundle({
      signal: strategyContext.signal,
      markPrice: strategyContext.markPrice,
      tickerLast: strategyContext.tickerLast,
      lastCandleClose: lastClose,
      t,
    });
  }, [strategyContext, lastClose, t]);

  const overlayModel = strategyBundle?.overlayModel ?? null;

  const chartLines = strategyBundle?.chartLines ?? [];

  const strategyPriceOverlay: ProductStrategyPriceOverlayProps | null =
    useMemo(() => {
      if (!strategyContext || chartLines.length === 0) return null;
      return {
        lines: chartLines,
        visible: layerVisible,
        enabled: strategyMaster,
      };
    }, [strategyContext, chartLines, layerVisible, strategyMaster]);

  const onLayerChange = useCallback(
    (id: StrategyOverlayLayerId, v: boolean) => {
      setLayerVisible((prev) => ({ ...prev, [id]: v }));
    },
    [],
  );

  const drawingsAllowed =
    TERMINAL_OVERLAY_ALLOW.structuralDrawings && showDrawings;
  const newsAllowed = TERMINAL_OVERLAY_ALLOW.newsMarkers && showNewsMarkers;

  useEffect(() => {
    const series = chartCtx?.candleSeries;
    const chart = chartCtx?.chart;
    if (!series || !chart) return;
    clearPriceLines(series, priceLinesRef.current);
    for (const ls of lineSeriesRef.current) {
      try {
        chart.removeSeries(ls);
      } catch {
        /* ignore */
      }
    }
    lineSeriesRef.current = [];
    if (drawingsAllowed) {
      applyPriceLines(series, drawings, priceLinesRef.current);
      for (const d of drawings) {
        if (!d.trendline) continue;
        const ls = chart.addLineSeries({
          color: d.trendline.color,
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: true,
        });
        ls.setData([
          {
            time: Math.floor(d.trendline.t0_ms / 1000) as Time,
            value: d.trendline.p0,
          },
          {
            time: Math.floor(d.trendline.t1_ms / 1000) as Time,
            value: d.trendline.p1,
          },
        ]);
        lineSeriesRef.current.push(ls);
      }
    }
  }, [chartCtx, drawings, drawingsAllowed]);

  useEffect(() => {
    const series = chartCtx?.candleSeries;
    if (!series) return;
    applyNewsMarkers(series, news, newsAllowed);
  }, [chartCtx, news, newsAllowed]);

  return (
    <div className="terminal-chart-stack">
      <ProductCandleChart
        candles={candles}
        showVolume
        hideEmptyOverlay
        height={420}
        fitContentOnData={false}
        className="terminal-main-chart"
        onReady={onReady}
        strategyPriceOverlay={strategyPriceOverlay}
        onStrategyCrosshairHint={setCrosshairHint}
        llmChartIntegration={false}
      />
      {strategyContext ? (
        <StrategyOverlayLegendBar
          model={overlayModel}
          masterEnabled={strategyMaster}
          onMasterChange={setStrategyMaster}
          layerVisible={layerVisible}
          onLayerChange={onLayerChange}
        />
      ) : null}
      {crosshairHint ? (
        <p className="muted small strategy-crosshair-hint" role="status">
          {crosshairHint}
        </p>
      ) : null}
    </div>
  );
}
