"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { SurfaceDiagnosticCard } from "@/components/diagnostics/SurfaceDiagnosticCard";
import { DemoDataNoticeBanner } from "@/components/live/DemoDataNoticeBanner";
import { StrategyOverlayLegendBar } from "@/components/chart/StrategyOverlayLegendBar";
import { ProductCandleChart } from "@/components/chart/ProductCandleChart";
import { useI18n } from "@/components/i18n/I18nProvider";
import {
  CHART_SURFACE_ALLOWLIST,
  buildStrategyMarkerOverlayBundle,
  candleStatsFromBars,
  resolveEffectiveLlmChartIntegration,
  resolveEffectiveStrategyPriceLevels,
  sanitizeLlmChartAnnotationsDetailed,
  type ChartSurfaceId,
} from "@/lib/chart/chart-intelligence";
import { fetchLiveState } from "@/lib/api";
import { mergeConsoleChartSearch } from "@/lib/chart-prefs";
import { consolePath } from "@/lib/console-paths";
import {
  defaultStrategyLayerVisibility,
  type StrategyOverlayLayerId,
} from "@/lib/chart/strategy-overlay-model";
import { LiveDataSituationBar } from "@/components/live-data/LiveDataSituationBar";
import type { ExecutionPathViewModel } from "@/lib/execution-path-view-model";
import { buildLiveDataSurfaceModelFromLiveState } from "@/lib/live-data-surface-model";
import { resolveConsoleChartSurfaceDiagnostic } from "@/lib/surface-diagnostic-catalog";
import type {
  LiveCandle,
  LiveMarketFreshness,
  LiveStateResponse,
} from "@/lib/types";

type UrlParams = Record<string, string>;

type Props = Readonly<{
  pathname: string;
  /** Aktuelle Query-Felder (nur definierte Strings) — wird mit Symbol/TF gemerged */
  urlParams: UrlParams;
  chartSymbol: string;
  chartTimeframe: string;
  symbolOptions: readonly string[];
  timeframeOptions?: readonly string[];
  height?: number;
  /** z. B. execution_mode aus Health/Runtime fuer Demo-Badge */
  executionModeLabel?: string | null;
  /** Aus Health oder Live-Broker-Runtime — fuer Live-Datenlage-Streifen */
  executionVm?: ExecutionPathViewModel | null;
  panelTitleKey?: string;
  showTerminalLink?: boolean;
  /** Keine Symbol-Zeile (z. B. Signaldetail — nur ein Instrument) */
  hideSymbolPicker?: boolean;
  /** KI-Chart-Layer (nur Signaldetail-Kontext mit Provider) */
  llmChartIntegration?: boolean;
  llmChartAnnotationsRaw?: unknown | null;
  llmChartLayerEnabled?: boolean;
  onLlmChartLayerEnabledChange?: (enabled: boolean) => void;
  /**
   * Steuert erlaubte Overlay-Klassen ({@link CHART_SURFACE_ALLOWLIST}).
   * Standard Konsole ohne Live-KI-Geometrie; Signaldetail setzt `signal_detail`.
   */
  chartSurfaceId?: ChartSurfaceId;
  /**
   * Wenn die Seite bereits eine {@link LiveDataSituationBar} oberhalb rendert,
   * auf false setzen — vermeidet doppelte Statusstreifen.
   */
  showLiveDataSituationBar?: boolean;
  /**
   * Roh-Badges (execution_mode, freshness.status) neben dem Panel-Titel.
   * Standard aus: Inhalt steht bereits in der Live-Datenlage-Leiste.
   */
  showInlineChartBadges?: boolean;
}>;

function badgeClassForFreshness(status: LiveMarketFreshness["status"]): string {
  switch (status) {
    case "live":
      return "status-pill status-ok";
    case "delayed":
      return "status-pill status-warn";
    case "stale":
    case "dead":
    case "no_candles":
      return "status-pill status-bad";
    default:
      return "status-pill";
  }
}

/**
 * Bitget-Marktchart mit URL-synchroner Symbol-/TF-Navigation und Persistenz der letzten Wahl.
 */
export function ConsoleLiveMarketChartSection({
  pathname,
  urlParams,
  chartSymbol,
  chartTimeframe,
  symbolOptions,
  timeframeOptions = ["1m", "5m", "15m", "1h", "4h"],
  height = 380,
  executionModeLabel,
  executionVm = null,
  panelTitleKey = "ui.chart.panelTitle",
  showTerminalLink = true,
  hideSymbolPicker = false,
  llmChartIntegration = false,
  llmChartAnnotationsRaw = null,
  llmChartLayerEnabled = true,
  onLlmChartLayerEnabledChange,
  chartSurfaceId = "console_market",
  showLiveDataSituationBar = true,
  showInlineChartBadges = false,
}: Props) {
  const { t } = useI18n();
  const overlayAllow = CHART_SURFACE_ALLOWLIST[chartSurfaceId];
  const strategyLevelsOk = resolveEffectiveStrategyPriceLevels(overlayAllow);
  const llmIntegrationEffective = resolveEffectiveLlmChartIntegration(
    overlayAllow,
    llmChartIntegration,
  );
  const [live, setLive] = useState<LiveStateResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchErr, setFetchErr] = useState<string | null>(null);
  const [prefsSaveErr, setPrefsSaveErr] = useState<string | null>(null);

  const tfOpts = useMemo(() => [...timeframeOptions], [timeframeOptions]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setFetchErr(null);
    fetchLiveState({
      symbol: chartSymbol,
      timeframe: chartTimeframe,
      limit: 480,
    })
      .then((r) => {
        if (!cancelled) setLive(r);
      })
      .catch((e) => {
        if (!cancelled)
          setFetchErr(
            e instanceof Error ? e.message : t("errors.fallbackMessage"),
          );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [chartSymbol, chartTimeframe, t]);

  useEffect(() => {
    setPrefsSaveErr(null);
    void fetch("/api/dashboard/chart-prefs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ symbol: chartSymbol, timeframe: chartTimeframe }),
    })
      .then(async (res) => {
        if (!res.ok) {
          const txt = await res.text().catch(() => "");
          setPrefsSaveErr(txt.trim() || `HTTP ${res.status}`);
        }
      })
      .catch((e) => {
        setPrefsSaveErr(
          e instanceof Error ? e.message : t("errors.fallbackMessage"),
        );
      });
  }, [chartSymbol, chartTimeframe, t]);

  const candles: LiveCandle[] = live?.candles ?? [];
  const freshness = live?.market_freshness ?? null;
  const resolvedSym = live?.symbol ?? chartSymbol;
  const resolvedTf = live?.timeframe ?? chartTimeframe;

  const chartSurfaceDiag = useMemo(
    () =>
      resolveConsoleChartSurfaceDiagnostic({
        loading,
        fetchErr,
        candleCount: candles.length,
        symbol: chartSymbol,
        timeframe: chartTimeframe,
        freshness,
      }),
    [loading, fetchErr, candles.length, chartSymbol, chartTimeframe, freshness],
  );

  const lastClose = candles.length ? candles[candles.length - 1]!.close : null;

  const situationModel = useMemo(
    () =>
      buildLiveDataSurfaceModelFromLiveState({
        live,
        executionVm,
        executionModeLabel,
        fetchError: Boolean(fetchErr),
        loading,
        candleCount: candles.length,
        surfaceKind: "market_chart",
      }),
    [
      live,
      executionVm,
      executionModeLabel,
      fetchErr,
      loading,
      candles.length,
    ],
  );

  const strategyBundle = useMemo(() => {
    if (!strategyLevelsOk) {
      return null;
    }
    return buildStrategyMarkerOverlayBundle({
      signal: live?.latest_signal ?? null,
      markPrice: live?.paper_state?.mark_price,
      tickerLast: live?.market_freshness?.ticker?.last_pr,
      lastCandleClose: lastClose,
      t,
    });
  }, [
    strategyLevelsOk,
    live?.latest_signal,
    live?.paper_state?.mark_price,
    live?.market_freshness?.ticker?.last_pr,
    lastClose,
    t,
  ]);

  const overlayModel = strategyBundle?.overlayModel ?? null;

  const [strategyMaster, setStrategyMaster] = useState(true);
  const [layerVisible, setLayerVisible] = useState(
    defaultStrategyLayerVisibility,
  );
  const [crosshairHint, setCrosshairHint] = useState<string | null>(null);

  const chartLines = strategyBundle?.chartLines ?? [];

  const strategyPriceOverlay = useMemo(() => {
    if (chartLines.length === 0) return null;
    return {
      lines: chartLines,
      visible: layerVisible,
      enabled: strategyMaster,
    };
  }, [chartLines, layerVisible, strategyMaster]);

  const llmSanitizeDetail = useMemo(() => {
    if (!llmIntegrationEffective || llmChartAnnotationsRaw == null) {
      return null;
    }
    const stats = candleStatsFromBars(candles);
    return sanitizeLlmChartAnnotationsDetailed(llmChartAnnotationsRaw, stats);
  }, [llmIntegrationEffective, llmChartAnnotationsRaw, candles]);

  const llmNotes = llmSanitizeDetail?.model.notes ?? [];
  const llmMeta = llmSanitizeDetail?.meta ?? null;

  const showLlmChartUi =
    llmIntegrationEffective && llmChartAnnotationsRaw != null;

  const onLayerChange = useCallback(
    (id: StrategyOverlayLayerId, v: boolean) => {
      setLayerVisible((prev) => ({ ...prev, [id]: v }));
    },
    [],
  );

  const hrefTf = (tf: string) =>
    mergeConsoleChartSearch(pathname, urlParams, { timeframe: tf });
  const hrefSym = (sym: string) =>
    mergeConsoleChartSearch(pathname, urlParams, { symbol: sym });

  const terminalHref = `${consolePath("terminal")}?${new URLSearchParams({
    symbol: chartSymbol,
    timeframe: chartTimeframe,
  }).toString()}`;

  const demoLower = (executionModeLabel ?? "").toLowerCase();
  const isPaperLike =
    demoLower.includes("paper") || demoLower.includes("shadow");

  return (
    <div className="panel console-live-market-chart">
      <DemoDataNoticeBanner notice={live?.demo_data_notice} />
      {showLiveDataSituationBar ? (
        <LiveDataSituationBar model={situationModel} />
      ) : null}
      {prefsSaveErr ? (
        <div className="console-chart-prefs-save-err" role="alert">
          <p className="muted small degradation-inline">{t("ui.chart.prefsSaveFailed")}</p>
          <details className="console-fetch-notice__diag small">
            <summary className="console-fetch-notice__diag-sum">
              {t("ui.diagnostic.summary")}
            </summary>
            <pre className="console-fetch-notice__pre">{prefsSaveErr}</pre>
          </details>
        </div>
      ) : null}
      <div className="console-live-market-chart__head">
        <h2>{t(panelTitleKey)}</h2>
        {showInlineChartBadges ? (
          <div className="console-live-market-chart__badges" role="status">
            {executionModeLabel ? (
              <span
                className={`status-pill ${isPaperLike ? "status-warn" : "status-ok"}`}
                title={t("ui.chart.badgeExecutionHint")}
              >
                {t("ui.chart.badgeExecution")}: {executionModeLabel}
              </span>
            ) : null}
            {freshness ? (
              <span
                className={badgeClassForFreshness(freshness.status)}
                title={t("ui.chart.badgeFreshnessHint")}
              >
                {t("ui.chart.badgeMarket")}: {freshness.status}
              </span>
            ) : loading ? (
              <span className="status-pill">{t("ui.chart.badgeChecking")}</span>
            ) : null}
          </div>
        ) : null}
      </div>
      <div className="filter-row console-live-market-chart__tf">
        <span
          className="muted"
          title={t("pages.signals.filters.hintTimeframe")}
        >
          {t("pages.signals.filters.labelTimeframe")}:
        </span>
        {tfOpts.map((tf) => (
          <Link
            key={tf}
            href={hrefTf(tf)}
            className={chartTimeframe === tf ? "active" : ""}
          >
            {tf}
          </Link>
        ))}
      </div>
      {hideSymbolPicker ? null : (
        <div className="filter-row console-live-market-chart__sym">
          <span className="muted" title={t("pages.signals.filters.hintSymbol")}>
            {t("pages.signals.filters.labelSymbol")}:
          </span>
          {symbolOptions.slice(0, 36).map((sym) => (
            <Link
              key={sym}
              href={hrefSym(sym)}
              className={chartSymbol === sym ? "active" : ""}
            >
              {sym}
            </Link>
          ))}
        </div>
      )}
      {resolvedSym !== chartSymbol || resolvedTf !== chartTimeframe ? (
        <p className="muted small console-live-market-chart__resolved">
          {t("ui.chart.resolvedFromGateway", {
            symbol: resolvedSym,
            timeframe: resolvedTf,
          })}
        </p>
      ) : null}
      {showTerminalLink ? (
        <p className="muted small">
          <Link href={terminalHref}>{t("ui.chart.openLiveTerminal")}</Link>
        </p>
      ) : null}
      <ProductCandleChart
        candles={candles}
        showVolume
        loading={loading && candles.length === 0}
        errorMessage={fetchErr}
        emptyMessage={t("ui.chart.emptyCandles")}
        height={height}
        fitContentOnData
        ariaLabel={t("ui.chart.contextAria", {
          symbol: chartSymbol,
          timeframe: chartTimeframe,
        })}
        strategyPriceOverlay={strategyPriceOverlay}
        onStrategyCrosshairHint={setCrosshairHint}
        llmChartIntegration={llmIntegrationEffective}
        llmChartAnnotationsRaw={llmChartAnnotationsRaw ?? null}
        llmChartLayerEnabled={llmChartLayerEnabled}
      />
      {chartSurfaceDiag ? (
        <SurfaceDiagnosticCard model={chartSurfaceDiag} />
      ) : null}
      {showLlmChartUi ? (
        <div
          className="llm-chart-layer-legend"
          role="region"
          aria-label={t("ui.chart.llmLayerAria")}
        >
          <label className="llm-chart-layer-legend__toggle">
            <input
              type="checkbox"
              checked={llmChartLayerEnabled}
              onChange={(e) => onLlmChartLayerEnabledChange?.(e.target.checked)}
            />
            <span>{t("ui.chart.llmLayerToggle")}</span>
          </label>
          <p className="muted small llm-chart-layer-legend__lead">
            {t("ui.chart.llmLayerLead")}
          </p>
          <p className="muted small llm-chart-layer-legend__footnote">
            {t("ui.chart.llmLayerFootnote")}
          </p>
          {llmMeta && llmMeta.timestampsCorrectedFromMs > 0 ? (
            <p
              className="muted small llm-chart-layer-legend__hint"
              role="status"
            >
              {t("ui.chart.llmLayerMsNormalized", {
                count: llmMeta.timestampsCorrectedFromMs,
              })}
            </p>
          ) : null}
          {llmMeta &&
          llmMeta.geometryCandidatesTotal > 0 &&
          llmMeta.geometryKeptTotal === 0 &&
          llmMeta.notesExtracted > 0 ? (
            <p
              className="muted small llm-chart-layer-legend__hint"
              role="status"
            >
              {t("ui.chart.llmLayerGeometryFiltered")}
            </p>
          ) : null}
          {llmNotes.length > 0 ? (
            <ul className="llm-chart-layer-legend__notes">
              {llmNotes.map((line, i) => (
                <li key={`llm-n-${i}-${line.slice(0, 24)}`}>{line}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      <StrategyOverlayLegendBar
        model={overlayModel}
        masterEnabled={strategyMaster}
        onMasterChange={setStrategyMaster}
        layerVisible={layerVisible}
        onLayerChange={onLayerChange}
      />
      {crosshairHint ? (
        <p className="muted small strategy-crosshair-hint" role="status">
          {crosshairHint}
        </p>
      ) : null}
    </div>
  );
}
