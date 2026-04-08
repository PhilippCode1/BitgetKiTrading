import Link from "next/link";

import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { Header } from "@/components/layout/Header";
import { consolePath } from "@/lib/console-paths";
import {
  diagnosticFromSearchParams,
  type ConsoleSearchParams,
} from "@/lib/console-params";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import {
  fetchBacktestRuns,
  fetchLearningDrift,
  fetchLearningDriftOnlineState,
  fetchLearningModelOpsReport,
  fetchLearningPatternsTop,
  fetchLearningRecommendations,
  fetchLearningStrategyMetrics,
  fetchModelRegistryV2,
} from "@/lib/api";
import type {
  BacktestsRunsListResponse,
  LearningDriftOnlineStateResponse,
  LearningDriftRecentResponse,
  LearningModelRegistryV2ListResponse,
  LearningPatternsTopResponse,
  LearningRecommendationsListResponse,
  LearningStrategyMetricsListResponse,
} from "@/lib/types";
import { formatTsMs } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function LearningPage({
  searchParams,
}: {
  searchParams: ConsoleSearchParams | Promise<ConsoleSearchParams>;
}) {
  const sp = await Promise.resolve(searchParams);
  const diagnostic = diagnosticFromSearchParams(sp);
  const t = await getServerTranslator();
  const emptyEnvelope = {
    status: "ok" as const,
    message: null,
    empty_state: true,
    degradation_reason: null,
    next_step: null,
  };
  let metrics: LearningStrategyMetricsListResponse = {
    ...emptyEnvelope,
    items: [],
    limit: 0,
  };
  let patterns: LearningPatternsTopResponse = {
    ...emptyEnvelope,
    items: [],
    limit: 10,
  };
  let recs: LearningRecommendationsListResponse = {
    ...emptyEnvelope,
    items: [],
    limit: 0,
  };
  let drift: LearningDriftRecentResponse = {
    ...emptyEnvelope,
    items: [],
    limit: 50,
  };
  let backtests: BacktestsRunsListResponse = {
    ...emptyEnvelope,
    items: [],
    limit: 10,
  };
  let registryV2: LearningModelRegistryV2ListResponse = {
    ...emptyEnvelope,
    items: [],
    limit: 0,
  };
  let onlineDrift: LearningDriftOnlineStateResponse = {
    ...emptyEnvelope,
    item: null,
  };
  let modelOpsReport: Record<string, unknown> | null = null;
  let modelOpsError: string | null = null;
  let error: string | null = null;
  try {
    [metrics, patterns, recs, drift, backtests, registryV2, onlineDrift] =
      await Promise.all([
        fetchLearningStrategyMetrics(),
        fetchLearningPatternsTop(),
        fetchLearningRecommendations(),
        fetchLearningDrift(),
        fetchBacktestRuns(),
        fetchModelRegistryV2(),
        fetchLearningDriftOnlineState(),
      ]);
  } catch (e) {
    error = e instanceof Error ? e.message : t("errors.fallbackMessage");
  }
  try {
    modelOpsReport = await fetchLearningModelOpsReport({ slice_hours: 168 });
  } catch (e) {
    modelOpsError =
      e instanceof Error ? e.message : t("pages.learning.modelOpsErrFallback");
  }

  return (
    <>
      <Header
        title={t("pages.learning.title")}
        subtitle={t("pages.learning.subtitle")}
        helpBriefKey="help.drift.brief"
        helpDetailKey="help.drift.detail"
      />
      <p className="muted small">
        {t("console.quickLinksLead")}{" "}
        <Link href={consolePath("strategies")}>
          {t("console.nav.strategies")}
        </Link>
        {" · "}
        <Link href={consolePath("health")}>{t("console.nav.health")}</Link>
        {" · "}
        <Link href={consolePath("no-trade")}>{t("console.nav.no_trade")}</Link>
        {" · "}
        <Link href={consolePath("ops")}>{t("console.nav.ops")}</Link>
      </p>
      <PanelDataIssue err={error} diagnostic={diagnostic} t={t} />
      <div className="panel">
        <h2>{t("pages.learning.onlineDriftTitle")}</h2>
        <p className="muted">{t("pages.learning.onlineDriftLead")}</p>
        {onlineDrift.status === "degraded" && onlineDrift.message ? (
          <div
            className="console-fetch-notice console-fetch-notice--soft"
            role="status"
          >
            <p className="console-fetch-notice__title">
              {t("pages.learning.driftSourceLimitedTitle")}
            </p>
            <p className="console-fetch-notice__body muted small">
              {onlineDrift.message}
            </p>
            <p className="console-fetch-notice__refresh muted small">
              {t("ui.refreshHint")}
            </p>
          </div>
        ) : null}
        {onlineDrift.item ? (
          <ul className="flat-list">
            <li>
              <strong>effective_action:</strong>{" "}
              {onlineDrift.item.effective_action}
            </li>
            <li>
              <strong>computed_at:</strong>{" "}
              {onlineDrift.item.computed_at ?? "—"}
            </li>
            <li>
              <strong>lookback_minutes:</strong>{" "}
              {onlineDrift.item.lookback_minutes ?? "—"}
            </li>
          </ul>
        ) : onlineDrift.status !== "degraded" ? (
          <p className="muted">
            {onlineDrift.message?.trim()
              ? onlineDrift.message
              : t("pages.learning.noDriftState")}
          </p>
        ) : null}
      </div>
      <div className="panel">
        <h2>{t("pages.learning.registryTitle")}</h2>
        <p className="muted">{t("pages.learning.registryLead")}</p>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("pages.learning.thModel")}</th>
                <th>{t("pages.learning.thRole")}</th>
                <th>{t("pages.learning.thScope")}</th>
                <th>{t("pages.learning.thRun")}</th>
                <th>{t("pages.learning.thVersion")}</th>
                <th>{t("pages.learning.thCalRegistry")}</th>
                <th>{t("pages.learning.thMethodRun")}</th>
                <th>{t("pages.learning.thPromoted")}</th>
                <th>{t("pages.learning.thActivated")}</th>
              </tr>
            </thead>
            <tbody>
              {registryV2.items.length === 0 ? (
                <tr>
                  <td colSpan={9}>{t("pages.learning.registryEmpty")}</td>
                </tr>
              ) : (
                registryV2.items.map((row) => (
                  <tr
                    key={`${row.model_name}-${row.role}-${row.scope_type ?? "global"}-${row.scope_key ?? ""}`}
                  >
                    <td>{row.model_name}</td>
                    <td>{row.role}</td>
                    <td>
                      {row.scope_type ?? "global"}
                      {row.scope_key ? ` / ${row.scope_key}` : ""}
                    </td>
                    <td title={row.run_id}>{row.run_id.slice(0, 8)}…</td>
                    <td>{row.version ?? "—"}</td>
                    <td>{row.calibration_status}</td>
                    <td>{row.calibration_method ?? "—"}</td>
                    <td>
                      {row.promoted_bool
                        ? t("pages.learning.yes")
                        : t("pages.learning.no")}
                    </td>
                    <td>{row.activated_ts ?? "—"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
      <div className="panel">
        <h2>{t("pages.learning.modelOpsTitle")}</h2>
        <p className="muted">{t("pages.learning.modelOpsLead")}</p>
        <PanelDataIssue err={modelOpsError} diagnostic={diagnostic} t={t} />
        {modelOpsReport ? (
          <pre
            className="muted"
            style={{
              fontSize: 12,
              overflow: "auto",
              maxHeight: 320,
              marginTop: 8,
            }}
          >
            {JSON.stringify(modelOpsReport, null, 2)}
          </pre>
        ) : !modelOpsError ? (
          <p className="muted">{t("pages.learning.noData")}</p>
        ) : null}
      </div>
      <div className="grid-2">
        <div className="panel">
          <h2>{t("pages.learning.errorPatternsTitle")}</h2>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("pages.learning.thPattern")}</th>
                  <th>{t("pages.learning.thWindow")}</th>
                  <th>{t("pages.learning.thCount")}</th>
                </tr>
              </thead>
              <tbody>
                {patterns.items.map((p) => (
                  <tr key={`${p.window}-${p.pattern_key}`}>
                    <td>{p.pattern_key}</td>
                    <td>{p.window}</td>
                    <td>{p.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="panel">
          <h2>{t("pages.learning.recommendationsTitle")}</h2>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("pages.learning.thType")}</th>
                  <th>{t("pages.learning.thStatus")}</th>
                  <th>{t("pages.learning.thTime")}</th>
                </tr>
              </thead>
              <tbody>
                {recs.items.map((r) => (
                  <tr key={r.rec_id}>
                    <td>{r.type}</td>
                    <td>{r.status}</td>
                    <td>{r.created_ts}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <div className="panel">
        <h2>{t("pages.learning.driftEventsTitle")}</h2>
        <ul className="news-list">
          {drift.items.map((d) => (
            <li key={d.drift_id}>
              <strong>{d.metric_name}</strong> ({d.severity}) — {d.detected_ts}
            </li>
          ))}
        </ul>
      </div>
      <div className="panel">
        <h2>{t("pages.learning.strategyMetricsTitle")}</h2>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("pages.learning.thStrategy")}</th>
                <th>{t("pages.learning.thWindow")}</th>
                <th>{t("pages.learning.thUpdated")}</th>
              </tr>
            </thead>
            <tbody>
              {metrics.items.map((m) => (
                <tr key={`${m.strategy_id}-${m.window}`}>
                  <td>{m.strategy_name}</td>
                  <td>{m.window}</td>
                  <td>{m.updated_ts}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <details className="panel">
        <summary className="operator-details-summary">
          {t("pages.learning.backtestSummary")}
        </summary>
        <div className="table-wrap" style={{ marginTop: 12 }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("pages.learning.thRun")}</th>
                <th>{t("pages.learning.thSymbol")}</th>
                <th>{t("pages.learning.thStatus")}</th>
                <th>{t("pages.learning.thCv")}</th>
                <th>{t("pages.learning.thCreated")}</th>
              </tr>
            </thead>
            <tbody>
              {backtests.items.map((b) => (
                <tr key={b.run_id}>
                  <td>{b.run_id.slice(0, 8)}…</td>
                  <td>{b.symbol}</td>
                  <td>{b.status}</td>
                  <td>{b.cv_method}</td>
                  <td>
                    {(() => {
                      const t = b.created_ts ? Date.parse(b.created_ts) : NaN;
                      return Number.isFinite(t) ? formatTsMs(t) : "—";
                    })()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  );
}
