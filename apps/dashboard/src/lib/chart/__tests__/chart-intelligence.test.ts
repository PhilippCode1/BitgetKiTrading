import {
  CHART_SURFACE_ALLOWLIST,
  buildStrategyMarkerOverlayBundle,
  resolveEffectiveLlmChartIntegration,
  resolveEffectiveStrategyPriceLevels,
} from "@/lib/chart/chart-intelligence";
import type { LiveSignal } from "@/lib/types";

describe("chart-intelligence", () => {
  it("console_market disallow llm geometry even if parent requests", () => {
    const allow = CHART_SURFACE_ALLOWLIST.console_market;
    expect(resolveEffectiveStrategyPriceLevels(allow)).toBe(true);
    expect(resolveEffectiveLlmChartIntegration(allow, true)).toBe(false);
  });

  it("signal_detail allows llm when parent requests", () => {
    const allow = CHART_SURFACE_ALLOWLIST.signal_detail;
    expect(resolveEffectiveLlmChartIntegration(allow, true)).toBe(true);
    expect(resolveEffectiveLlmChartIntegration(allow, false)).toBe(false);
  });

  it("terminal allows structural and news flags", () => {
    const t = CHART_SURFACE_ALLOWLIST.terminal;
    expect(t.structuralDrawings).toBe(true);
    expect(t.newsMarkers).toBe(true);
    expect(t.llmChartGeometry).toBe(false);
    expect(t.lineagePanelAdjacent).toBe(true);
  });

  it("buildStrategyMarkerOverlayBundle derives reference from mark price", () => {
    const signal = {
      direction: "long",
      stop_distance_pct: 0.01,
    } as LiveSignal;
    const t = (k: string) => k;
    const b = buildStrategyMarkerOverlayBundle({
      signal,
      markPrice: 100,
      tickerLast: 99,
      lastCandleClose: 98,
      t,
    });
    expect(b.reference?.source).toBe("mark_price");
    expect(b.chartLines.some((l) => l.id === "reference")).toBe(true);
    expect(b.chartLines.some((l) => l.id === "stop_loss")).toBe(true);
  });
});
