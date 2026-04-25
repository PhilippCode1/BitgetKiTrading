import { ConsoleLiveMarketChartSection } from "@/components/console/ConsoleLiveMarketChartSection";
import { HealthSnapshotLoadNotice } from "@/components/console/HealthSnapshotLoadNotice";
import { LiveDataSituationBar } from "@/components/live-data/LiveDataSituationBar";
import { ExecutionPathSummaryList } from "@/components/console/ExecutionPathSummaryList";
import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { ConsolePartialLoadNotice } from "@/components/console/ConsolePartialLoadNotice";
import { GatewayReadNotice } from "@/components/console/GatewayReadNotice";
import { EmptyStateHelp } from "@/components/help/EmptyStateHelp";
import { Header } from "@/components/layout/Header";
import Link from "next/link";
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
import {
  executionPathFromLiveBrokerRuntime,
  executionPathFromSystemHealth,
} from "@/lib/execution-path-view-model";
import { buildLiveDataSurfaceModelFromBrokerPage } from "@/lib/live-data-surface-model";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import { userFacingBodyForFetchFailure } from "@/lib/user-facing-fetch-error";
import { readConsoleChartPrefs } from "@/lib/chart-prefs-server";
import { buildPrivateCredentialViewModel } from "@/lib/private-credential-view-model";
import {
  brokerLastOrderActionSummary,
  brokerLiveBlockers,
  brokerLiveTradingStatus,
  brokerUnknownStates,
  orderStatusCountsNonEmpty,
  prettyJsonLine,
  recordHasKeys,
} from "@/lib/live-broker-console";
import {
  fetchLiveBrokerAuditRecent,
  fetchLiveBrokerDecisions,
  fetchLiveBrokerFills,
  fetchLiveBrokerKillSwitchActive,
  fetchLiveBrokerKillSwitchEvents,
  fetchLiveBrokerOrderActions,
  fetchLiveBrokerOrders,
  fetchLiveBrokerRuntime,
  fetchSystemHealthBestEffort,
} from "@/lib/api";
import { publicEnv } from "@/lib/env";
import type {
  LiveBrokerAuditResponse,
  LiveBrokerAuditTrail,
  LiveBrokerDecisionItem,
  LiveBrokerFillItem,
  LiveBrokerKillSwitchEvent,
  LiveBrokerKillSwitchResponse,
  LiveBrokerOrderActionItem,
  LiveBrokerOrderItem,
  LiveBrokerOrdersResponse,
  LiveBrokerRuntimeItem,
  LiveBrokerRuntimeResponse,
} from "@/lib/types";

import { LiveSubmissionOperatorStrip } from "./live-submission-operator-strip";
import { ExecutionSafetyPanel } from "@/components/safety/ExecutionSafetyPanel";

export const dynamic = "force-dynamic";

export default async function LiveBrokerOpsPage({
  searchParams = {},
}: {
  searchParams?: ConsoleSearchParams | Promise<ConsoleSearchParams>;
}) {
  const sp = await Promise.resolve(searchParams);
  const diagnostic = diagnosticFromSearchParams(sp);
  const t = await getServerTranslator();
  const dash = t("pages.broker.emDash");

  const sectionErrors: string[] = [];

  const settled = await Promise.allSettled([
    fetchLiveBrokerRuntime(),
    fetchLiveBrokerKillSwitchActive(),
    fetchLiveBrokerKillSwitchEvents(),
    fetchLiveBrokerAuditRecent(),
    fetchLiveBrokerDecisions(),
    fetchLiveBrokerOrders(),
    fetchLiveBrokerFills(),
    fetchLiveBrokerOrderActions(),
  ]);

  const [rtRes, actRes, evRes, audRes, decRes, ordRes, filRes, oaRes] = settled;

  let runtimeResponse: LiveBrokerRuntimeResponse | undefined;
  if (rtRes.status === "fulfilled") runtimeResponse = rtRes.value;
  else
    sectionErrors.push(
      `${t("pages.broker.sectionRuntime")}: ${userFacingBodyForFetchFailure(rtRes.reason, t)}`,
    );

  let activeResponse: LiveBrokerKillSwitchResponse | undefined;
  if (actRes.status === "fulfilled") activeResponse = actRes.value;
  else
    sectionErrors.push(
      `${t("pages.broker.sectionKillActive")}: ${userFacingBodyForFetchFailure(actRes.reason, t)}`,
    );

  let eventsResponse: LiveBrokerKillSwitchResponse | undefined;
  if (evRes.status === "fulfilled") eventsResponse = evRes.value;
  else
    sectionErrors.push(
      `${t("pages.broker.sectionKillEvents")}: ${userFacingBodyForFetchFailure(evRes.reason, t)}`,
    );

  let auditResponse: LiveBrokerAuditResponse | undefined;
  if (audRes.status === "fulfilled") auditResponse = audRes.value;
  else
    sectionErrors.push(
      `${t("pages.broker.sectionAudit")}: ${userFacingBodyForFetchFailure(audRes.reason, t)}`,
    );

  let decisionsResponse:
    | Awaited<ReturnType<typeof fetchLiveBrokerDecisions>>
    | undefined;
  if (decRes.status === "fulfilled") decisionsResponse = decRes.value;
  else
    sectionErrors.push(
      `${t("pages.broker.sectionDecisions")}: ${userFacingBodyForFetchFailure(decRes.reason, t)}`,
    );

  let ordersResponse: LiveBrokerOrdersResponse | undefined;
  if (ordRes.status === "fulfilled") ordersResponse = ordRes.value;
  else
    sectionErrors.push(
      `${t("pages.broker.sectionOrders")}: ${userFacingBodyForFetchFailure(ordRes.reason, t)}`,
    );

  let fillsResponse:
    | Awaited<ReturnType<typeof fetchLiveBrokerFills>>
    | undefined;
  if (filRes.status === "fulfilled") fillsResponse = filRes.value;
  else
    sectionErrors.push(
      `${t("pages.broker.sectionFills")}: ${userFacingBodyForFetchFailure(filRes.reason, t)}`,
    );

  let actionsResponse:
    | Awaited<ReturnType<typeof fetchLiveBrokerOrderActions>>
    | undefined;
  if (oaRes.status === "fulfilled") actionsResponse = oaRes.value;
  else
    sectionErrors.push(
      `${t("pages.broker.sectionOrderActions")}: ${userFacingBodyForFetchFailure(oaRes.reason, t)}`,
    );

  const runtime: LiveBrokerRuntimeItem | null = runtimeResponse?.item ?? null;
  const active: LiveBrokerKillSwitchEvent[] = activeResponse?.items ?? [];
  const events: LiveBrokerKillSwitchEvent[] = eventsResponse?.items ?? [];
  const audit: LiveBrokerAuditTrail[] = auditResponse?.items ?? [];
  const decisions: LiveBrokerDecisionItem[] = decisionsResponse?.items ?? [];
  const orders: LiveBrokerOrderItem[] = ordersResponse?.items ?? [];
  const fills: LiveBrokerFillItem[] = fillsResponse?.items ?? [];
  const orderActions: LiveBrokerOrderActionItem[] =
    actionsResponse?.items ?? [];

  const allFailed = sectionErrors.length === settled.length;
  const pageError = allFailed ? sectionErrors.join(" · ") : null;

  const chartPrefs = await readConsoleChartPrefs();
  const { chartSymbol: brokerChartSymbol, chartTimeframe: brokerChartTf } =
    resolveConsoleChartSymbolTimeframe({
      urlSymbol: firstSearchParam(sp, "symbol"),
      urlTimeframe: firstSearchParam(sp, "timeframe"),
      persistedSymbol: chartPrefs.symbol,
      persistedTimeframe: chartPrefs.timeframe,
      defaultSymbol: publicEnv.defaultSymbol,
      defaultTimeframe: publicEnv.defaultTimeframe,
    });
  const brokerChartNav: Record<string, string> = {
    symbol: brokerChartSymbol,
    timeframe: brokerChartTf,
  };
  const brokerSymbolOptions = resolveConsoleChartSymbolOptions({
    facetSymbols: null,
    watchlist: publicEnv.watchlistSymbols,
    chartSymbol: brokerChartSymbol,
  });

  function listSectionNotice(
    res: LiveBrokerKillSwitchResponse | LiveBrokerAuditResponse | undefined,
  ) {
    if (!res) {
      return (
        <p className="muted small degradation-inline" role="status">
          {t("pages.broker.sectionUnavailable")}
        </p>
      );
    }
    return <GatewayReadNotice payload={res} t={t} />;
  }

  /** Prüft, ob die Sektion wegen Fetch fehlt (Label steht am Anfang von sectionErrors). */
  function sectionFetchFailed(label: string): boolean {
    return sectionErrors.some((line) => line.startsWith(`${label}:`));
  }

  const { health, error: healthLoadError } =
    await fetchSystemHealthBestEffort();
  const chartExecutionVm =
    executionPathFromLiveBrokerRuntime(runtime) ??
    executionPathFromSystemHealth(health);
  const brokerSituationModel = buildLiveDataSurfaceModelFromBrokerPage({
    executionVm: chartExecutionVm,
    runtimeSnapshotTs: runtime?.created_ts ?? null,
    upstreamOk: runtime?.upstream_ok ?? null,
    sectionErrorCount: sectionErrors.length,
    runtimeFetchFailed: sectionFetchFailed(t("pages.broker.sectionRuntime")),
  });
  const privateCredentialVm = buildPrivateCredentialViewModel(runtime);
  const liveStatus = brokerLiveTradingStatus({ runtime, health });
  const liveBlockerReasons = brokerLiveBlockers({
    runtime,
    health,
    orderCount: orders.length,
  });
  const unknownStates = brokerUnknownStates({ runtime, health });
  const lastOrderAction = brokerLastOrderActionSummary({ orders, orderActions });
  const reconcileStatus = health?.ops?.live_broker?.latest_reconcile_status ?? "unbekannt";
  const reconcileOk = reconcileStatus === "ok";
  const killSwitchActive = (runtime?.active_kill_switches?.length ?? 0) > 0;
  const safetyLatchActive = runtime?.safety_latch_active === true;

  return (
    <>
      <Header
        title={t("pages.broker.title")}
        subtitle={t("pages.broker.subtitle")}
        helpBriefKey="help.broker.brief"
        helpDetailKey="help.broker.detail"
      />
      <PanelDataIssue err={pageError} diagnostic={diagnostic} t={t} />
      <HealthSnapshotLoadNotice
        error={healthLoadError}
        diagnostic={diagnostic}
        t={t}
      />

      {!allFailed && sectionErrors.length > 0 ? (
        <ConsolePartialLoadNotice
          t={t}
          titleKey="pages.broker.partialLoadTitle"
          bodyKey="pages.broker.partialLoadBody"
          lines={sectionErrors}
          diagnostic={diagnostic}
        />
      ) : null}

      {runtime?.operator_live_submission ? (
        <LiveSubmissionOperatorStrip
          summary={runtime.operator_live_submission}
          t={t}
        />
      ) : null}

      <LiveDataSituationBar model={brokerSituationModel} />

      <div className="panel">
        <h2>Broker-Uebersicht</h2>
        <ul className="news-list">
          <li>
            Betriebsmodus: <strong>{runtime?.execution_mode ?? dash}</strong>
          </li>
          <li>
            Live-Trading aktiv: <strong>{liveStatus}</strong>
          </li>
          <li>
            Bitget Public Readiness:{" "}
            <strong>
              {runtime?.bitget_private_status?.public_api_ok == null
                ? "unbekannt"
                : String(runtime?.bitget_private_status?.public_api_ok)}
            </strong>
          </li>
          <li>
            Bitget Private Readiness:{" "}
            <strong>
              {runtime?.bitget_private_status?.private_auth_ok == null
                ? "unbekannt"
                : String(runtime?.bitget_private_status?.private_auth_ok)}
            </strong>
          </li>
          <li>
            Reconcile-Status: <strong>{reconcileStatus}</strong>
          </li>
          <li>
            Safety-Latch: <strong>{safetyLatchActive ? "aktiv" : "aus"}</strong>
          </li>
          <li>
            Kill-Switch: <strong>{killSwitchActive ? "aktiv" : "aus"}</strong>
          </li>
          <li>
            Letzte Order/Action: <strong>{lastOrderAction}</strong>
          </li>
        </ul>
        {liveBlockerReasons.length > 0 ? (
          <p className="muted small" role="status">
            Live-Blocker: {liveBlockerReasons.join(" · ")}
          </p>
        ) : (
          <p className="muted small" role="status">
            Keine harten Live-Blocker erkannt.
          </p>
        )}
        {unknownStates.length > 0 ? (
          <p className="muted small" role="status">
            Unknown States: {unknownStates.join(" · ")}
          </p>
        ) : null}
      </div>

      <ExecutionSafetyPanel
        killSwitchActive={killSwitchActive}
        safetyLatchActive={safetyLatchActive}
        reconcileOk={reconcileOk}
      />

      <ConsoleLiveMarketChartSection
        pathname={consolePath("live-broker")}
        urlParams={brokerChartNav}
        chartSymbol={brokerChartSymbol}
        chartTimeframe={brokerChartTf}
        symbolOptions={brokerSymbolOptions}
        executionVm={chartExecutionVm}
        executionModeLabel={runtime?.execution_mode ?? null}
        panelTitleKey="pages.broker.chartPanelTitle"
        showLiveDataSituationBar={false}
      />

      <div className="panel">
        <h2>{t("pages.broker.runtimePanelTitle")}</h2>
        {runtimeResponse ? (
          <GatewayReadNotice payload={runtimeResponse} t={t} />
        ) : null}
        {runtime ? (
          <ExecutionPathSummaryList
            model={executionPathFromLiveBrokerRuntime(runtime)}
            t={t}
          />
        ) : sectionFetchFailed(t("pages.broker.sectionRuntime")) ? (
          <p className="muted small" role="status">
            {t("pages.broker.sectionUnavailable")}
          </p>
        ) : (
          <EmptyStateHelp
            titleKey="help.broker.runtimeEmptyTitle"
            bodyKey="help.broker.runtimeEmptyBody"
            stepKeys={["help.broker.runtimeStep1", "help.broker.runtimeStep2"]}
            commsPhase="unknown"
          />
        )}
      </div>

      <div className="panel">
        <h2>{t("pages.broker.bitgetPanelTitle")}</h2>
        {sectionFetchFailed(t("pages.broker.sectionRuntime")) ? (
          <p className="muted small" role="status">
            {t("pages.broker.sectionUnavailable")}
          </p>
        ) : runtime?.bitget_private_status ? (
          <>
            <ul className="news-list">
              <li>
                {t("pages.broker.bitgetProfile")}:{" "}
                <strong>
                  {runtime.bitget_private_status.credential_profile ?? dash}
                </strong>{" "}
                ({runtime.bitget_private_status.bitget_connection_label})
              </li>
              <li>
                {t("pages.broker.bitgetUiStatus")}:{" "}
                <strong>{runtime.bitget_private_status.ui_status}</strong>
              </li>
              <li>
                {t("pages.broker.bitgetPublicApi")}:{" "}
                <strong>
                  {String(runtime.bitget_private_status.public_api_ok ?? dash)}
                </strong>
              </li>
              <li>
                {t("pages.broker.bitgetKeysConfigured")}:{" "}
                <strong>
                  {String(
                    runtime.bitget_private_status.private_api_configured ??
                      dash,
                  )}
                </strong>
              </li>
              <li>
                {t("pages.broker.bitgetPrivateAuth")}:{" "}
                <strong>
                  {String(
                    runtime.bitget_private_status.private_auth_ok ?? dash,
                  )}
                </strong>
                {runtime.bitget_private_status.private_auth_classification
                  ? ` (${runtime.bitget_private_status.private_auth_classification})`
                  : null}
              </li>
              <li>
                {t("pages.broker.bitgetPaptradingHeader")}:{" "}
                <strong>
                  {String(
                    runtime.bitget_private_status.paptrading_header_active ??
                      dash,
                  )}
                </strong>
              </li>
              <li>
                {t("pages.broker.bitgetIsolationRelaxed")}:{" "}
                <strong>
                  {String(
                    runtime.bitget_private_status
                      .credential_isolation_relaxed ?? dash,
                  )}
                </strong>
              </li>
            </ul>
            {runtime.bitget_private_status.private_auth_detail_de ? (
              <p className="muted small" role="status">
                {runtime.bitget_private_status.private_auth_detail_de}
              </p>
            ) : null}
            <div className="panel" style={{ marginTop: "1rem", padding: "0.8rem" }}>
              <h3 className="small">Bitget-Verbindung</h3>
              <ul className="news-list">
                <li>
                  Credential-Status (redacted):{" "}
                  <strong>{privateCredentialVm.status}</strong>
                </li>
                <li>
                  Demo/Live-Modus:{" "}
                  <strong>
                    {privateCredentialVm.demoModus ? "demo_only" : "live_or_paper"}
                  </strong>
                </li>
                <li>
                  Read-only geprüft:{" "}
                  <strong>{String(privateCredentialVm.readOnlyGeprueft)}</strong>
                </li>
                <li>
                  Trading-Permission erkannt:{" "}
                  <strong>{String(privateCredentialVm.tradingPermissionErkannt)}</strong>
                </li>
                <li>
                  Withdrawal-Permission erkannt:{" "}
                  <strong>
                    {privateCredentialVm.withdrawalPermissionErkannt == null
                      ? "unklar"
                      : String(privateCredentialVm.withdrawalPermissionErkannt)}
                  </strong>
                </li>
                <li>
                  Live-Write:{" "}
                  <strong>
                    {privateCredentialVm.liveWriteBlocked
                      ? "blockiert"
                      : "eligible_after_all_gates"}
                  </strong>
                </li>
                <li>
                  Letzte Prüfung:{" "}
                  <strong>{privateCredentialVm.letztePruefung ?? dash}</strong>
                </li>
                <li>
                  Credential-Hints:{" "}
                  <strong>
                    key={privateCredentialVm.credentialHints.apiKey}, secret=
                    {privateCredentialVm.credentialHints.apiSecret}, passphrase=
                    {privateCredentialVm.credentialHints.passphrase}
                  </strong>
                </li>
                <li>
                  Runtime-Profil:{" "}
                  <strong>{publicEnv.deploymentProfile || "local_private"}</strong>
                </li>
              </ul>
              {privateCredentialVm.blockgruendeDe.length ? (
                <p className="muted small" role="status">
                  {privateCredentialVm.blockgruendeDe.join(" | ")}
                </p>
              ) : null}
              <p className="muted small" role="status">
                Sicherheitsmodus:{" "}
                {publicEnv.deploymentProfile === "local_ngrok_preview"
                  ? "ngrok-preview erkannt; sensible Daten bleiben geschützt und Live-Write blockiert."
                  : publicEnv.deploymentProfile === "production_private"
                    ? "production_private aktiv; server-only Auth und fail-closed Live-Gates erforderlich."
                    : "Privater Modus aktiv; bei Unsicherheit bleibt Live blockiert."}
              </p>
            </div>
            {runtime.bitget_private_status.bitget_private_rest ? (
              <>
                <h3 className="small" style={{ marginTop: "1rem" }}>
                  {t("pages.broker.bitgetRestCircuitTitle")}
                </h3>
                <pre className="muted">
                  {prettyJsonLine(
                    runtime.bitget_private_status.bitget_private_rest,
                  )}
                </pre>
              </>
            ) : null}
          </>
        ) : (
          <p className="muted small" role="status">
            {t("pages.broker.bitgetNoDiagnostic")}
          </p>
        )}
      </div>

      <div className="panel">
        <h2>{t("pages.broker.orderStatusTitle")}</h2>
        {sectionFetchFailed(t("pages.broker.sectionRuntime")) ? (
          <p className="muted small" role="status">
            {t("pages.broker.sectionUnavailable")}
          </p>
        ) : runtime ? (
          orderStatusCountsNonEmpty(runtime.order_status_counts) ? (
            <pre className="muted">
              {prettyJsonLine(runtime.order_status_counts)}
            </pre>
          ) : (
            <p className="muted small" role="status">
              {t("pages.broker.orderStatusEmpty")}
            </p>
          )
        ) : (
          <p className="muted small" role="status">
            {t("pages.broker.orderStatusEmpty")}
          </p>
        )}
      </div>

      <div className="panel">
        <h2>{t("pages.broker.instrumentPanelTitle")}</h2>
        {sectionFetchFailed(t("pages.broker.sectionRuntime")) ? (
          <p className="muted small" role="status">
            {t("pages.broker.sectionUnavailable")}
          </p>
        ) : runtime ? (
          <>
            <ul className="news-list">
              <li>
                {t("pages.broker.instrumentSnapshotLabel")}:{" "}
                <strong>
                  {runtime.instrument_catalog?.snapshot_id ?? dash}
                </strong>
              </li>
              <li>
                {t("pages.broker.instrumentStatusLabel")}:{" "}
                <strong>{runtime.instrument_catalog?.status ?? dash}</strong>
              </li>
              <li>
                {t("pages.broker.instrumentCapCategoriesLabel")}:{" "}
                <strong>
                  {runtime.instrument_catalog?.capability_matrix?.length ?? 0}
                </strong>
              </li>
            </ul>
            <h3>{t("pages.broker.instrumentCatalogTitle")}</h3>
            <pre className="muted">
              {prettyJsonLine(runtime.instrument_catalog ?? {})}
            </pre>
            <h3>{t("pages.broker.instrumentActiveTitle")}</h3>
            <pre className="muted">
              {prettyJsonLine(runtime.current_instrument_metadata ?? {})}
            </pre>
          </>
        ) : (
          <p className="muted" role="status">
            {t("pages.broker.instrumentEmpty")}
          </p>
        )}
      </div>

      <div className="panel">
        <h2>{t("pages.broker.reconcilePanelTitle")}</h2>
        {sectionFetchFailed(t("pages.broker.sectionRuntime")) ? (
          <p className="muted small" role="status">
            {t("pages.broker.sectionUnavailable")}
          </p>
        ) : runtime ? (
          recordHasKeys(runtime.details) ? (
            <pre className="muted">{prettyJsonLine(runtime.details)}</pre>
          ) : (
            <p className="muted" role="status">
              {t("pages.broker.reconcileEmpty")}
            </p>
          )
        ) : (
          <p className="muted" role="status">
            {t("pages.broker.reconcileEmpty")}
          </p>
        )}
      </div>

      <div className="panel">
        <h2>{t("pages.broker.sectionKillActive")}</h2>
        {listSectionNotice(activeResponse)}
        {active.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("pages.broker.thScope")}</th>
                  <th>{t("pages.broker.thKey")}</th>
                  <th>{t("pages.broker.thReason")}</th>
                  <th>{t("pages.broker.thSource")}</th>
                  <th>{t("pages.broker.thTime")}</th>
                </tr>
              </thead>
              <tbody>
                {active.map((row) => (
                  <tr key={row.kill_switch_event_id}>
                    <td>{row.scope}</td>
                    <td>{row.scope_key}</td>
                    <td>{row.reason}</td>
                    <td>{row.source}</td>
                    <td>{row.created_ts ?? dash}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : activeResponse &&
          !sectionFetchFailed(t("pages.broker.sectionKillActive")) ? (
          !(activeResponse.empty_state && activeResponse.message) ? (
            <p className="muted" role="status">
              {t("pages.broker.killSwitchInactiveExplain")}
            </p>
          ) : null
        ) : null}
      </div>

      <div className="panel">
        <h2>{t("pages.broker.sectionAudit")}</h2>
        {listSectionNotice(auditResponse)}
        {audit.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("pages.broker.thCategory")}</th>
                  <th>{t("pages.broker.thAction")}</th>
                  <th>{t("pages.broker.thSeverity")}</th>
                  <th>{t("pages.broker.thKey")}</th>
                  <th>{t("pages.broker.thSymbol")}</th>
                  <th>{t("pages.broker.thDetails")}</th>
                  <th>{t("pages.broker.thTime")}</th>
                </tr>
              </thead>
              <tbody>
                {audit.map((row) => (
                  <tr key={row.audit_trail_id}>
                    <td>{row.category}</td>
                    <td>{row.action}</td>
                    <td>{row.severity}</td>
                    <td>{row.scope_key}</td>
                    <td>{row.symbol ?? dash}</td>
                    <td>
                      <pre className="json-mini">
                        {prettyJsonLine(row.details)}
                      </pre>
                    </td>
                    <td>{row.created_ts ?? dash}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : auditResponse &&
          !sectionFetchFailed(t("pages.broker.sectionAudit")) ? (
          !(auditResponse.empty_state && auditResponse.message) ? (
            <p className="muted degradation-inline" role="status">
              {t("pages.broker.tableEmptyOperational")}
            </p>
          ) : null
        ) : null}
      </div>

      <div className="panel">
        <h2>{t("pages.broker.sectionDecisions")}</h2>
        {decisionsResponse ? (
          <GatewayReadNotice payload={decisionsResponse} t={t} />
        ) : (
          <p className="muted small degradation-inline" role="status">
            {t("pages.broker.sectionUnavailable")}
          </p>
        )}
        {decisions.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("pages.broker.thSymbol")}</th>
                  <th>{t("pages.broker.thFamily")}</th>
                  <th>{t("pages.broker.thLane")}</th>
                  <th>{t("pages.broker.thDecisionAction")}</th>
                  <th>{t("pages.broker.thDecisionReason")}</th>
                  <th>{t("pages.broker.thSignalAction")}</th>
                  <th>{t("pages.broker.thLevFree")}</th>
                  <th>{t("pages.broker.thLevFinal")}</th>
                  <th>{t("pages.broker.thCaps")}</th>
                  <th>{t("pages.broker.thShadowLiveOk")}</th>
                  <th>{t("pages.broker.thMirror")}</th>
                  <th>{t("pages.broker.thRelease")}</th>
                  <th>{t("pages.broker.thRisk")}</th>
                  <th>{t("pages.broker.thShadowHard")}</th>
                  <th>{t("pages.broker.thForensic")}</th>
                  <th>{t("pages.broker.thTime")}</th>
                </tr>
              </thead>
              <tbody>
                {decisions.map((row) => (
                  <tr key={row.execution_id}>
                    <td>{row.symbol}</td>
                    <td>{row.signal_market_family ?? dash}</td>
                    <td className="mono-small">
                      {row.signal_meta_trade_lane ?? dash}
                    </td>
                    <td>{row.decision_action}</td>
                    <td>{row.decision_reason}</td>
                    <td>{row.signal_trade_action ?? dash}</td>
                    <td>
                      {row.signal_allowed_leverage == null
                        ? dash
                        : `${row.signal_allowed_leverage}x`}
                    </td>
                    <td>
                      {row.signal_recommended_leverage == null
                        ? row.leverage == null
                          ? dash
                          : `${row.leverage}x`
                        : `${row.signal_recommended_leverage}x`}
                    </td>
                    <td>
                      {row.signal_leverage_cap_reasons_json.length > 0 ? (
                        <pre className="json-mini">
                          {prettyJsonLine(row.signal_leverage_cap_reasons_json)}
                        </pre>
                      ) : (
                        dash
                      )}
                    </td>
                    <td>
                      {row.shadow_live_match_ok == null
                        ? dash
                        : String(row.shadow_live_match_ok)}
                    </td>
                    <td>
                      {row.live_mirror_eligible == null
                        ? dash
                        : String(row.live_mirror_eligible)}
                    </td>
                    <td>
                      {row.operator_release_exists
                        ? t("pages.broker.releaseReleased")
                        : t("pages.broker.releasePending")}
                    </td>
                    <td className="mono-small">
                      {row.risk_primary_reason ?? dash}
                    </td>
                    <td>
                      {Array.isArray(row.shadow_live_hard_violations) &&
                      row.shadow_live_hard_violations.length > 0 ? (
                        <pre className="json-mini">
                          {prettyJsonLine(row.shadow_live_hard_violations)}
                        </pre>
                      ) : (
                        dash
                      )}
                    </td>
                    <td>
                      <Link
                        href={consolePath(
                          `live-broker/forensic/${row.execution_id}`,
                        )}
                      >
                        {t("pages.broker.forensicLink")}
                      </Link>
                    </td>
                    <td>{row.created_ts ?? dash}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : decisionsResponse &&
          !sectionFetchFailed(t("pages.broker.sectionDecisions")) ? (
          !(decisionsResponse.empty_state && decisionsResponse.message) ? (
            <p className="muted degradation-inline" role="status">
              {t("pages.broker.tableEmptyOperational")}
            </p>
          ) : null
        ) : null}
      </div>

      <div className="panel">
        <h2>{t("pages.broker.sectionOrderActions")}</h2>
        {actionsResponse ? (
          <GatewayReadNotice payload={actionsResponse} t={t} />
        ) : (
          <p className="muted small degradation-inline" role="status">
            {t("pages.broker.sectionUnavailable")}
          </p>
        )}
        {orderActions.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("pages.broker.thAction")}</th>
                  <th>{t("pages.broker.thRequestPath")}</th>
                  <th>{t("pages.broker.thHttp")}</th>
                  <th>{t("pages.broker.thExchange")}</th>
                  <th>{t("pages.broker.thOrder")}</th>
                  <th>{t("pages.broker.thTime")}</th>
                </tr>
              </thead>
              <tbody>
                {orderActions.map((row) => (
                  <tr key={row.order_action_id}>
                    <td>{row.action}</td>
                    <td>{row.request_path}</td>
                    <td>{row.http_status ?? dash}</td>
                    <td>{row.exchange_msg ?? row.exchange_code ?? dash}</td>
                    <td>{row.internal_order_id}</td>
                    <td>{row.created_ts ?? dash}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : actionsResponse &&
          !sectionFetchFailed(t("pages.broker.sectionOrderActions")) ? (
          !(actionsResponse.empty_state && actionsResponse.message) ? (
            <p className="muted degradation-inline" role="status">
              {t("pages.broker.tableEmptyOperational")}
            </p>
          ) : null
        ) : null}
      </div>

      <div className="panel">
        <h2>{t("pages.broker.sectionFills")}</h2>
        {fillsResponse ? (
          <GatewayReadNotice payload={fillsResponse} t={t} />
        ) : (
          <p className="muted small degradation-inline" role="status">
            {t("pages.broker.sectionUnavailable")}
          </p>
        )}
        {fills.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("pages.broker.thSymbol")}</th>
                  <th>{t("pages.broker.thSide")}</th>
                  <th>{t("pages.broker.thPrice")}</th>
                  <th>{t("pages.broker.thSize")}</th>
                  <th>{t("pages.broker.thFee")}</th>
                  <th>{t("pages.broker.thMaker")}</th>
                  <th>{t("pages.broker.thTime")}</th>
                </tr>
              </thead>
              <tbody>
                {fills.map((row) => (
                  <tr key={row.exchange_trade_id}>
                    <td>{row.symbol}</td>
                    <td>{row.side}</td>
                    <td>{row.price ?? dash}</td>
                    <td>{row.size ?? dash}</td>
                    <td>
                      {row.fee
                        ? `${row.fee} ${row.fee_coin ?? ""}`.trim()
                        : dash}
                    </td>
                    <td>
                      {row.is_maker == null ? dash : String(row.is_maker)}
                    </td>
                    <td>{row.created_ts ?? dash}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : fillsResponse &&
          !sectionFetchFailed(t("pages.broker.sectionFills")) ? (
          !(fillsResponse.empty_state && fillsResponse.message) ? (
            <p className="muted degradation-inline" role="status">
              {t("pages.broker.tableEmptyOperational")}
            </p>
          ) : null
        ) : null}
      </div>

      <div className="panel">
        <h2>{t("pages.broker.sectionOrders")}</h2>
        {ordersResponse ? (
          <GatewayReadNotice payload={ordersResponse} t={t} />
        ) : (
          <p className="muted small degradation-inline" role="status">
            {t("pages.broker.sectionUnavailable")}
          </p>
        )}
        {orders.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("pages.broker.thSymbol")}</th>
                  <th>{t("pages.broker.thOrderStatus")}</th>
                  <th>{t("pages.broker.thLastAction")}</th>
                  <th>{t("pages.broker.thReduceOnly")}</th>
                  <th>{t("pages.broker.thClientOid")}</th>
                  <th>{t("pages.broker.thTime")}</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((row) => (
                  <tr key={row.internal_order_id}>
                    <td>{row.symbol}</td>
                    <td>{row.status}</td>
                    <td>{row.last_action}</td>
                    <td>{String(row.reduce_only)}</td>
                    <td>{row.client_oid}</td>
                    <td>{row.updated_ts ?? row.created_ts ?? dash}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : ordersResponse &&
          !sectionFetchFailed(t("pages.broker.sectionOrders")) ? (
          !(ordersResponse.empty_state && ordersResponse.message) ? (
            <p className="muted degradation-inline" role="status">
              {t("pages.broker.tableEmptyOperational")}
            </p>
          ) : null
        ) : null}
      </div>

      <div className="panel">
        <h2>{t("pages.broker.sectionKillEvents")}</h2>
        {listSectionNotice(eventsResponse)}
        {events.length ? (
          <div className="table-wrap">
            <table className="data-table data-table--dense">
              <thead>
                <tr>
                  <th>{t("pages.broker.thScope")}</th>
                  <th>{t("pages.broker.thKey")}</th>
                  <th>{t("pages.broker.thReason")}</th>
                  <th>{t("pages.broker.thSource")}</th>
                  <th>{t("pages.broker.thTime")}</th>
                </tr>
              </thead>
              <tbody>
                {events.slice(0, 20).map((row) => (
                  <tr key={row.kill_switch_event_id}>
                    <td>{row.scope}</td>
                    <td>{row.scope_key}</td>
                    <td>{row.reason}</td>
                    <td>{row.source}</td>
                    <td>{row.created_ts ?? dash}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : eventsResponse &&
          !sectionFetchFailed(t("pages.broker.sectionKillEvents")) ? (
          !(eventsResponse.empty_state && eventsResponse.message) ? (
            <p className="muted degradation-inline" role="status">
              {t("pages.broker.tableEmptyOperational")}
            </p>
          ) : null
        ) : null}
      </div>
    </>
  );
}
