import Link from "next/link";

import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { ConsolePartialLoadNotice } from "@/components/console/ConsolePartialLoadNotice";
import { GatewayReadNotice } from "@/components/console/GatewayReadNotice";
import { Header } from "@/components/layout/Header";
import { LiveDataSituationBar } from "@/components/live-data/LiveDataSituationBar";
import {
  fetchLiveBrokerDecisions,
  fetchLiveBrokerFills,
  fetchLiveState,
  fetchPaperTradesRecent,
  fetchSystemHealthCached,
} from "@/lib/api";
import { buildLiveDataSurfaceModelFromShadowLivePage } from "@/lib/live-data-surface-model";
import { readConsoleChartPrefs } from "@/lib/chart-prefs-server";
import { consolePath } from "@/lib/console-paths";
import {
  diagnosticFromSearchParams,
  firstSearchParam,
  type ConsoleSearchParams,
} from "@/lib/console-params";
import { resolveConsoleChartSymbolTimeframe } from "@/lib/console-chart-context";
import { publicEnv } from "@/lib/env";
import { gatewayFetchErrorMessage } from "@/lib/gateway-fetch-errors";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import { getRequestLocale } from "@/lib/i18n/server";
import { prettyJsonLine } from "@/lib/live-broker-console";
import {
  buildDecisionBuckets,
  summarizePaperVsLiveOutcome,
} from "@/lib/operator-console";
import {
  labelsForLineageSegment,
  shadowLiveMatchCellAria,
  violationEntryCount,
} from "@/lib/shadow-live-console";
import type {
  LiveBrokerDecisionsResponse,
  LiveBrokerFillsResponse,
  LiveStateResponse,
  PaperTradesResponse,
  SystemHealthResponse,
} from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function ShadowLivePage({
  searchParams = {},
}: {
  searchParams?: ConsoleSearchParams | Promise<ConsoleSearchParams>;
}) {
  const sp = await Promise.resolve(searchParams);
  const diagnostic = diagnosticFromSearchParams(sp);
  const t = await getServerTranslator();
  const locale = await getRequestLocale();
  const dash = t("pages.shadowLive.emDash");

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

  const sectionErrors: string[] = [];

  const settled = await Promise.allSettled([
    fetchLiveBrokerDecisions(),
    fetchLiveBrokerFills(),
    fetchPaperTradesRecent({ symbol: sym, limit: 40 }),
    fetchLiveState({ symbol: sym, timeframe: tf, limit: 120 }),
    fetchSystemHealthCached(),
  ]);

  const [dRes, fRes, pRes, lRes, hRes] = settled;

  let decisionsRes: LiveBrokerDecisionsResponse | undefined;
  if (dRes.status === "fulfilled") decisionsRes = dRes.value;
  else
    sectionErrors.push(
      `${t("pages.shadowLive.sectionDecisions")}: ${gatewayFetchErrorMessage(dRes.reason)}`,
    );

  let fillsRes: LiveBrokerFillsResponse | undefined;
  if (fRes.status === "fulfilled") fillsRes = fRes.value;
  else
    sectionErrors.push(
      `${t("pages.shadowLive.sectionFills")}: ${gatewayFetchErrorMessage(fRes.reason)}`,
    );

  let paperRes: PaperTradesResponse | undefined;
  if (pRes.status === "fulfilled") paperRes = pRes.value;
  else
    sectionErrors.push(
      `${t("pages.shadowLive.sectionPaper")}: ${gatewayFetchErrorMessage(pRes.reason)}`,
    );

  let liveStateRes: LiveStateResponse | undefined;
  if (lRes.status === "fulfilled") liveStateRes = lRes.value;
  else
    sectionErrors.push(
      `${t("pages.shadowLive.sectionLiveState")}: ${gatewayFetchErrorMessage(lRes.reason)}`,
    );

  let healthRes: SystemHealthResponse | undefined;
  if (hRes.status === "fulfilled") healthRes = hRes.value;
  else
    sectionErrors.push(
      `${t("pages.shadowLive.sectionHealth")}: ${gatewayFetchErrorMessage(hRes.reason)}`,
    );

  const decisions = decisionsRes?.items ?? [];
  const fills = fillsRes?.items ?? [];
  const paperTrades = paperRes?.trades ?? [];

  const buckets = buildDecisionBuckets(decisions);
  const outcome = summarizePaperVsLiveOutcome({
    decisions,
    fills,
    paperTrades,
  });
  const divergences = buckets.divergenceRows.slice(0, 15);

  const allFailed = sectionErrors.length === settled.length;
  const pageError = allFailed ? sectionErrors.join(" · ") : null;

  const lineageRows = liveStateRes?.data_lineage ?? [];

  const shadowSituationModel = buildLiveDataSurfaceModelFromShadowLivePage({
    health: healthRes ?? null,
    live: liveStateRes ?? null,
    liveFetchFailed: lRes.status === "rejected",
    sectionErrorCount: sectionErrors.length,
  });

  return (
    <>
      <Header
        title={t("pages.shadowLive.title")}
        subtitle={t("pages.shadowLive.subtitle", {
          symbol: sym,
          timeframe: tf,
        })}
      />
      <LiveDataSituationBar model={shadowSituationModel} />
      <p className="muted small">
        {t("pages.shadowLive.contextLinks")}{" "}
        <Link href={consolePath("live-broker")}>
          {t("pages.shadowLive.linkJournal")}
        </Link>
        {" · "}
        <Link href={consolePath("ops")}>
          {t("pages.shadowLive.linkCockpit")}
        </Link>
        {" · "}
        <Link href={consolePath("paper")}>
          {t("pages.shadowLive.linkPaper")}
        </Link>
      </p>
      <PanelDataIssue err={pageError} diagnostic={diagnostic} t={t} />

      {!allFailed && sectionErrors.length > 0 ? (
        <ConsolePartialLoadNotice
          t={t}
          titleKey="pages.shadowLive.partialLoadTitle"
          bodyKey="pages.shadowLive.partialLoadBody"
          lines={sectionErrors}
          diagnostic={diagnostic}
        />
      ) : null}

      <div className="panel muted small" role="note">
        <h2 className="small" style={{ marginTop: 0 }}>
          {t("pages.shadowLive.provenanceTitle")}
        </h2>
        <ul className="news-list">
          <li>{t("pages.shadowLive.provenanceDecisions")}</li>
          <li>{t("pages.shadowLive.provenanceFills")}</li>
          <li>{t("pages.shadowLive.provenancePaper")}</li>
          <li>{t("pages.shadowLive.provenanceDivergence")}</li>
          <li>{t("pages.shadowLive.provenanceAssessments")}</li>
          <li>{t("pages.shadowLive.provenanceLineage")}</li>
        </ul>
      </div>

      <div className="panel">
        <h2>{t("pages.shadowLive.summaryTitle")}</h2>
        <p className="muted small">{t("pages.shadowLive.summaryFootnote")}</p>
        <ul className="news-list operator-metric-list">
          <li>
            {t("pages.shadowLive.mLiveCand")}{" "}
            <strong>{outcome.liveCandidates}</strong> /{" "}
            <strong>{outcome.releasedLive}</strong>
          </li>
          <li>
            {t("pages.shadowLive.mBlocked")}{" "}
            <strong>{outcome.blockedLive}</strong>
          </li>
          <li>
            {t("pages.shadowLive.mMirror")}{" "}
            <strong>{outcome.mirrorEligible}</strong>
          </li>
          <li>
            {t("pages.shadowLive.mDivRows")}{" "}
            <strong>{outcome.divergenceCount}</strong>
          </li>
          <li>
            {t("pages.shadowLive.mFills")} <strong>{outcome.liveFills}</strong>
          </li>
          <li>
            {t("pages.shadowLive.mPaperRows")}{" "}
            <strong>{outcome.paperTradeRowsLoaded}</strong> —{" "}
            {t("pages.shadowLive.mPaperClosed")}{" "}
            <strong>{outcome.paperClosedTrades}</strong> (
            {t("pages.shadowLive.mPaperWl")}:{" "}
            <strong>
              {outcome.paperWins}/{outcome.paperLosses}
            </strong>
            )
          </li>
        </ul>
      </div>

      <div className="panel">
        <h2>{t("pages.shadowLive.lineageTitle")}</h2>
        <p className="muted small">
          {t("pages.shadowLive.lineageLead", { symbol: sym, timeframe: tf })}
        </p>
        {liveStateRes ? (
          <GatewayReadNotice payload={liveStateRes} t={t} />
        ) : (
          <p className="muted small degradation-inline" role="status">
            {t("pages.shadowLive.lineageUnavailable")}
          </p>
        )}
        {lineageRows.length === 0 && liveStateRes ? (
          <p className="muted small" role="status">
            {t("pages.shadowLive.lineageEmpty")}
          </p>
        ) : lineageRows.length > 0 ? (
          <div className="table-wrap">
            <table className="data-table data-table--dense">
              <thead>
                <tr>
                  <th>{t("pages.shadowLive.lineageColSegment")}</th>
                  <th>{t("pages.shadowLive.lineageColData")}</th>
                  <th>{t("pages.shadowLive.lineageColProducer")}</th>
                  <th>{t("pages.shadowLive.lineageColGap")}</th>
                  <th>{t("pages.shadowLive.lineageColNext")}</th>
                </tr>
              </thead>
              <tbody>
                {lineageRows.map((seg) => {
                  const L = labelsForLineageSegment(seg, locale);
                  return (
                    <tr key={seg.segment_id}>
                      <td className="mono-small">{L.label}</td>
                      <td>
                        {seg.has_data
                          ? t("pages.shadowLive.lineageYes")
                          : t("pages.shadowLive.lineageNo")}
                      </td>
                      <td className="muted small">{L.producer}</td>
                      <td className="muted small">
                        {seg.has_data ? dash : L.whyEmpty}
                      </td>
                      <td className="muted small">{L.nextStep}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>

      <div className="panel">
        <h2>{t("pages.shadowLive.divergenceTitle")}</h2>
        <p className="muted small">{t("pages.shadowLive.divergenceLead")}</p>
        {decisionsRes ? (
          <GatewayReadNotice payload={decisionsRes} t={t} />
        ) : null}
        {divergences.length === 0 ? (
          <p className="muted degradation-inline">
            {t("pages.shadowLive.divergenceEmpty")}
          </p>
        ) : (
          <div className="table-wrap">
            <table className="data-table data-table--dense">
              <thead>
                <tr>
                  <th>{t("approvals.thSymbol")}</th>
                  <th>{t("pages.shadowLive.thRuntime")}</th>
                  <th>{t("pages.shadowLive.thShadowLive")}</th>
                  <th>{t("pages.shadowLive.thMirror")}</th>
                  <th>{t("pages.shadowLive.thHard")}</th>
                  <th>{t("pages.shadowLive.thSoft")}</th>
                  <th>{t("pages.shadowLive.thRisk")}</th>
                  <th>{t("pages.shadowLive.thForensic")}</th>
                </tr>
              </thead>
              <tbody>
                {divergences.map((d) => {
                  const matchAria = shadowLiveMatchCellAria(
                    d.shadow_live_match_ok,
                  );
                  const matchKey =
                    `pages.shadowLive.matchCell.${matchAria}` as const;
                  const hardN = violationEntryCount(
                    d.shadow_live_hard_violations,
                  );
                  const softN = violationEntryCount(
                    d.shadow_live_soft_violations,
                  );
                  return (
                    <tr key={d.execution_id}>
                      <td>{d.symbol}</td>
                      <td className="mono-small">
                        {d.effective_runtime_mode ?? dash}
                      </td>
                      <td>{t(matchKey)}</td>
                      <td>
                        {d.live_mirror_eligible == null
                          ? dash
                          : String(d.live_mirror_eligible)}
                      </td>
                      <td
                        className="mono-small"
                        title={
                          hardN
                            ? prettyJsonLine(d.shadow_live_hard_violations)
                            : undefined
                        }
                      >
                        {hardN || dash}
                      </td>
                      <td
                        className="mono-small"
                        title={
                          softN
                            ? prettyJsonLine(d.shadow_live_soft_violations)
                            : undefined
                        }
                      >
                        {softN || dash}
                      </td>
                      <td className="mono-small">
                        {d.risk_primary_reason ?? dash}
                      </td>
                      <td>
                        <Link
                          href={`${consolePath("live-broker")}/forensic/${d.execution_id}`}
                        >
                          {t("pages.shadowLive.linkTimeline")}
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
