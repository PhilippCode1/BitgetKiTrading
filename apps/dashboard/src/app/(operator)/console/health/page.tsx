import Link from "next/link";
import { Suspense } from "react";

import { ConsoleLiveMarketChartSection } from "@/components/console/ConsoleLiveMarketChartSection";
import { LiveDataSituationBar } from "@/components/live-data/LiveDataSituationBar";
import { HealthLoadFailureSurfaceCard } from "@/components/diagnostics/HealthLoadFailureSurfaceCard";
import { HealthOpenAlertsSurfaceBlock } from "@/components/diagnostics/HealthOpenAlertsSurfaceBlock";
import { IssueCenterQuickActions } from "@/components/console/IssueCenterQuickActions";
import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { IntegrationSummaryBanner } from "@/components/panels/IntegrationSummaryBanner";
import { Header } from "@/components/layout/Header";
import { HealthGrid } from "@/components/panels/HealthGrid";
import {
  HealthTradingReadinessPanel,
  type HealthTradingReadinessLabels,
} from "@/components/panels/HealthTradingReadinessPanel";
import { HealthWarningsPanel } from "@/components/panels/HealthWarningsPanel";
import { IntegrationsMatrixPanel } from "@/components/panels/IntegrationsMatrixPanel";
import { AssistLayerPanel } from "@/components/panels/AssistLayerPanel";
import { OperatorExplainPanel } from "@/components/panels/OperatorExplainPanel";
import { SafetyDiagnosisPanel } from "@/components/panels/SafetyDiagnosisPanel";
import {
  fetchAlertOutboxRecent,
  fetchMonitorAlertsOpen,
  fetchSystemHealthCached,
} from "@/lib/api";
import {
  resolveConsoleChartSymbolOptions,
  resolveConsoleChartSymbolTimeframe,
} from "@/lib/console-chart-context";
import { consolePath } from "@/lib/console-paths";
import {
  diagnosticFromSearchParams,
  firstSearchParam,
  type ConsoleSearchParams,
} from "@/lib/console-params";
import { connectivitySupplements } from "@/lib/health-service-reachability";
import { healthWarningsForDisplay } from "@/lib/health-warnings-ui";
import { readConsoleChartPrefs } from "@/lib/chart-prefs-server";
import { executionPathFromSystemHealth } from "@/lib/execution-path-view-model";
import { buildLiveDataSurfaceModelFromHealth } from "@/lib/live-data-surface-model";
import { buildSafetyDiagnosticContext } from "@/lib/safety-diagnosis-context";
import { publicEnv } from "@/lib/env";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function HealthPage({
  searchParams = {},
}: {
  searchParams?: ConsoleSearchParams | Promise<ConsoleSearchParams>;
}) {
  const sp = await Promise.resolve(searchParams);
  const diagnostic = diagnosticFromSearchParams(sp);
  const t = await getServerTranslator();
  let health: import("@/lib/types").SystemHealthResponse | null = null;
  let openAlerts: import("@/lib/types").MonitorAlertItem[] = [];
  let outbox: import("@/lib/types").AlertOutboxItem[] = [];
  let error: string | null = null;
  try {
    const [healthRes, alertsRes, outboxRes] = await Promise.all([
      fetchSystemHealthCached(),
      fetchMonitorAlertsOpen(),
      fetchAlertOutboxRecent(),
    ]);
    health = healthRes;
    openAlerts = alertsRes.items;
    outbox = outboxRes.items;
  } catch (e) {
    error = e instanceof Error ? e.message : t("errors.fallbackMessage");
  }

  const chartPrefs = await readConsoleChartPrefs();
  const { chartSymbol: healthChartSymbol, chartTimeframe: healthChartTf } =
    resolveConsoleChartSymbolTimeframe({
      urlSymbol: firstSearchParam(sp, "symbol"),
      urlTimeframe: firstSearchParam(sp, "timeframe"),
      persistedSymbol: chartPrefs.symbol,
      persistedTimeframe: chartPrefs.timeframe,
      defaultSymbol: publicEnv.defaultSymbol,
      defaultTimeframe: publicEnv.defaultTimeframe,
    });
  const healthChartNav: Record<string, string> = {
    symbol: healthChartSymbol,
    timeframe: healthChartTf,
  };
  const healthSymbolOptions = resolveConsoleChartSymbolOptions({
    facetSymbols: null,
    watchlist: publicEnv.watchlistSymbols,
    chartSymbol: healthChartSymbol,
  });

  const reachSup = health ? connectivitySupplements(health) : null;

  const readinessLabels: HealthTradingReadinessLabels = {
    connectivityTitle: t("pages.health.connectivityTitle"),
    connectivityLead: t("pages.health.connectivityLead"),
    connectivityB1: t("pages.health.connectivityB1"),
    connectivityB2: t("pages.health.connectivityB2"),
    connectivityB3: t("pages.health.connectivityB3"),
    connectivityB4: t("pages.health.connectivityB4"),
    paperPathTitle: t("pages.health.paperPathTitle"),
    paperPathLead: t("pages.health.paperPathLead"),
    paperStep1: t("pages.health.paperStep1"),
    paperStep2: t("pages.health.paperStep2"),
    paperStep3: t("pages.health.paperStep3"),
    paperStep4: t("pages.health.paperStep4"),
    cockpitCta: t("pages.health.cockpitCta"),
    readinessManualExplainer:
      health?.execution.execution_mode === "paper" &&
      health?.execution.strategy_execution_mode === "manual"
        ? t("pages.health.readinessManualExplainer")
        : undefined,
    connectivityExtraMonitorRefused:
      reachSup?.monitorEngineConnectionRefused === true
        ? t("pages.health.connectivityExtraMonitorRefused")
        : undefined,
    connectivityExtraSplitBrain:
      reachSup?.partialReachabilityPattern === true
        ? t("pages.health.connectivityExtraSplitBrain")
        : undefined,
  };

  const executionExplainerParts: string[] = [];
  if (health?.execution.execution_mode === "paper") {
    executionExplainerParts.push(t("pages.health.execLinePaper"));
  }
  if (health?.execution.strategy_execution_mode === "manual") {
    executionExplainerParts.push(t("pages.health.execLineManual"));
  }
  if (health && !health.execution.live_order_submission_enabled) {
    executionExplainerParts.push(t("pages.health.execLineLiveSubmitOff"));
  }
  const executionExplainer =
    executionExplainerParts.length > 0
      ? executionExplainerParts.join(" ")
      : null;

  const safetyDiagnosticBundle = buildSafetyDiagnosticContext({
    health,
    openAlerts,
    outbox,
    loadError: error,
  });

  const healthOverviewModel = health
    ? buildLiveDataSurfaceModelFromHealth({ health })
    : null;
  const executionVm = executionPathFromSystemHealth(health);

  return (
    <>
      <Header
        title={t("pages.health.title")}
        subtitle={t("pages.health.subtitle")}
        helpBriefKey="help.healthPage.brief"
        helpDetailKey="help.healthPage.detail"
      />
      <p className="muted small">
        {t("console.quickLinksLead")}{" "}
        <Link href={consolePath("ops")}>{t("console.nav.ops")}</Link>
        {" · "}
        <Link href={consolePath("live-broker")}>
          {t("console.nav.live_broker")}
        </Link>
        {" · "}
        <Link href={consolePath("usage")}>{t("console.nav.usage")}</Link>
        {" · "}
        <Link href={consolePath("terminal")}>{t("console.nav.terminal")}</Link>
      </p>
      {healthOverviewModel ? (
        <LiveDataSituationBar model={healthOverviewModel} />
      ) : null}
      {error ? (
        <div className="panel" role="status">
          <PanelDataIssue err={error} diagnostic={diagnostic} t={t} />
          <HealthLoadFailureSurfaceCard errorMessage={error} />
          <p className="muted small" style={{ marginTop: 10 }}>
            {t("pages.health.loadErrorHint")}
          </p>
          <Suspense fallback={null}>
            <IssueCenterQuickActions />
          </Suspense>
          <p className="muted small" style={{ marginTop: 10 }}>
            <Link href={consolePath("terminal")}>
              {t("console.nav.terminal")}
            </Link>
          </p>
        </div>
      ) : null}
      {health ? (
        <div className="panel">
          <h2>{t("pages.health.pdfPanelTitle")}</h2>
          <p className="muted small">{t("pages.health.pdfDownloadHint")}</p>
          <p>
            <a href="/api/dashboard/health/operator-report">
              {t("pages.health.pdfDownload")}
            </a>
          </p>
        </div>
      ) : null}
      <OperatorExplainPanel />
      <SafetyDiagnosisPanel
        bundledContextJson={safetyDiagnosticBundle}
        initialQuestionDe={
          error
            ? t(
                "diagnostic.surfaces.healthPageLoadFailed.suggestedSafetyQuestion",
              )
            : undefined
        }
      />
      <AssistLayerPanel
        titleKey="pages.health.assistLayerTitle"
        leadKey="pages.health.assistLayerLead"
        enableOpsRiskForensicLoader
        segments={[
          {
            segment: "admin-operations",
            labelKey: "pages.health.assistTabAdminOps",
            contextHintKey: "pages.health.assistContextHintAdminOps",
          },
          {
            segment: "strategy-signal",
            labelKey: "pages.health.assistTabStrategy",
            contextHintKey: "pages.health.assistContextHintStrategy",
          },
          {
            segment: "ops-risk",
            labelKey: "pages.health.assistTabOpsRisk",
            contextHintKey: "pages.health.assistContextHintOpsRisk",
          },
        ]}
      />
      {health ? (
        <ConsoleLiveMarketChartSection
          pathname={consolePath("health")}
          urlParams={healthChartNav}
          chartSymbol={healthChartSymbol}
          chartTimeframe={healthChartTf}
          symbolOptions={healthSymbolOptions}
          executionVm={executionVm}
          executionModeLabel={health.execution.execution_mode}
          panelTitleKey="pages.health.chartPanelTitle"
          showLiveDataSituationBar={false}
        />
      ) : null}
      {health ? (
        <HealthTradingReadinessPanel health={health} labels={readinessLabels} />
      ) : null}
      {health ? (
        <HealthWarningsPanel
          items={healthWarningsForDisplay(health)}
          heading={t("pages.health.hintsHeading")}
          machineBlockToggleLabel={t("pages.health.machineDetailsToggle")}
          relatedServicesPrefix={t("pages.health.relatedServicesPrefix")}
        />
      ) : null}
      {health ? (
        <IntegrationSummaryBanner matrix={health.integrations_matrix} />
      ) : null}
      {health ? (
        <IntegrationsMatrixPanel matrix={health.integrations_matrix} />
      ) : null}
      {health ? (
        <HealthGrid
          health={health}
          executionExplainer={executionExplainer}
          t={t}
        />
      ) : null}
      <div className="panel">
        <h2>{t("pages.health.alertsHeading")}</h2>
        <p className="muted small">{t("pages.health.alertsLead")}</p>
        {openAlerts.length === 0 ? (
          <p className="muted console-mobile-only">
            {t("help.monitor.alertsEmpty")}
          </p>
        ) : (
          <ul
            className="console-stack-list console-mobile-only"
            aria-label={t("pages.health.alertsHeading")}
          >
            {openAlerts.map((row) => (
              <li key={`m-${row.alert_key}`} className="console-stack-card">
                <div className="console-stack-card__meta">
                  <span className="status-pill">{row.severity}</span>
                  <time className="muted small">
                    {row.updated_ts ?? row.created_ts ?? "—"}
                  </time>
                </div>
                <p className="console-stack-card__title">{row.title}</p>
                <p className="muted small" style={{ margin: 0 }}>
                  {row.message}
                </p>
              </li>
            ))}
          </ul>
        )}
        <div className="table-wrap console-desktop-only">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("pages.health.thSeverity")}</th>
                <th>{t("pages.health.thAlert")}</th>
                <th>{t("pages.health.thMessage")}</th>
                <th>{t("pages.health.thTime")}</th>
              </tr>
            </thead>
            <tbody>
              {openAlerts.length === 0 ? (
                <tr>
                  <td colSpan={4} className="muted">
                    {t("help.monitor.alertsEmpty")}
                  </td>
                </tr>
              ) : (
                openAlerts.map((row) => (
                  <tr key={row.alert_key}>
                    <td>{row.severity}</td>
                    <td>{row.title}</td>
                    <td>{row.message}</td>
                    <td>{row.updated_ts ?? row.created_ts ?? "—"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <HealthOpenAlertsSurfaceBlock
          alerts={openAlerts.map((row) => ({
            severity: row.severity,
            alert_key: row.alert_key,
            title: row.title,
          }))}
        />
      </div>
      <div className="panel">
        <h2>{t("pages.health.outboxHeading")}</h2>
        {outbox.length === 0 ? (
          <p className="muted console-mobile-only">
            {t("help.monitor.outboxEmpty")}
          </p>
        ) : (
          <ul
            className="console-stack-list console-mobile-only"
            aria-label={t("pages.health.outboxHeading")}
          >
            {outbox.map((row) => (
              <li key={`m-${row.alert_id}`} className="console-stack-card">
                <div className="console-stack-card__meta">
                  <span className="mono-small">{row.alert_type}</span>
                  <span className="status-pill">{row.severity}</span>
                </div>
                <div className="console-stack-card__dl">
                  <div>
                    <span className="console-stack-card__k">
                      {t("pages.health.thStatus")}
                    </span>
                    <span className="console-stack-card__v">{row.state}</span>
                  </div>
                  <div>
                    <span className="console-stack-card__k">
                      {t("pages.health.thSymbol")}
                    </span>
                    <span className="console-stack-card__v">
                      {row.symbol ?? "—"}
                    </span>
                  </div>
                  <div>
                    <span className="console-stack-card__k">
                      {t("pages.health.thTime")}
                    </span>
                    <span className="console-stack-card__v mono-small">
                      {row.created_ts ?? "—"}
                    </span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
        <div className="table-wrap console-desktop-only">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("pages.health.thType")}</th>
                <th>{t("pages.health.thSeverity")}</th>
                <th>{t("pages.health.thStatus")}</th>
                <th>{t("pages.health.thAttempt")}</th>
                <th>{t("pages.health.thSymbol")}</th>
                <th>{t("pages.health.thTime")}</th>
              </tr>
            </thead>
            <tbody>
              {outbox.length === 0 ? (
                <tr>
                  <td colSpan={6} className="muted">
                    {t("help.monitor.outboxEmpty")}
                  </td>
                </tr>
              ) : (
                outbox.map((row) => (
                  <tr key={row.alert_id}>
                    <td>{row.alert_type}</td>
                    <td>{row.severity}</td>
                    <td>{row.state}</td>
                    <td>{row.attempt_count ?? "—"}</td>
                    <td>{row.symbol ?? "—"}</td>
                    <td>{row.created_ts ?? "—"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
