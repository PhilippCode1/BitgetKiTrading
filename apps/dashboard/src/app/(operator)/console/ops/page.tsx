import Link from "next/link";

import { CollapsedModuleStaleNotice } from "@/components/console/CollapsedModuleStaleNotice";
import { ConsoleLiveMarketChartSection } from "@/components/console/ConsoleLiveMarketChartSection";
import {
  GlobalIncidentBanner,
  SecondaryIncidentsStrip,
} from "@/components/console/GlobalIncidentBanner";
import { LiveSignalRiskStrip } from "@/components/console/LiveSignalRiskStrip";
import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { Header } from "@/components/layout/Header";
import { OperatorSituationStrip } from "@/components/operator/OperatorSituationStrip";
import { OpenPositionsTable } from "@/components/tables/OpenPositionsTable";
import {
  fetchAlertOutboxRecent,
  fetchLearningDrift,
  fetchLearningDriftOnlineState,
  fetchLiveBrokerDecisions,
  fetchLiveBrokerFills,
  fetchLiveBrokerKillSwitchActive,
  fetchLiveBrokerOrders,
  fetchLiveBrokerRuntime,
  fetchLiveState,
  fetchModelRegistryV2,
  fetchMonitorAlertsOpen,
  fetchPaperMetricsSummary,
  fetchPaperOpen,
  fetchPaperTradesRecent,
  fetchSignalsFacets,
  fetchSystemHealthCached,
} from "@/lib/api";
import { resolveConsoleChartSymbolTimeframe } from "@/lib/console-chart-context";
import { consolePath } from "@/lib/console-paths";
import {
  diagnosticFromSearchParams,
  firstSearchParam,
} from "@/lib/console-params";
import { consoleHref, pickTruthyQueryFields } from "@/lib/console-url-params";
import { readConsoleChartPrefs } from "@/lib/chart-prefs-server";
import { executionPathFromSystemHealth } from "@/lib/execution-path-view-model";
import { publicEnv } from "@/lib/env";
import {
  buildDecisionBuckets,
  matchAlertToDecision,
  summarizePaperVsLiveOutcome,
} from "@/lib/operator-console";
import {
  buildOperatorSituationSummary,
  extractAccountDisplayRows,
  extractPaperPositionRiskRows,
  parseDriftFromRuntimeDetails,
} from "@/lib/operator-snapshot";
import { healthWarningsForDisplay } from "@/lib/health-warnings-ui";
import { formatNum, formatTsMs } from "@/lib/format";
import { getGatewayBootstrapProbeForRequest } from "@/lib/gateway-bootstrap-probe";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import {
  aggregateOpsFetchFailures,
  type OpsModuleId,
} from "@/lib/upstream-incidents";
import type { SystemHealthResponse } from "@/lib/types";
export const dynamic = "force-dynamic";

type SP = Record<string, string | string[] | undefined>;

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function healthServiceByName(
  health: SystemHealthResponse | null,
  name: string,
) {
  return health?.services?.find((s) => s.name === name) ?? null;
}

function fmtTelemetryScalar(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "number" && !Number.isFinite(v)) return "—";
  if (typeof v === "string" && v.length === 0) return "—";
  return String(v);
}

function coveragePreview(cov: unknown, max = 8): string {
  if (!Array.isArray(cov) || cov.length === 0) return "—";
  const parts = cov.slice(0, max).map((item) => {
    if (item !== null && typeof item === "object" && !Array.isArray(item)) {
      const o = item as Record<string, unknown>;
      const ch = o.channel != null ? String(o.channel) : "";
      const id =
        o.instId != null
          ? String(o.instId)
          : o.coin != null
            ? String(o.coin)
            : "";
      return id ? `${ch}:${id}` : ch || JSON.stringify(o);
    }
    return String(item);
  });
  const tail = cov.length > max ? ` +${cov.length - max}` : "";
  return `${parts.join(", ")}${tail}`;
}

export default async function OperatorCockpitPage({
  searchParams,
}: {
  searchParams: SP | Promise<SP>;
}) {
  const sp = await Promise.resolve(searchParams);
  const t = await getServerTranslator();
  const diagnostic = diagnosticFromSearchParams(sp);
  const chartPrefs = await readConsoleChartPrefs();
  const { chartSymbol: sym, chartTimeframe: tf } =
    resolveConsoleChartSymbolTimeframe({
      urlSymbol: firstSearchParam(sp, "symbol"),
      urlTimeframe: firstSearchParam(sp, "timeframe"),
      persistedSymbol: chartPrefs.symbol,
      persistedTimeframe: chartPrefs.timeframe,
      defaultSymbol: publicEnv.defaultSymbol,
      defaultTimeframe: publicEnv.defaultTimeframe,
    });
  const marketFamily =
    firstSearchParam(sp, "market_family")?.trim() || undefined;
  const symbolOptions = Array.from(
    new Set([sym, publicEnv.defaultSymbol, ...publicEnv.watchlistSymbols]),
  )
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
  const tfOptions = ["1m", "5m", "15m", "1h", "4h"] as const;

  const settled = await Promise.allSettled([
    fetchSystemHealthCached(),
    fetchLiveState({ symbol: sym, timeframe: tf, limit: 120 }),
    fetchModelRegistryV2(),
    fetchLiveBrokerRuntime(),
    fetchLiveBrokerKillSwitchActive(),
    fetchLiveBrokerOrders(),
    fetchLiveBrokerFills(),
    fetchPaperOpen(sym),
    fetchPaperMetricsSummary(),
    fetchMonitorAlertsOpen(),
    fetchLearningDriftOnlineState(),
    fetchLearningDrift(),
    fetchLiveBrokerDecisions(),
    fetchAlertOutboxRecent(),
    fetchPaperTradesRecent({ limit: 25 }),
  ]);
  const facetsResult = await fetchSignalsFacets({ lookback_rows: 4000 }).catch(
    () => null,
  );

  const health = settled[0].status === "fulfilled" ? settled[0].value : null;
  const executionVm = executionPathFromSystemHealth(health);
  const healthErr =
    settled[0].status === "rejected"
      ? settled[0].reason instanceof Error
        ? settled[0].reason.message
        : t("pages.ops.errHealth")
      : null;

  const live = settled[1].status === "fulfilled" ? settled[1].value : null;
  const liveErr =
    settled[1].status === "rejected"
      ? settled[1].reason instanceof Error
        ? settled[1].reason.message
        : t("pages.ops.errLiveState")
      : null;

  const models =
    settled[2].status === "fulfilled" ? settled[2].value.items : [];
  const modelsErr =
    settled[2].status === "rejected"
      ? settled[2].reason instanceof Error
        ? settled[2].reason.message
        : t("pages.ops.errModelRegistry")
      : null;

  const runtime =
    settled[3].status === "fulfilled" ? settled[3].value.item : null;
  const lbErr =
    settled[3].status === "rejected"
      ? settled[3].reason instanceof Error
        ? settled[3].reason.message
        : t("pages.ops.errLiveBrokerRuntime")
      : null;

  const killActive =
    settled[4].status === "fulfilled" ? settled[4].value.items : [];
  const killErr =
    settled[4].status === "rejected"
      ? settled[4].reason instanceof Error
        ? settled[4].reason.message
        : t("pages.ops.errKillSwitch")
      : null;

  const orders =
    settled[5].status === "fulfilled" ? settled[5].value.items : [];
  const ordersErr =
    settled[5].status === "rejected"
      ? settled[5].reason instanceof Error
        ? settled[5].reason.message
        : t("pages.ops.errOrders")
      : null;

  const fills = settled[6].status === "fulfilled" ? settled[6].value.items : [];
  const fillsErr =
    settled[6].status === "rejected"
      ? settled[6].reason instanceof Error
        ? settled[6].reason.message
        : t("pages.ops.errFills")
      : null;

  const paperPos =
    settled[7].status === "fulfilled" ? settled[7].value.positions : [];
  const paperErr =
    settled[7].status === "rejected"
      ? settled[7].reason instanceof Error
        ? settled[7].reason.message
        : t("pages.ops.errPaperPositions")
      : null;

  const paperMetrics =
    settled[8].status === "fulfilled" ? settled[8].value : null;
  const paperMetricsErr =
    settled[8].status === "rejected"
      ? settled[8].reason instanceof Error
        ? settled[8].reason.message
        : t("pages.ops.errPaperMetrics")
      : null;

  const monitorAlerts =
    settled[9].status === "fulfilled" ? settled[9].value.items : [];
  const monitorErr =
    settled[9].status === "rejected"
      ? settled[9].reason instanceof Error
        ? settled[9].reason.message
        : t("pages.ops.errMonitorAlerts")
      : null;

  const onlineDriftState =
    settled[10].status === "fulfilled"
      ? settled[10].value
      : { item: null, detail: undefined };
  const onlineDriftErr =
    settled[10].status === "rejected"
      ? settled[10].reason instanceof Error
        ? settled[10].reason.message
        : t("pages.ops.errOnlineDrift")
      : null;

  const learnDriftItems =
    settled[11].status === "fulfilled" ? settled[11].value.items : [];
  const learnDriftErr =
    settled[11].status === "rejected"
      ? settled[11].reason instanceof Error
        ? settled[11].reason.message
        : t("pages.ops.errLearningDrift")
      : null;

  const lbDecisions =
    settled[12].status === "fulfilled" ? settled[12].value.items : [];
  const lbDecisionsErr =
    settled[12].status === "rejected"
      ? settled[12].reason instanceof Error
        ? settled[12].reason.message
        : t("pages.ops.errLiveDecisions")
      : null;

  const alertOutbox =
    settled[13].status === "fulfilled" ? settled[13].value.items : [];
  const alertOutboxErr =
    settled[13].status === "rejected"
      ? settled[13].reason instanceof Error
        ? settled[13].reason.message
        : t("pages.ops.errAlertOutbox")
      : null;

  const paperTradesRecent =
    settled[14].status === "fulfilled" ? settled[14].value.trades : [];
  const paperTradesErr =
    settled[14].status === "rejected"
      ? settled[14].reason instanceof Error
        ? settled[14].reason.message
        : t("pages.ops.errPaperTrades")
      : null;

  const champions = models.filter(
    (m) => m.promoted_bool || m.role.toLowerCase().includes("champion"),
  );
  const buckets = buildDecisionBuckets(lbDecisions);
  const approvalQueue = buckets.approvalQueue.map((decision) => ({
    decision,
    alert: matchAlertToDecision(decision, alertOutbox),
  }));
  const liveMirrors = buckets.liveMirrors.map((decision) => ({
    decision,
    alert: matchAlertToDecision(decision, alertOutbox),
  }));
  const divergenceRows = buckets.divergenceRows;
  const drift = runtime ? parseDriftFromRuntimeDetails(runtime.details) : null;
  const accountRows = runtime ? extractAccountDisplayRows(runtime.details) : [];
  const paperMetas = paperPos.map((p) =>
    p.meta && typeof p.meta === "object" && !Array.isArray(p.meta)
      ? (p.meta as Record<string, unknown>)
      : {},
  );
  const paperRiskRows = extractPaperPositionRiskRows(paperMetas);
  const outcomeSummary = summarizePaperVsLiveOutcome({
    decisions: lbDecisions,
    fills,
    paperTrades: paperTradesRecent,
  });
  const instrumentMeta = asRecord(runtime?.current_instrument_metadata);
  const currentSignal = live?.latest_signal ?? null;
  const currentSignalWarnings = Array.isArray(
    currentSignal?.live_execution_block_reasons_json,
  )
    ? currentSignal.live_execution_block_reasons_json
    : [];
  const currentSignalUniversalBlocks = Array.isArray(
    currentSignal?.governor_universal_hard_block_reasons_json,
  )
    ? currentSignal.governor_universal_hard_block_reasons_json
    : [];
  const opsQueryBase = {
    symbol: sym,
    timeframe: tf,
    market_family: marketFamily,
  };
  const opsHref = (extra: Record<string, string | undefined | null>) =>
    consoleHref(consolePath("ops"), opsQueryBase, extra);

  const panelFetchErrors = [
    healthErr,
    liveErr,
    modelsErr,
    lbErr,
    killErr,
    ordersErr,
    fillsErr,
    paperErr,
    paperMetricsErr,
    monitorErr,
    onlineDriftErr,
    learnDriftErr,
    lbDecisionsErr,
    alertOutboxErr,
    paperTradesErr,
  ].filter(Boolean) as string[];

  const gatewayProbe = await getGatewayBootstrapProbeForRequest();

  const agg = aggregateOpsFetchFailures([
    { id: "health", error: healthErr },
    { id: "liveState", error: liveErr },
    { id: "models", error: modelsErr },
    { id: "liveBrokerRuntime", error: lbErr },
    { id: "killSwitch", error: killErr },
    { id: "orders", error: ordersErr },
    { id: "fills", error: fillsErr },
    { id: "paperPositions", error: paperErr },
    { id: "paperMetrics", error: paperMetricsErr },
    { id: "monitorAlerts", error: monitorErr },
    { id: "onlineDrift", error: onlineDriftErr },
    { id: "learningDrift", error: learnDriftErr },
    { id: "liveDecisions", error: lbDecisionsErr },
    { id: "alertOutbox", error: alertOutboxErr },
    { id: "paperTrades", error: paperTradesErr },
  ]);

  type IntegrationKey =
    | "liveDb"
    | "liveRedis"
    | "monitorApi"
    | "onlineDriftApi"
    | "learningDriftApi";
  const integrationIssues: { key: IntegrationKey; raw: string }[] = [];
  if (live && live.health.db !== "ok") {
    integrationIssues.push({ key: "liveDb", raw: String(live.health.db) });
  }
  if (live && live.health.redis !== "ok" && live.health.redis !== "skipped") {
    integrationIssues.push({
      key: "liveRedis",
      raw: String(live.health.redis),
    });
  }
  if (monitorErr && !agg.suppressedModules.has("monitorAlerts")) {
    integrationIssues.push({ key: "monitorApi", raw: monitorErr });
  }
  if (onlineDriftErr && !agg.suppressedModules.has("onlineDrift")) {
    integrationIssues.push({ key: "onlineDriftApi", raw: onlineDriftErr });
  }
  if (learnDriftErr && !agg.suppressedModules.has("learningDrift")) {
    integrationIssues.push({ key: "learningDriftApi", raw: learnDriftErr });
  }

  const structuredHealthWarnings = health
    ? healthWarningsForDisplay(health)
    : [];
  const hasDegradation =
    structuredHealthWarnings.length > 0 || integrationIssues.length > 0;

  const showPartialSummary =
    !agg.transportCascade && panelFetchErrors.length >= 3;

  /** Kein zweites grosses Incident-Panel, wenn das Console-Layout schon den Gateway-Bootstrap-Banner zeigt. */
  const showTransportIncidentBanner =
    Boolean(agg.transportCascade) && gatewayProbe.rootCause === "ok";

  const sup = agg.suppressedModules;
  function panelIssue(err: string | null, mid: OpsModuleId) {
    if (!err) return null;
    if (sup.has(mid))
      return <CollapsedModuleStaleNotice moduleId={mid} t={t} />;
    return <PanelDataIssue err={err} diagnostic={diagnostic} t={t} />;
  }

  const situation = buildOperatorSituationSummary({
    health,
    killSwitchActiveCount: killActive.length,
    onlineDrift: onlineDriftState.item,
    openMonitorAlerts: monitorAlerts.length,
    recentDriftItemsCount: learnDriftItems.length,
  });

  return (
    <>
      <Header
        title={t("console.nav.ops")}
        subtitle={`${sym} / ${tf}. ${t("pages.ops.lead")}`}
        helpBriefKey="help.risk.brief"
        helpDetailKey="help.risk.detail"
      />

      {showTransportIncidentBanner && agg.transportCascade ? (
        <GlobalIncidentBanner
          cascade={agg.transportCascade}
          secondary={agg.secondaryIncidents}
          diagnostic={diagnostic}
          t={t}
        />
      ) : !showTransportIncidentBanner && agg.secondaryIncidents.length > 0 ? (
        <div className="global-incident-stack">
          <SecondaryIncidentsStrip
            secondary={agg.secondaryIncidents}
            diagnostic={diagnostic}
            t={t}
          />
        </div>
      ) : null}

      <OperatorSituationStrip summary={situation} symbol={sym} timeframe={tf} />

      <ConsoleLiveMarketChartSection
        pathname={consolePath("ops")}
        urlParams={pickTruthyQueryFields(opsQueryBase)}
        chartSymbol={sym}
        chartTimeframe={tf}
        symbolOptions={symbolOptions}
        executionVm={executionVm}
        executionModeLabel={health?.execution.execution_mode ?? null}
        panelTitleKey="pages.ops.priceChartTitle"
      />

      {showPartialSummary ? (
        <div
          className="console-fetch-notice console-fetch-notice--soft"
          role="status"
        >
          <p className="console-fetch-notice__title">
            {t("pages.ops.partialLoad.title")}
          </p>
          <p className="console-fetch-notice__body muted small">
            {t("pages.ops.partialLoad.body")}
          </p>
          {!diagnostic ? (
            <p className="console-fetch-notice__refresh muted small">
              {t("ui.diagnostic.urlHint")}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="panel">
        <h2>{t("pages.ops.panelFocus")}</h2>
        <div className="filter-row">
          <span className="muted" title={t("pages.signals.filters.hintSymbol")}>
            {t("pages.ops.labelSymbol")}:
          </span>
          {symbolOptions.map((item) => (
            <Link
              key={item}
              href={opsHref({ symbol: item })}
              className={sym === item ? "active" : ""}
            >
              {item}
            </Link>
          ))}
        </div>
        <div className="filter-row">
          <span
            className="muted"
            title={t("pages.signals.filters.hintTimeframe")}
          >
            {t("pages.ops.labelTimeframe")}:
          </span>
          {tfOptions.map((item) => (
            <Link
              key={item}
              href={opsHref({ timeframe: item })}
              className={tf === item ? "active" : ""}
            >
              {item}
            </Link>
          ))}
        </div>
        <div className="filter-row">
          <span className="muted" title={t("pages.ops.hintOpsMarketFamily")}>
            {t("pages.ops.labelMarketFamily")}:
          </span>
          <Link
            href={opsHref({ market_family: null })}
            className={!marketFamily ? "active" : ""}
          >
            {t("pages.ops.filterAll")}
          </Link>
          {(facetsResult?.market_families ?? []).map((item) => (
            <Link
              key={item}
              href={opsHref({ market_family: item })}
              className={marketFamily === item ? "active" : ""}
            >
              {item}
            </Link>
          ))}
        </div>
        <div className="signal-grid">
          <div>
            <span className="label">{t("pages.ops.labelObservedSymbols")}</span>
            <div>{facetsResult?.symbols.length ?? "—"}</div>
          </div>
          <div>
            <span className="label">{t("pages.ops.labelRouterExit")}</span>
            <div>
              {facetsResult?.specialist_routers.length ?? 0} /{" "}
              {facetsResult?.exit_families.length ?? 0}
            </div>
          </div>
          <div>
            <span className="label" title={t("pages.ops.hintOpsCanonicalId")}>
              {t("pages.ops.labelCanonicalId")}
            </span>
            <div className="mono-small">
              {currentSignal?.canonical_instrument_id ?? "—"}
            </div>
          </div>
          <div>
            <span className="label" title={t("pages.ops.hintOpsSignalFamily")}>
              {t("pages.ops.labelSignalFamily")}
            </span>
            <div>{currentSignal?.market_family ?? marketFamily ?? "—"}</div>
          </div>
          <div>
            <span className="label" title={t("pages.ops.hintOpsRuntimeMeta")}>
              {t("pages.ops.labelRuntimeMeta")}
            </span>
            <div className="mono-small">
              {String(instrumentMeta?.metadata_source ?? "—")} / verified=
              {String(instrumentMeta?.metadata_verified ?? "—")}
            </div>
          </div>
          <div>
            <span className="label">{t("pages.ops.labelCatalogSnapshot")}</span>
            <div className="mono-small">
              {runtime?.instrument_catalog?.snapshot_id
                ? String(runtime.instrument_catalog.snapshot_id)
                : "—"}
            </div>
          </div>
          <div>
            <span className="label">
              {t("pages.ops.labelCapabilityCategories")}
            </span>
            <div>
              {runtime?.instrument_catalog?.capability_matrix?.length ?? "—"}
            </div>
          </div>
        </div>
        <p className="muted small" style={{ marginTop: 8 }}>
          {t("pages.ops.focusInstrumentExplainer")}
        </p>
      </div>

      {learnDriftItems.length > 0 ? (
        <div className="panel operator-drift-recent">
          <h2>{t("pages.ops.driftRecentTitle")}</h2>
          <ul className="news-list">
            {learnDriftItems.slice(0, 5).map((d) => (
              <li key={d.drift_id}>
                <strong>{d.metric_name}</strong>{" "}
                <span className="muted">({d.severity})</span> —{" "}
                {d.detected_ts ?? "—"}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {hasDegradation ? (
        <details
          className="panel operator-degraded-wrap"
          open={structuredHealthWarnings.length + integrationIssues.length <= 2}
        >
          <summary className="operator-degraded-summary">
            {t("pages.ops.degradedHeading")}{" "}
            <span className="muted small">
              ({structuredHealthWarnings.length + integrationIssues.length})
            </span>
          </summary>
          <div className="operator-degraded" role="status">
            <ul className="news-list">
              {structuredHealthWarnings.map((w) => (
                <li key={w.code} className="operator-warn-soft">
                  <div className="health-warning-title">{w.title}</div>
                  <p>{w.message}</p>
                  <p className="muted small">{w.next_step}</p>
                  <p className="muted small">
                    {t("pages.health.relatedServicesPrefix")}{" "}
                    {w.related_services}
                  </p>
                </li>
              ))}
              {integrationIssues.map((issue) => (
                <li key={issue.key} className="operator-warn-soft">
                  <div className="health-warning-title">
                    {t(`pages.ops.integration.${issue.key}.title`)}
                  </div>
                  <p>{t(`pages.ops.integration.${issue.key}.body`)}</p>
                  {diagnostic ? (
                    <pre
                      className="console-fetch-notice__pre"
                      style={{ marginTop: 6 }}
                    >
                      {issue.raw}
                    </pre>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        </details>
      ) : null}

      <div className="panel">
        <details>
          <summary className="operator-details-summary">
            {t("pages.ops.executionDetailsSummary")}
          </summary>
          {panelIssue(healthErr, "health")}
          {health ? (
            <ul className="news-list operator-metric-list">
              <li>
                {t("pages.ops.executionExecMode")}:{" "}
                <strong>{health.execution.execution_mode}</strong>
              </li>
              <li>
                {t("pages.ops.executionStrategyMode")}:{" "}
                <strong>{health.execution.strategy_execution_mode}</strong>
              </li>
              <li>
                {t("pages.ops.executionPaperActive")}:{" "}
                <strong>{String(health.execution.paper_path_active)}</strong>
              </li>
              <li>
                {t("pages.ops.executionShadowEnable")}:{" "}
                <strong>{String(health.execution.shadow_trade_enable)}</strong>{" "}
                · {t("pages.ops.executionShadowPath")}:{" "}
                <strong>{String(health.execution.shadow_path_active)}</strong>
              </li>
              <li>
                {t("pages.ops.executionLiveEnable")}:{" "}
                <strong>{String(health.execution.live_trade_enable)}</strong> ·{" "}
                {t("pages.ops.executionLiveSubmit")}:{" "}
                <strong>
                  {String(health.execution.live_order_submission_enabled)}
                </strong>
              </li>
              {health.execution.execution_runtime ? (
                <>
                  <li className="muted">
                    {t("pages.ops.executionRuntimeLine", {
                      version: health.execution.execution_runtime.schema_version,
                      lb: String(
                        health.execution.execution_runtime.capabilities
                          .live_broker_consumes_signals,
                      ),
                      ex: String(
                        health.execution.execution_runtime.capabilities
                          .exchange_order_submit_automated,
                      ),
                    })}
                  </li>
                  <li className="muted">
                    {t("pages.ops.executionLiveReleaseLine", {
                      full: String(
                        health.execution.execution_runtime.live_release
                          .fully_released_for_automated_exchange_orders,
                      ),
                      manualSuffix:
                        health.execution.execution_runtime.live_release
                          .manual_strategy_holds_live_firewall
                          ? t("pages.ops.executionLiveReleaseManualHold")
                          : "",
                    })}
                  </li>
                </>
              ) : null}
            </ul>
          ) : !healthErr ? (
            <p className="muted degradation-inline">
              {t("pages.ops.executionNoHealth")}
            </p>
          ) : null}
          {health ? (
            <p className="muted">
              {t("pages.ops.executionReconcile")}:{" "}
              {health.ops.live_broker.latest_reconcile_status ?? "—"}
              {health.ops.live_broker.latest_reconcile_age_ms != null
                ? t("pages.ops.executionReconcileAge", {
                    ms: health.ops.live_broker.latest_reconcile_age_ms,
                  })
                : ""}
            </p>
          ) : null}
        </details>
      </div>

      <div
        className="panel"
        role="region"
        aria-label={t("pages.ops.wsStreamPanelTitle")}
      >
        <h2>{t("pages.ops.wsStreamPanelTitle")}</h2>
        <p className="muted small">{t("pages.ops.wsStreamPanelLead")}</p>
        {(() => {
          const ms = healthServiceByName(health, "market-stream");
          const lb = healthServiceByName(health, "live-broker");
          const pub =
            ms?.configured === false
              ? null
              : ((ms?.bitget_ws_stream as
                  | Record<string, unknown>
                  | undefined) ?? null);
          const priv =
            lb?.configured === false
              ? null
              : ((lb?.private_ws as Record<string, unknown> | undefined) ??
                null);
          return (
            <div className="grid-2" style={{ marginTop: 12 }}>
              <div>
                <p className="label" style={{ marginTop: 0 }}>
                  {t("pages.ops.wsStreamMarketStream")}
                </p>
                {ms == null || ms.configured === false ? (
                  <p className="muted degradation-inline">
                    {t("pages.ops.wsStreamNotConfigured")}
                  </p>
                ) : pub == null ? (
                  <p className="muted degradation-inline">
                    {t("pages.ops.wsStreamNoTelemetry")}
                  </p>
                ) : (
                  <ul className="news-list operator-metric-list">
                    <li>
                      {t("pages.ops.wsStreamConnection")}:{" "}
                      <strong>
                        {fmtTelemetryScalar(pub.connection_state)}
                      </strong>
                    </li>
                    <li>
                      {t("pages.ops.wsStreamLastEventAge")}:{" "}
                      <strong>
                        {fmtTelemetryScalar(pub.last_event_age_ms)}
                      </strong>
                    </li>
                    <li>
                      {t("pages.ops.wsStreamIngestLatency")}:{" "}
                      <strong>
                        {fmtTelemetryScalar(pub.last_ingest_latency_ms)}
                      </strong>
                    </li>
                    <li>
                      {t("pages.ops.wsStreamGapEvents")}:{" "}
                      <strong>
                        {fmtTelemetryScalar(pub.gap_events_count)}
                      </strong>
                    </li>
                    <li>
                      {t("pages.ops.wsStreamStaleEscalation")}:{" "}
                      <strong>
                        {fmtTelemetryScalar(pub.stale_escalation_count)}
                      </strong>
                    </li>
                    <li>
                      {t("pages.ops.wsStreamDataFreshness")}:{" "}
                      <strong>
                        {fmtTelemetryScalar(pub.data_freshness_ok)} (
                        {fmtTelemetryScalar(pub.data_freshness_reason)})
                      </strong>
                    </li>
                    <li>
                      {t("pages.ops.wsStreamGapfill")}:{" "}
                      <strong>
                        {fmtTelemetryScalar(pub.gapfill_last_reason)}
                      </strong>{" "}
                      @ {fmtTelemetryScalar(pub.gapfill_last_ok_ts_ms)}
                    </li>
                    <li>
                      {t("pages.ops.wsStreamCoverage")}:{" "}
                      <span className="mono-small">
                        {coveragePreview(pub.subscription_coverage)}
                      </span>
                    </li>
                  </ul>
                )}
              </div>
              <div>
                <p className="label" style={{ marginTop: 0 }}>
                  {t("pages.ops.wsStreamLiveBroker")}
                </p>
                {lb == null || lb.configured === false ? (
                  <p className="muted degradation-inline">
                    {t("pages.ops.wsStreamNotConfigured")}
                  </p>
                ) : priv == null ? (
                  <p className="muted degradation-inline">
                    {t("pages.ops.wsStreamNoTelemetry")}
                  </p>
                ) : (
                  <ul className="news-list operator-metric-list">
                    <li>
                      {t("pages.ops.wsStreamConnection")}:{" "}
                      <strong>{fmtTelemetryScalar(priv.state)}</strong>
                    </li>
                    <li>
                      {t("pages.ops.wsStreamHost")}:{" "}
                      <strong className="mono-small">
                        {fmtTelemetryScalar(priv.ws_endpoint_host)}
                      </strong>
                    </li>
                    <li>
                      {t("pages.ops.wsStreamLastEventAge")}:{" "}
                      <strong>
                        {fmtTelemetryScalar(priv.last_event_age_ms)}
                      </strong>
                    </li>
                    <li>
                      {t("pages.ops.wsStreamIngestLatency")}:{" "}
                      <strong>
                        {fmtTelemetryScalar(priv.last_ingest_latency_ms)}
                      </strong>
                    </li>
                    <li>
                      {t("pages.ops.wsStreamPrivateStale")}:{" "}
                      <strong>
                        {fmtTelemetryScalar(priv.data_stale_suspected)}
                      </strong>{" "}
                      (≤ {fmtTelemetryScalar(priv.stale_threshold_sec)} s)
                    </li>
                    <li>
                      {t("pages.ops.wsStreamPrivateCatchups")}:{" "}
                      <strong>
                        {fmtTelemetryScalar(priv.gap_recovery_triggers)}
                      </strong>{" "}
                      / esc {fmtTelemetryScalar(priv.stale_escalation_count)}
                    </li>
                    <li>
                      {t("pages.ops.wsStreamCoverage")}:{" "}
                      <span className="mono-small">
                        {coveragePreview(priv.channel_coverage)}
                      </span>
                    </li>
                  </ul>
                )}
              </div>
            </div>
          );
        })()}
      </div>

      <div className="grid-2">
        <div className="panel">
          <h2>Mirror-Freigabe (Approval Queue)</h2>
          <p className="muted small">
            Nur `operator_release_pending`-Kandidaten für die enge
            Echtgeld-Mirror-Stufe. Telegram dient hier nur als bestaetigender
            Kanal, nie als Strategiekonfiguration.
          </p>
          {approvalQueue.length === 0 ? (
            <p className="muted degradation-inline">
              Keine offenen Live-Kandidaten im Fenster.
            </p>
          ) : (
            <div className="table-wrap">
              <table className="data-table data-table--dense">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Familie</th>
                    <th>Lane</th>
                    <th>Action</th>
                    <th>Mirror</th>
                    <th>Telegram</th>
                    <th>execution_id</th>
                    <th>Forensik</th>
                  </tr>
                </thead>
                <tbody>
                  {approvalQueue.map(({ decision, alert }) => (
                    <tr key={decision.execution_id}>
                      <td>{decision.symbol}</td>
                      <td>{decision.signal_market_family ?? "—"}</td>
                      <td className="mono-small">
                        {decision.signal_meta_trade_lane ?? "—"}
                      </td>
                      <td className="mono-small">{decision.decision_action}</td>
                      <td>
                        {decision.live_mirror_eligible == null
                          ? "—"
                          : `${String(decision.live_mirror_eligible)} / match ${String(decision.shadow_live_match_ok ?? "—")}`}
                      </td>
                      <td className="mono-small">
                        {alert
                          ? `${alert.alert_type} / ${alert.state} / ${alert.telegram_message_id ?? "—"}`
                          : "—"}
                      </td>
                      <td className="mono-small">
                        {decision.execution_id.slice(0, 12)}…
                      </td>
                      <td>
                        <Link
                          href={consolePath(
                            `live-broker/forensic/${decision.execution_id}`,
                          )}
                        >
                          Timeline
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <div className="panel">
          <h2>Live Mirrors &amp; Divergenz</h2>
          <p className="muted small">
            Spiegelbare Execution-Kandidaten und erkannte
            Shadow-vs-Live-Abweichungen aus dem Live-Broker-Journal.
          </p>
          {liveMirrors.length === 0 && divergenceRows.length === 0 ? (
            <p className="muted degradation-inline">
              Keine Mirror-/Divergenz-Faelle im Fenster.
            </p>
          ) : (
            <div className="table-wrap">
              <table className="data-table data-table--dense">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Action</th>
                    <th>Mirror</th>
                    <th>Shadow≈Live</th>
                    <th>Risk</th>
                    <th>Release</th>
                  </tr>
                </thead>
                <tbody>
                  {Array.from(
                    new Map(
                      [
                        ...liveMirrors.map(({ decision }) => decision),
                        ...divergenceRows,
                      ].map((decision) => [decision.execution_id, decision]),
                    ).values(),
                  )
                    .slice(0, 12)
                    .map((decision) => (
                      <tr key={decision.execution_id}>
                        <td>{decision.symbol}</td>
                        <td className="mono-small">
                          {decision.decision_action}
                        </td>
                        <td>
                          {decision.live_mirror_eligible == null
                            ? "—"
                            : String(decision.live_mirror_eligible)}
                        </td>
                        <td>
                          {decision.shadow_live_match_ok == null
                            ? "—"
                            : String(decision.shadow_live_match_ok)}
                        </td>
                        <td className="mono-small">
                          {decision.risk_primary_reason ?? "—"}
                        </td>
                        <td>
                          {decision.operator_release_exists
                            ? "released"
                            : "pending"}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <div className="grid-2">
        <div className="panel">
          <h2>Plan- / Decision-Queue (Live-Broker)</h2>
          {panelIssue(lbDecisionsErr, "liveDecisions")}
          <p className="muted small">
            Deterministische Queue aus <code>live.execution_decisions</code>.
            Approval-Status, Mirror-Eignung, Governor-Hinweise und Telegram-Link
            werden aus Journal/Outbox zusammengezogen, nicht aus Client-Secrets.
          </p>
          {lbDecisions.length === 0 && !lbDecisionsErr ? (
            <p className="muted degradation-inline">
              Keine Decision-Zeilen im Fenster.
            </p>
          ) : (
            <div className="table-wrap">
              <table className="data-table data-table--dense">
                <thead>
                  <tr>
                    <th>Zeit</th>
                    <th>Symbol</th>
                    <th>Familie</th>
                    <th>Lane</th>
                    <th>Action</th>
                    <th>Runtime</th>
                    <th>Shadow≈Live</th>
                    <th>Mirror?</th>
                    <th>Release</th>
                    <th>Risk</th>
                    <th>Forensik</th>
                    <th>execution_id</th>
                  </tr>
                </thead>
                <tbody>
                  {lbDecisions.slice(0, 18).map((d) => (
                    <tr key={d.execution_id}>
                      <td>{d.created_ts ?? "—"}</td>
                      <td>{d.symbol}</td>
                      <td className="mono-small">
                        {d.signal_market_family ?? "—"}
                      </td>
                      <td className="mono-small">
                        {d.signal_meta_trade_lane ?? "—"}
                      </td>
                      <td className="mono-small">{d.decision_action}</td>
                      <td>{d.effective_runtime_mode}</td>
                      <td>
                        {d.shadow_live_match_ok == null
                          ? "—"
                          : String(d.shadow_live_match_ok)}
                      </td>
                      <td>
                        {d.live_mirror_eligible == null
                          ? "—"
                          : String(d.live_mirror_eligible)}
                      </td>
                      <td>
                        {d.operator_release_exists ? "released" : "pending"}
                      </td>
                      <td className="mono-small">
                        {d.risk_primary_reason ?? "—"}
                      </td>
                      <td>
                        <Link
                          href={consolePath(
                            `live-broker/forensic/${d.execution_id}`,
                          )}
                        >
                          Timeline
                        </Link>
                      </td>
                      <td className="mono-small">
                        <Link
                          href={consolePath(
                            `live-broker/forensic/${d.execution_id}`,
                          )}
                          title={d.execution_id}
                        >
                          {d.execution_id.slice(0, 8)}…
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="muted">
            Queue-Fenster: {buckets.planQueue.length} / {lbDecisions.length} —
            offene Approvals: {approvalQueue.length} — released live:{" "}
            {buckets.releasedLive.length}
          </p>
        </div>
        <div className="panel">
          <h2>Alert-Outbox / Telegram-Anbindung</h2>
          {panelIssue(alertOutboxErr, "alertOutbox")}
          {alertOutbox.length === 0 && !alertOutboxErr ? (
            <p className="muted degradation-inline">
              Keine Outbox-Eintraege im Fenster.
            </p>
          ) : (
            <div className="table-wrap">
              <table className="data-table data-table--dense">
                <thead>
                  <tr>
                    <th>State</th>
                    <th>Typ</th>
                    <th>Symbol</th>
                    <th>Signal / Exec</th>
                    <th>telegram_message_id</th>
                    <th>Versuche</th>
                    <th>Zeit</th>
                  </tr>
                </thead>
                <tbody>
                  {alertOutbox.slice(0, 15).map((a) => (
                    <tr key={a.alert_id}>
                      <td>{a.state}</td>
                      <td className="mono-small">{a.alert_type}</td>
                      <td>{a.symbol ?? "—"}</td>
                      <td className="mono-small">
                        {String(
                          (typeof a.payload?.signal_id === "string" &&
                            a.payload.signal_id) ||
                            (typeof a.payload?.execution_id === "string" &&
                              a.payload.execution_id) ||
                            (typeof a.payload?.correlation_id === "string" &&
                              a.payload.correlation_id) ||
                            "—",
                        ).slice(0, 18)}
                      </td>
                      <td>{a.telegram_message_id ?? "—"}</td>
                      <td>{a.attempt_count ?? "—"}</td>
                      <td>{a.sent_ts ?? a.created_ts ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <div className="panel">
        <h2>Model-Slots (Registry v2, alle Rollen)</h2>
        {panelIssue(modelsErr, "models")}
        {models.length === 0 && !modelsErr ? (
          <p className="muted degradation-inline">Keine Registry-Zeilen.</p>
        ) : (
          <div className="table-wrap">
            <table className="data-table data-table--dense">
              <thead>
                <tr>
                  <th>Modell</th>
                  <th>Rolle</th>
                  <th>Scope</th>
                  <th>Run</th>
                  <th>Status</th>
                  <th>promoted</th>
                </tr>
              </thead>
              <tbody>
                {models.slice(0, 40).map((m) => (
                  <tr key={`${m.model_name}-${m.run_id}-${m.role}`}>
                    <td>{m.model_name}</td>
                    <td>{m.role}</td>
                    <td className="mono-small">
                      {m.scope_type ?? "—"}
                      {m.scope_key ? `:${m.scope_key}` : ""}
                    </td>
                    <td className="mono-small">{m.run_id.slice(0, 12)}…</td>
                    <td>{m.calibration_status}</td>
                    <td>{String(m.promoted_bool)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="grid-2">
        <div className="panel">
          <h2>Paper — letzte Trades (Outcome-Fenster)</h2>
          {panelIssue(paperTradesErr, "paperTrades")}
          <p className="muted small">
            Vergleich mit Live nur operativ — keine implizite 1:1-Spiegelung.
            Detail: <Link href={consolePath("paper")}>Paper-Seite</Link>.
          </p>
          <ul className="news-list operator-metric-list">
            <li>
              Live-Kandidaten / released:{" "}
              <strong>{outcomeSummary.liveCandidates}</strong> /{" "}
              <strong>{outcomeSummary.releasedLive}</strong>
            </li>
            <li>
              Paper geschlossen W/L: <strong>{outcomeSummary.paperWins}</strong>{" "}
              / <strong>{outcomeSummary.paperLosses}</strong>
            </li>
            <li>
              Live-Fills / Mirror-eligible:{" "}
              <strong>{outcomeSummary.liveFills}</strong> /{" "}
              <strong>{outcomeSummary.mirrorEligible}</strong>
            </li>
          </ul>
          {paperTradesRecent.length === 0 && !paperTradesErr ? (
            <p className="muted degradation-inline">
              Keine geschlossenen Paper-Trades im Fenster.
            </p>
          ) : (
            <div className="table-wrap">
              <table className="data-table data-table--dense">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Seite</th>
                    <th>State</th>
                    <th>PnL net</th>
                    <th>Closed</th>
                  </tr>
                </thead>
                <tbody>
                  {paperTradesRecent.slice(0, 12).map((t) => (
                    <tr key={t.position_id}>
                      <td>{t.symbol}</td>
                      <td>{t.side}</td>
                      <td>{t.state}</td>
                      <td>
                        {t.pnl_net_usdt == null
                          ? "—"
                          : formatNum(t.pnl_net_usdt, 4)}
                      </td>
                      <td>
                        {t.closed_ts_ms == null
                          ? "—"
                          : formatTsMs(t.closed_ts_ms)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <div className="panel">
          <h2>Drift &amp; Pfad-Gates</h2>
          <p className="muted small">
            Materialisierte Online-Drift (Learning) + Reconcile-Kennzahlen —
            steuern Degradation, nicht Einzelorders.
          </p>
          <ul className="news-list operator-metric-list">
            <li>
              Online-Drift Aktion:{" "}
              <strong>{onlineDriftState.item?.effective_action ?? "—"}</strong>
              {onlineDriftState.item?.computed_at
                ? ` (${onlineDriftState.item.computed_at})`
                : ""}
            </li>
            <li>
              Letzte Drift-Events (Learning):{" "}
              <strong>{learnDriftItems.length}</strong> sichtbar (
              <Link href={consolePath("learning")}>Learning</Link>)
            </li>
            <li>
              Live-Fills im Cockpit-Fenster: <strong>{fills.length}</strong>{" "}
              (siehe unten)
            </li>
            <li>
              Divergenz-Faelle:{" "}
              <strong>{outcomeSummary.divergenceCount}</strong> / blockierte
              Live-Entscheide: <strong>{outcomeSummary.blockedLive}</strong>
            </li>
          </ul>
        </div>
      </div>

      <div className="grid-2">
        <div className="panel">
          <h2>Champion-Modelle (Registry, Kurzliste)</h2>
          {champions.length === 0 && !modelsErr ? (
            <p className="muted degradation-inline">
              Keine promoted Slots — Learning/Registry prüfen.
            </p>
          ) : (
            <ul className="news-list">
              {champions.map((m) => (
                <li key={`${m.model_name}-${m.run_id}`}>
                  <strong>{m.model_name}</strong> ({m.role}) run{" "}
                  <code>{m.run_id}</code> — Kalibrierung: {m.calibration_status}
                  {m.version ? ` — v${m.version}` : ""}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="panel">
          <h2>Signal &amp; Risiko (letztes Bundle)</h2>
          {panelIssue(liveErr, "liveState")}
          <LiveSignalRiskStrip signal={live?.latest_signal ?? null} t={t} />
          {currentSignal ? (
            <ul
              className="news-list operator-metric-list"
              style={{ marginTop: 10 }}
            >
              <li>
                Echtgeld frei:{" "}
                <strong>
                  {currentSignal.live_execution_clear_for_real_money === true
                    ? "ja"
                    : currentSignal.live_execution_clear_for_real_money ===
                        false
                      ? "nein"
                      : "—"}
                </strong>
              </li>
              <li>
                Governor universal / live:{" "}
                <strong>{currentSignalUniversalBlocks.length}</strong> /{" "}
                <strong>{currentSignalWarnings.length}</strong>
              </li>
              <li>
                Stop-Fragil / Exec:{" "}
                <strong>
                  {typeof currentSignal.stop_fragility_0_1 === "number"
                    ? currentSignal.stop_fragility_0_1.toFixed(2)
                    : "—"}
                </strong>{" "}
                /{" "}
                <strong>
                  {typeof currentSignal.stop_executability_0_1 === "number"
                    ? currentSignal.stop_executability_0_1.toFixed(2)
                    : "—"}
                </strong>
              </li>
            </ul>
          ) : null}
        </div>
      </div>

      <div className="grid-2">
        <div className="panel">
          <h2>Kill-Switch</h2>
          {panelIssue(killErr, "killSwitch")}
          {killActive.length > 0 ? (
            <ul className="news-list operator-warn">
              {killActive.map((k) => (
                <li key={k.kill_switch_event_id}>
                  <strong>{k.scope}</strong> / {k.scope_key}: {k.reason} (
                  {k.source})
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Keine aktiven Kill-Switches.</p>
          )}
          {health?.ops.live_broker.safety_latch_active ? (
            <p className="operator-warn" role="status">
              <strong>Safety-Latch aktiv</strong> — signalgetriebener Live-Pfad
              blockiert bis operatorisches Release (
              <code>POST /v1/live-broker/safety/safety-latch/release</code>
              ). Audit:{" "}
              <code>
                GET /v1/live-broker/audit/recent?category=safety_latch
              </code>
              . Runbook: <code>docs/emergency_runbook.md</code>.
            </p>
          ) : null}
        </div>
        <div className="panel">
          <h2>Shadow vs. Live (Reconcile-Drift)</h2>
          {panelIssue(lbErr, "liveBrokerRuntime")}
          {runtime && drift ? (
            <ul className="news-list">
              <li>
                Drift gesamt: <strong>{drift.totalCount ?? "—"}</strong>
              </li>
              <li>
                Positions-Abweichungen:{" "}
                <strong>{drift.positionMismatchCount ?? "—"}</strong>
              </li>
              <li>
                Orders nur lokal: <strong>{drift.orderLocalOnly ?? "—"}</strong>{" "}
                / nur Boerse: <strong>{drift.orderExchangeOnly ?? "—"}</strong>
              </li>
              <li>
                Shadow-Match-Pflicht:{" "}
                <strong>
                  {String(runtime.require_shadow_match_before_live ?? false)}
                </strong>
              </li>
            </ul>
          ) : !lbErr ? (
            <p className="muted degradation-inline">
              Keine Runtime-Snapshot-Daten.
            </p>
          ) : null}
          <p className="muted">
            <Link href={consolePath("live-broker")}>
              Vollstaendiges Live-Broker-Journal
            </Link>
          </p>
        </div>
      </div>

      <div className="grid-2">
        <div className="panel">
          <h2>Margin / Kontext (Exchange-Snapshot)</h2>
          {accountRows.length === 0 ? (
            <p className="muted degradation-inline">
              Keine Account-Rohfelder im letzten Reconcile — bei Live-Betrieb
              Live-Broker/Exchange prüfen.
            </p>
          ) : (
            <ul className="news-list">
              {accountRows.map((r) => (
                <li key={r.label}>
                  <code>{r.label}</code>: {r.value}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="panel">
          <h2>Paper: Liquidationspuffer / Margin-Felder</h2>
          {panelIssue(paperErr, "paperPositions")}
          {panelIssue(paperMetricsErr, "paperMetrics")}
          {paperMetrics?.account ? (
            <ul className="news-list">
              <li>
                Equity:{" "}
                <strong>{formatNum(paperMetrics.account.equity, 4)}</strong>{" "}
                {paperMetrics.account.currency ?? "USDT"}
              </li>
              <li>
                Initial:{" "}
                <strong>
                  {formatNum(paperMetrics.account.initial_equity, 4)}
                </strong>
              </li>
            </ul>
          ) : !paperMetricsErr ? (
            <p className="muted">Kein Paper-Konto materialisiert.</p>
          ) : null}
          {paperRiskRows.length > 0 ? (
            <ul className="news-list">
              {paperRiskRows.map((r) => (
                <li key={r.label}>
                  <code>{r.label}</code>: {r.value}
                </li>
              ))}
            </ul>
          ) : paperPos.length > 0 ? (
            <p className="muted">
              Keine Liquidations-Meta-Felder in offenen Positionen (normal wenn
              Engine keine annotiert).
            </p>
          ) : null}
          <OpenPositionsTable positions={paperPos} />
        </div>
      </div>

      <div className="panel">
        <h2>Live-Orders (kurz)</h2>
        {panelIssue(ordersErr, "orders")}
        {orders.length === 0 && !ordersErr ? (
          <p className="muted degradation-inline">Keine Orders im Fenster.</p>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Status</th>
                  <th>Seite</th>
                  <th>Aktualisiert</th>
                </tr>
              </thead>
              <tbody>
                {orders.slice(0, 12).map((o) => (
                  <tr key={o.internal_order_id}>
                    <td>{o.symbol}</td>
                    <td>{o.status}</td>
                    <td>{o.side}</td>
                    <td>{o.updated_ts ?? o.created_ts ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="panel">
        <h2>Letzte Fills</h2>
        {panelIssue(fillsErr, "fills")}
        {fills.length === 0 && !fillsErr ? (
          <p className="muted degradation-inline">Keine Fills im Fenster.</p>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Seite</th>
                  <th>Preis</th>
                  <th>Menge</th>
                  <th>Zeit</th>
                </tr>
              </thead>
              <tbody>
                {fills.slice(0, 15).map((f) => (
                  <tr key={f.exchange_trade_id}>
                    <td>{f.symbol}</td>
                    <td>{f.side}</td>
                    <td>{f.price ?? "—"}</td>
                    <td>{f.size ?? "—"}</td>
                    <td>{f.created_ts ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
