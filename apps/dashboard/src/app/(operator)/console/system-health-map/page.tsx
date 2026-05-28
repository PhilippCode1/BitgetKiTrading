import { Header } from "@/components/layout/Header";
import {
  fetchLiveBrokerRuntime,
  fetchLiveState,
  fetchMonitorAlertsOpen,
  fetchSystemHealthBestEffort,
} from "@/lib/api";
import { buildHealthMapViewModel } from "@/lib/health-map-view-model";
import { buildSystemDiagnosticsViewModel } from "@/lib/system-diagnostics-view-model";
import { publicEnv } from "@/lib/env";
import {
  healthMapBlockerReasons,
  localizeHealthMapComponent,
} from "@/lib/health-map-locale";
import {
  localizeDiagnosticsEmptyLine,
  localizeDiagnosticsOverallStatus,
  localizeDataSourceName,
  localizeDiagnosticsSummary,
  localizeStaleCheckDetail,
  localizeStaleCheckLabel,
  localizeWireStatus,
} from "@/lib/system-diagnostics-locale";
import { getRequestLocale } from "@/lib/i18n/server";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function SystemHealthMapPage() {
  const locale = await getRequestLocale();
  const t = await getServerTranslator();
  const [healthRes, runtimeRes, liveRes, alertsRes] = await Promise.allSettled([
    fetchSystemHealthBestEffort(),
    fetchLiveBrokerRuntime(),
    fetchLiveState({
      symbol: publicEnv.defaultSymbol,
      timeframe: publicEnv.defaultTimeframe,
      limit: 200,
    }),
    fetchMonitorAlertsOpen(),
  ]);

  const health =
    healthRes.status === "fulfilled" ? healthRes.value.health : null;
  const runtime =
    runtimeRes.status === "fulfilled" ? runtimeRes.value.item : null;
  const liveState = liveRes.status === "fulfilled" ? liveRes.value : null;
  const openAlerts =
    alertsRes.status === "fulfilled" ? alertsRes.value.items : [];
  const model = buildHealthMapViewModel({ health, runtime });
  const blockerReasons = healthMapBlockerReasons(model, locale);
  const diagnostics = buildSystemDiagnosticsViewModel({
    health,
    runtime,
    liveState,
    openAlerts,
    healthEndpointWired: healthRes.status === "fulfilled",
  });
  const healthEndpointMissing = healthRes.status !== "fulfilled";

  return (
    <>
      <Header
        title={t("console.systemHealthMapPage.title")}
        subtitle={t("console.systemHealthMapPage.subtitle")}
      />

      <div className="panel">
        <h2>{t("console.systemHealthMapPage.overallTitle")}</h2>
        <p>
          {t("console.systemHealthMapPage.overallStatus")}:{" "}
          <strong>
            {localizeDiagnosticsOverallStatus(diagnostics.overallStatus, t)}
          </strong>
        </p>
        <p className="muted small">
          {localizeDiagnosticsSummary(diagnostics, locale, t).join(" · ")}
        </p>
        <p>
          {t("console.systemHealthMapPage.liveTrading")}:{" "}
          <strong>
            {model.live_blockiert
              ? t("console.systemHealthMapPage.liveBlocked")
              : t("console.systemHealthMapPage.liveNotBlocked")}
          </strong>
        </p>
        {blockerReasons.length > 0 ? (
          <>
            <p className="muted small">
              {t("console.systemHealthMapPage.blockerReasons")}:
            </p>
            <ul className="muted small">
              {blockerReasons.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          </>
        ) : null}
      </div>

      <div className="panel">
        <h2>{t("console.systemHealthMapPage.systemStatusTitle")}</h2>
        <ul className="news-list">
          <li>
            {t("console.systemHealthMapPage.diagDbRedis")}{" "}
            <strong>{localizeWireStatus(diagnostics.dbStatus, t)}</strong> /{" "}
            <strong>{localizeWireStatus(diagnostics.redisStatus, t)}</strong>
          </li>
          <li>
            {t("console.systemHealthMapPage.diagBitget")}{" "}
            <strong>
              {localizeWireStatus(diagnostics.bitgetPublicStatus, t)}
            </strong>{" "}
            /{" "}
            <strong>
              {localizeWireStatus(diagnostics.bitgetPrivateStatus, t)}
            </strong>
          </li>
          <li>
            {t("console.systemHealthMapPage.diagLlmNews")}{" "}
            <strong>{localizeWireStatus(diagnostics.llmStatus, t)}</strong> /{" "}
            <strong>{localizeWireStatus(diagnostics.newsStatus, t)}</strong>
          </li>
          <li>
            {t("console.systemHealthMapPage.diagAlertMonitor")}{" "}
            <strong>{localizeWireStatus(diagnostics.alertStatus, t)}</strong>
          </li>
        </ul>
      </div>

      <div className="panel">
        <h2>{t("console.systemHealthMapPage.componentsTitle")}</h2>
        <p className="muted small">
          {t("console.systemHealthMapPage.componentsLead")}
        </p>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("console.systemHealthMapPage.colComponent")}</th>
                <th>{t("console.systemHealthMapPage.colStatus")}</th>
                <th>{t("console.systemHealthMapPage.colFreshness")}</th>
                <th>{t("console.systemHealthMapPage.colBlocksLive")}</th>
                <th>{t("console.systemHealthMapPage.colLiveImpact")}</th>
                <th>{t("console.systemHealthMapPage.colErrorReason")}</th>
                <th>{t("console.systemHealthMapPage.colNextStep")}</th>
              </tr>
            </thead>
            <tbody>
              {model.komponenten.map((row) => {
                const loc = localizeHealthMapComponent(row, locale);
                return (
                  <tr key={row.komponente}>
                    <td>{loc.komponente}</td>
                    <td>{loc.status}</td>
                    <td>{loc.freshness_status}</td>
                    <td>
                      {loc.blockiert_live
                        ? t("console.systemHealthMapPage.blocksLiveYes")
                        : t("console.systemHealthMapPage.blocksLiveNo")}
                    </td>
                    <td>{loc.liveImpact}</td>
                    <td>{loc.errorReason || "—"}</td>
                    <td>{loc.nextStep || "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <h2>{t("console.systemHealthMapPage.dataSourcesTitle")}</h2>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("console.systemHealthMapPage.colService")}</th>
                <th>{t("console.systemHealthMapPage.colStatus")}</th>
              </tr>
            </thead>
            <tbody>
              {diagnostics.dataSources.map((source) => (
                <tr key={source.name}>
                  <td>{localizeDataSourceName(source.name, t)}</td>
                  <td>
                    <span
                      className={
                        source.status === "ok"
                          ? "status-pill status-pill--ok"
                          : "status-pill status-pill--danger"
                      }
                    >
                      {source.status === "ok"
                        ? t("console.systemHealthMapPage.ok")
                        : t("console.systemHealthMapPage.stale")}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <h2>{t("console.systemHealthMapPage.staleTitle")}</h2>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("console.systemHealthMapPage.colCheck")}</th>
                <th>{t("console.systemHealthMapPage.colStatus")}</th>
                <th>{t("console.systemHealthMapPage.colDetail")}</th>
              </tr>
            </thead>
            <tbody>
              {diagnostics.staleChecks.map((s) => (
                <tr key={s.key}>
                  <td>{localizeStaleCheckLabel(s, t)}</td>
                  <td>
                    <span
                      className={
                        s.stale
                          ? "status-pill status-pill--danger"
                          : "status-pill status-pill--ok"
                      }
                    >
                      {s.stale
                        ? t("console.systemHealthMapPage.stale")
                        : t("console.systemHealthMapPage.ok")}
                    </span>
                  </td>
                  <td>{localizeStaleCheckDetail(s, t)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <h2>{t("console.systemHealthMapPage.servicesTitle")}</h2>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("console.systemHealthMapPage.colService")}</th>
                <th>{t("console.systemHealthMapPage.colStatus")}</th>
                <th>{t("console.systemHealthMapPage.colDetail")}</th>
              </tr>
            </thead>
            <tbody>
              {diagnostics.serviceStatus.length === 0 ? (
                <tr>
                  <td colSpan={3} className="muted">
                    {t("console.systemHealthMapPage.noServiceData")}
                  </td>
                </tr>
              ) : (
                diagnostics.serviceStatus.map((s) => (
                  <tr key={s.name}>
                    <td>{s.name}</td>
                    <td>{s.status}</td>
                    <td>{localizeDiagnosticsEmptyLine(s.detail, t)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <h2>{t("console.systemHealthMapPage.errorsTitle")}</h2>
        <ul className="news-list">
          {diagnostics.latestCriticalErrors.map((line) => (
            <li key={line}>{localizeDiagnosticsEmptyLine(line, t)}</li>
          ))}
        </ul>
        <h3>{t("console.systemHealthMapPage.successTitle")}</h3>
        <ul className="news-list">
          {diagnostics.latestSuccessfulChecks.map((line) => (
            <li key={line}>{localizeDiagnosticsEmptyLine(line, t)}</li>
          ))}
        </ul>
      </div>

      <div className="panel">
        <h2>{t("console.systemHealthMapPage.actionsTitle")}</h2>
        <p className="muted small">
          {t("console.systemHealthMapPage.actionsLead")}
        </p>
        <button
          type="button"
          className="public-btn ghost"
          disabled
          title={t("console.systemHealthMapPage.refreshTitle")}
        >
          {t("console.systemHealthMapPage.safeRefresh")}
        </button>
        <button
          type="button"
          className="public-btn ghost"
          disabled={healthEndpointMissing}
          title={
            healthEndpointMissing
              ? t("console.systemHealthMapPage.healthMissingTitle")
              : t("console.systemHealthMapPage.safeCheck")
          }
          style={{ marginLeft: 8 }}
        >
          {t("console.systemHealthMapPage.safeCheck")}
        </button>
        {healthEndpointMissing ? (
          <p className="muted small">
            {t("console.systemHealthMapPage.healthMissingBody")}
          </p>
        ) : null}
      </div>
    </>
  );
}
