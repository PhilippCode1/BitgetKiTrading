/**
 * Gemeinsame Chart-„Intelligence“-Schicht: Welche Overlay-Arten eine Fläche darf,
 * einheitlicher Aufbau der Strategie-Preislinien aus Gateway-Signalen,
 * Re-Export der KI-Annotation-Sanitizer (schema chart_annotations_v1).
 *
 * Keine automatische Aktivierung: Surfaces nutzen {@link CHART_SURFACE_ALLOWLIST};
 * Eltern-Komponenten setzen weiterhin explizite Toggles (z. B. Terminal Zeichnungen/News).
 */

import type { LiveSignal } from "@/lib/types";
import {
  buildStrategyOverlayModel,
  resolveStrategyReferencePrice,
  type StrategyOverlayModel,
} from "@/lib/chart/strategy-overlay-model";
import {
  buildStrategyOverlayChartLines,
  formatChartPriceDe,
  type StrategyOverlayChartLine,
} from "@/lib/chart/strategy-overlay-i18n";

export type ChartSurfaceId = "console_market" | "signal_detail" | "terminal";

/** Welche Overlay-Klassen technisch zulässig sind (Guardrails, keine UX-Toggles). */
export type ChartOverlayAllowlist = Readonly<{
  /** Horizontale Levels aus Live-Signal + Referenzpreis (Gateway-Felder). */
  strategyPriceLevels: boolean;
  /** Geometrie/Marker aus Live-LLM-Antwort (strategy_signal_explain.chart_annotations), gesäubert. */
  llmChartGeometry: boolean;
  /** Struktur-Zeichnungen (Trendlinien) aus app.drawings — nur Terminal-Pipeline. */
  structuralDrawings: boolean;
  /** News-Marker auf der Kerzenserie — nur Terminal-Pipeline. */
  newsMarkers: boolean;
  /**
   * Daten-Lineage als Panel neben dem Chart (nicht Canvas) — Steuerung in LiveTerminalClient;
   * hier nur dokumentiert für die Matrix.
   */
  lineagePanelAdjacent: boolean;
}>;

export const CHART_SURFACE_ALLOWLIST: Record<
  ChartSurfaceId,
  ChartOverlayAllowlist
> = {
  /** Konsole: Signale-Liste, Ops, Health, Live-Broker, Marktuniversum — kein LLM-Canvas ohne Signaldetail. */
  console_market: {
    strategyPriceLevels: true,
    llmChartGeometry: false,
    structuralDrawings: false,
    newsMarkers: false,
    lineagePanelAdjacent: false,
  },
  /** Signaldetail: Strategie-Levels + optional LLM-Overlays nach expliziter Anfrage (Context-Provider). */
  signal_detail: {
    strategyPriceLevels: true,
    llmChartGeometry: true,
    structuralDrawings: false,
    newsMarkers: false,
    lineagePanelAdjacent: false,
  },
  /** Live-Terminal: Strategie optional, Struktur + News; Lineage als separates Panel. */
  terminal: {
    strategyPriceLevels: true,
    llmChartGeometry: false,
    structuralDrawings: true,
    newsMarkers: true,
    lineagePanelAdjacent: true,
  },
};

export type ChartIntelligenceTranslator = (
  key: string,
  params?: Record<string, string | number>,
) => string;

export function resolveEffectiveLlmChartIntegration(
  allow: ChartOverlayAllowlist,
  parentRequestsLlm: boolean,
): boolean {
  return allow.llmChartGeometry && parentRequestsLlm;
}

export function resolveEffectiveStrategyPriceLevels(
  allow: ChartOverlayAllowlist,
): boolean {
  return allow.strategyPriceLevels;
}

export function buildStrategyMarkerOverlayBundle(input: {
  signal: LiveSignal | null;
  markPrice: number | null | undefined;
  tickerLast: number | null | undefined;
  lastCandleClose: number | null | undefined;
  t: ChartIntelligenceTranslator;
  formatPrice?: (n: number) => string;
}): Readonly<{
  overlayModel: StrategyOverlayModel;
  chartLines: StrategyOverlayChartLine[];
  reference: ReturnType<typeof resolveStrategyReferencePrice>;
}> {
  const reference = resolveStrategyReferencePrice({
    markPrice: input.markPrice,
    tickerLast: input.tickerLast,
    lastCandleClose: input.lastCandleClose,
  });
  const overlayModel = buildStrategyOverlayModel({
    signal: input.signal,
    reference,
  });
  const formatPrice = input.formatPrice ?? formatChartPriceDe;
  const chartLines = buildStrategyOverlayChartLines(
    overlayModel,
    input.signal,
    input.t,
    formatPrice,
  );
  return { overlayModel, chartLines, reference };
}

export {
  candleStatsFromBars,
  sanitizeLlmChartAnnotationsDetailed,
  sanitizeLlmChartAnnotations,
  type SanitizedLlmChartAnnotations,
  type LlmChartAnnotationSanitizeMeta,
  type SanitizeLlmChartAnnotationsDetailedResult,
} from "@/lib/chart/llm-chart-annotations";
