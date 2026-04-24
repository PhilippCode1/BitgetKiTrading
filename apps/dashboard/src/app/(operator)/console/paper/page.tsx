import { ExecutionPathSummaryList } from "@/components/console/ExecutionPathSummaryList";
import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { ConsolePartialLoadNotice } from "@/components/console/ConsolePartialLoadNotice";
import { ProductLineChart } from "@/components/chart/ProductLineChart";
import { Header } from "@/components/layout/Header";
import { PaperOpenPositionsClient } from "@/components/paper/PaperOpenPositionsClient";
import { TradesTable } from "@/components/tables/TradesTable";
import {
  fetchPaperJournalRecent,
  fetchPaperLedgerRecent,
  fetchPaperMetricsSummary,
  fetchPaperOpen,
  fetchPaperTradesRecent,
  fetchSystemHealthCached,
} from "@/lib/api";
import { resolveConsoleChartSymbolTimeframe } from "@/lib/console-chart-context";
import {
  diagnosticFromSearchParams,
  firstSearchParam,
} from "@/lib/console-params";
import { executionPathFromSystemHealth } from "@/lib/execution-path-view-model";
import { formatNum, formatTsMs } from "@/lib/format";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import { readConsoleChartPrefs } from "@/lib/chart-prefs-server";
import { publicEnv } from "@/lib/env";
import {
  derivePaperClosedTradeStats,
  paperSectionFetchErrorMessage,
  previewPaperJournalDetail,
} from "@/lib/paper-console";
import {
  emptyPaperJournalResponse,
  emptyPaperLedgerResponse,
  emptyPaperMetricsResponse,
  emptyPaperOpenResponse,
  emptyPaperTradesResponse,
} from "@/lib/paper-response-defaults";
import type {
  PaperJournalEvent,
  PaperJournalResponse,
  PaperLedgerResponse,
  PaperMetricsResponse,
  PaperOpenResponse,
  PaperTradesResponse,
  SystemHealthResponse,
} from "@/lib/types";

import { PaperReadNotice } from "./paper-read-notice";

export const dynamic = "force-dynamic";

type SP = Record<string, string | string[] | undefined>;

export default async function PaperPage({
  searchParams,
}: {
  searchParams: SP | Promise<SP>;
}) {
  const t = await getServerTranslator();
  const sp = await Promise.resolve(searchParams);
  const diagnostic = diagnosticFromSearchParams(sp);
  const chartPrefs = await readConsoleChartPrefs();
  const { chartSymbol: sym } = resolveConsoleChartSymbolTimeframe({
    urlSymbol: firstSearchParam(sp, "symbol"),
    urlTimeframe: firstSearchParam(sp, "timeframe"),
    persistedSymbol: chartPrefs.symbol,
    persistedTimeframe: chartPrefs.timeframe,
    defaultSymbol: publicEnv.defaultSymbol,
    defaultTimeframe: publicEnv.defaultTimeframe,
  });

  let positions: PaperOpenResponse = emptyPaperOpenResponse();
  let trades: PaperTradesResponse = emptyPaperTradesResponse(40);
  let metrics: PaperMetricsResponse = emptyPaperMetricsResponse();
  let journal: PaperJournalResponse = emptyPaperJournalResponse(35);
  let ledger: PaperLedgerResponse = emptyPaperLedgerResponse(40);
  let systemHealth: SystemHealthResponse | null = null;

  const sectionErrors: string[] = [];

  const settled = await Promise.allSettled([
    fetchPaperOpen(sym),
    fetchPaperTradesRecent({ symbol: sym, limit: 40 }),
    fetchPaperMetricsSummary(),
    fetchPaperJournalRecent({ symbol: sym, limit: 35 }),
    fetchPaperLedgerRecent({ limit: 40 }),
    fetchSystemHealthCached(),
  ]);

  const [pRes, tRes, mRes, jRes, lRes, hRes] = settled;
  if (pRes.status === "fulfilled") positions = pRes.value;
  else
    sectionErrors.push(
      `${t("pages.paper.sectionPositions")}: ${paperSectionFetchErrorMessage(pRes.reason)}`,
    );
  if (tRes.status === "fulfilled") trades = tRes.value;
  else
    sectionErrors.push(
      `${t("pages.paper.sectionTrades")}: ${paperSectionFetchErrorMessage(tRes.reason)}`,
    );
  if (mRes.status === "fulfilled") metrics = mRes.value;
  else
    sectionErrors.push(
      `${t("pages.paper.sectionMetrics")}: ${paperSectionFetchErrorMessage(mRes.reason)}`,
    );
  if (jRes.status === "fulfilled") journal = jRes.value;
  else
    sectionErrors.push(
      `${t("pages.paper.sectionJournal")}: ${paperSectionFetchErrorMessage(jRes.reason)}`,
    );
  if (lRes.status === "fulfilled") ledger = lRes.value;
  else
    sectionErrors.push(
      `${t("pages.paper.sectionLedger")}: ${paperSectionFetchErrorMessage(lRes.reason)}`,
    );
  if (hRes.status === "fulfilled") systemHealth = hRes.value;
  else
    sectionErrors.push(
      `${t("pages.paper.sectionSystemHealth")}: ${paperSectionFetchErrorMessage(hRes.reason)}`,
    );

  const allFailed = sectionErrors.length === settled.length;
  const pageError = allFailed ? sectionErrors.join(" · ") : null;

  const ledgerFromApi = lRes.status === "fulfilled";
  const ledgerRows = ledgerFromApi
    ? ledger.entries
    : (metrics.account_ledger_recent ?? []);

  const { closedCount, wins, losses, pnlSum, winRatePercent } =
    derivePaperClosedTradeStats(trades.trades);

  const equityEmptyMessage =
    metrics.account == null && metrics.equity_curve.length === 0
      ? t("pages.paper.equityCurveNoAccount")
      : t("ui.chart.emptyGeneric");

  return (
    <>
      <Header
        title={t("pages.paper.title")}
        subtitle={t("pages.paper.subtitle", { symbol: sym })}
        helpBriefKey="help.paperPage.brief"
        helpDetailKey="help.paperPage.detail"
      />
      <p className="muted small readable" style={{ marginTop: 4 }}>
        {t("pages.paper.leadParagraph")}
      </p>
      <PanelDataIssue err={pageError} diagnostic={diagnostic} t={t} />
      {!allFailed && sectionErrors.length > 0 ? (
        <ConsolePartialLoadNotice
          t={t}
          titleKey="pages.paper.partialLoadTitle"
          bodyKey="pages.paper.partialLoadBody"
          lines={sectionErrors}
          diagnostic={diagnostic}
        />
      ) : null}
      {systemHealth ? (
        <div className="panel">
          <h2>{t("pages.paper.executionPanelTitle")}</h2>
          <ExecutionPathSummaryList
            model={executionPathFromSystemHealth(systemHealth)}
            t={t}
          />
        </div>
      ) : null}
      <div
        className="panel readable"
        role="region"
        aria-label={t("pages.paper.trustPanelTitle")}
      >
        <h2 style={{ marginTop: 0 }}>{t("pages.paper.trustPanelTitle")}</h2>
        <p className="muted small" style={{ marginBottom: 0 }}>
          {t("pages.paper.trustPanelBody")}
        </p>
      </div>
      <details className="panel muted small">
        <summary className="operator-details-summary">
          {t("pages.paper.adminDetailsSummary")}
        </summary>
        <p style={{ marginTop: 8 }}>
          <strong>{t("pages.paper.adminHintTitle")}</strong>
        </p>
        <p style={{ marginTop: 6 }}>{t("pages.paper.adminHintBody")}</p>
      </details>
      <div className="grid-2">
        <div className="panel">
          <h2>{t("pages.paper.openPositionsTitle")}</h2>
          <PaperReadNotice payload={positions} t={t} />
          <PaperOpenPositionsClient symbol={sym} initial={positions} />
        </div>
        <div className="panel">
          <h2>{t("pages.paper.accountCostsTitle")}</h2>
          <PaperReadNotice payload={metrics} t={t} />
          {metrics.account ? (
            <ul className="news-list">
              <li>
                {t("pages.paper.equityLabel")}:{" "}
                {formatNum(metrics.account.equity, 4)} USDT
              </li>
              <li>
                {t("pages.paper.initialLabel")}:{" "}
                {formatNum(metrics.account.initial_equity, 4)} USDT
              </li>
            </ul>
          ) : (
            <p className="muted">{t("pages.paper.noAccount")}</p>
          )}
          <h3 className="muted small" style={{ marginTop: 12 }}>
            {t("pages.paper.feesLedgerLabel")}
          </h3>
          <ul className="news-list">
            <li>{formatNum(metrics.fees_total_usdt, 4)} USDT</li>
          </ul>
          <h3 className="muted small" style={{ marginTop: 12 }}>
            {t("pages.paper.fundingLedgerLabel")}
          </h3>
          <ul className="news-list">
            <li>{formatNum(metrics.funding_total_usdt, 4)} USDT</li>
          </ul>
        </div>
      </div>
      <div className="panel">
        <h2>{t("pages.paper.performanceTitle")}</h2>
        <PaperReadNotice payload={trades} t={t} />
        <ul className="news-list operator-metric-list">
          <li>
            {t("pages.paper.perfClosed")}: <strong>{closedCount}</strong>
          </li>
          <li>
            {t("pages.paper.perfWins")}: <strong>{wins}</strong> /{" "}
            {t("pages.paper.perfLosses")}: <strong>{losses}</strong>
          </li>
          <li>
            {t("pages.paper.perfPnlSum")}:{" "}
            <strong>{formatNum(pnlSum, 4)}</strong> USDT
          </li>
          <li>
            {t("pages.paper.perfWinRate")}:{" "}
            <strong>
              {winRatePercent != null
                ? `${winRatePercent}%`
                : t("tables.paperOpen.emDash")}
            </strong>
          </li>
        </ul>
      </div>
      <div className="panel">
        <h2>{t("pages.paper.equityCurveTitle")}</h2>
        <p className="muted small">{t("pages.paper.equityCurveExplain")}</p>
        <ProductLineChart
          series={metrics.equity_curve.map((p) => ({
            time_s: p.time_s,
            value: p.equity,
          }))}
          emptyMessage={equityEmptyMessage}
          ariaLabel={t("pages.paper.equityChartAria")}
        />
      </div>
      <div className="panel">
        <h2>{t("pages.paper.ledgerTitle")}</h2>
        <p className="muted small">{t("pages.paper.ledgerLead")}</p>
        {ledgerFromApi ? (
          <PaperReadNotice payload={ledger} t={t} />
        ) : (
          <p className="muted small degradation-inline" role="status">
            {t("pages.paper.ledgerFallbackFromMetrics")}
          </p>
        )}
        {ledgerRows.length === 0 ? (
          <p className="muted degradation-inline">
            {t("pages.paper.ledgerEmpty")}
          </p>
        ) : (
          <div className="table-wrap">
            <table className="data-table data-table--dense">
              <thead>
                <tr>
                  <th>{t("pages.paper.ledgerColTime")}</th>
                  <th>{t("pages.paper.ledgerColReason")}</th>
                  <th>{t("pages.paper.ledgerColAmount")}</th>
                  <th>{t("pages.paper.ledgerColBalance")}</th>
                </tr>
              </thead>
              <tbody>
                {ledgerRows.map((row) => (
                  <tr key={row.entry_id}>
                    <td>{formatTsMs(row.ts_ms)}</td>
                    <td className="mono-small">{row.reason}</td>
                    <td>{row.amount_usdt}</td>
                    <td>{row.balance_after}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <div className="panel">
        <h2>{t("pages.paper.journalTitle")}</h2>
        <p className="muted small">{t("pages.paper.journalLead")}</p>
        <PaperReadNotice payload={journal} t={t} />
        {journal.events.length === 0 ? (
          <p className="muted degradation-inline">
            {t("pages.paper.journalEmpty")}
          </p>
        ) : (
          <div className="table-wrap">
            <table className="data-table data-table--dense">
              <thead>
                <tr>
                  <th>{t("pages.paper.ledgerColTime")}</th>
                  <th>{t("pages.paper.journalColSource")}</th>
                  <th>{t("pages.paper.journalColSymbol")}</th>
                  <th>{t("pages.paper.journalColDetail")}</th>
                </tr>
              </thead>
              <tbody>
                {journal.events.map((ev: PaperJournalEvent) => (
                  <tr key={`${ev.source}-${ev.ref_id}`}>
                    <td>{formatTsMs(ev.ts_ms)}</td>
                    <td className="mono-small">{ev.source}</td>
                    <td>{ev.symbol ?? t("tables.paperOpen.emDash")}</td>
                    <td className="mono-small">
                      {previewPaperJournalDetail(ev.detail)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <div className="panel">
        <h2>{t("pages.paper.recentTradesTitle")}</h2>
        <PaperReadNotice payload={trades} t={t} />
        <TradesTable trades={trades.trades} />
      </div>
    </>
  );
}
