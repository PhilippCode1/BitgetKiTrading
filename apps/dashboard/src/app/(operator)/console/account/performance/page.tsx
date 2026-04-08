import Link from "next/link";

import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { Header } from "@/components/layout/Header";
import { fetchCommerceCustomerPerformance } from "@/lib/api";
import { consolePath } from "@/lib/console-paths";
import { getRequestLocale } from "@/lib/i18n/server";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import type { CommerceCustomerPerformanceResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

function num(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number" && Number.isFinite(v)) return String(v);
  if (typeof v === "string") return v;
  return String(v);
}

export default async function AccountPerformancePage() {
  const t = await getServerTranslator();
  const locale = await getRequestLocale();
  let data: CommerceCustomerPerformanceResponse | null = null;
  let err: string | null = null;
  try {
    data = await fetchCommerceCustomerPerformance({ trades_limit: 160 });
  } catch (e) {
    err = e instanceof Error ? e.message : t("account.performance.loadErr");
  }

  const explain =
    locale === "de"
      ? (data?.explainability.de ?? t("account.performance.explainFallback"))
      : (data?.explainability.en ?? t("account.performance.explainFallback"));

  const demo = (data?.demo ?? {}) as Record<string, unknown>;
  const scopeNotice =
    locale === "de"
      ? (demo.scope_notice as { de?: string } | undefined)?.de
      : (demo.scope_notice as { en?: string } | undefined)?.en;
  const periods = (demo.periods ?? {}) as Record<
    string,
    Record<string, unknown>
  >;
  const dd = (demo.drawdown ?? {}) as Record<string, unknown>;
  const streaks = (demo.streaks ?? {}) as Record<string, unknown>;
  const openPos =
    (demo.open_positions as Record<string, unknown>[] | undefined) ?? [];
  const closed =
    (demo.closed_trades_recent as Record<string, unknown>[] | undefined) ?? [];
  const liveFees = (data?.live_and_fees ?? {}) as Record<string, unknown>;
  const hwm = liveFees.high_water_mark_cents as
    | { paper?: number; live?: number }
    | null
    | undefined;

  return (
    <>
      <Header
        title={t("account.performance.title")}
        subtitle={t("account.performance.subtitle")}
      />
      {err ? (
        <PanelDataIssue err={err} diagnostic={false} t={t} />
      ) : (
        <>
          <div className="panel">
            <h2>{t("account.performance.explainHeading")}</h2>
            <p className="muted" style={{ marginTop: 0 }}>
              {explain}
            </p>
            <p className="muted small">
              <Link href={consolePath("signals")}>
                {t("account.performance.linkSignals")}
              </Link>
              {" · "}
              <Link href={consolePath("paper")}>
                {t("account.performance.linkPaperConsole")}
              </Link>
              {" · "}
              <Link href={consolePath("live-broker")}>
                {t("account.performance.linkLiveConsole")}
              </Link>
            </p>
          </div>

          <div className="panel">
            <h2>{t("account.performance.demoHeading")}</h2>
            {scopeNotice ? (
              <p className="msg-ok" role="note" style={{ marginTop: 0 }}>
                {scopeNotice}
              </p>
            ) : null}
            <div className="btn-row" style={{ marginTop: "0.75rem" }}>
              <a
                className="btn-secondary"
                href="/api/dashboard/commerce/customer/performance/export?format=csv&trades_limit=250"
              >
                {t("account.performance.exportCsv")}
              </a>
              <a
                className="btn-secondary"
                href="/api/dashboard/commerce/customer/performance/report-pdf?trades_limit=160"
              >
                {t("account.performance.exportPdf")}
              </a>
            </div>
            <h3 style={{ fontSize: "1rem", marginTop: "1.25rem" }}>
              {t("account.performance.kpisHeading")}
            </h3>
            <ul className="news-list">
              <li>
                {t("account.performance.openCount")}:{" "}
                <strong>{num(demo.open_positions_count)}</strong> —{" "}
                {t("account.performance.unrealizedSum")}:{" "}
                <strong>{num(demo.unrealized_pnl_usdt_sum)} USDT</strong>
              </li>
              <li>
                {t("account.performance.feesPaper")}:{" "}
                <strong>{num(demo.fees_total_usdt)} USDT</strong> —{" "}
                {t("account.performance.funding")}:{" "}
                <strong>{num(demo.funding_total_usdt)} USDT</strong>
              </li>
              <li>
                {t("account.performance.maxDrawdown")}:{" "}
                <strong>{num(dd.max_drawdown_pct)} %</strong> (
                {t("account.performance.vsPeak")})
              </li>
              <li>
                {t("account.performance.streaks")}:{" "}
                <strong>
                  {num(streaks.max_consecutive_wins)} /{" "}
                  {num(streaks.max_consecutive_losses)}
                </strong>{" "}
                ({t("account.performance.winLossStreaks")})
              </li>
            </ul>
            <h3 style={{ fontSize: "1rem", marginTop: "1rem" }}>
              {t("account.performance.periodsHeading")}
            </h3>
            <div className="table-wrap">
              <table className="data-table data-table--dense">
                <thead>
                  <tr>
                    <th>{t("account.performance.thPeriod")}</th>
                    <th>{t("account.performance.thTrades")}</th>
                    <th>{t("account.performance.thWinRate")}</th>
                    <th>{t("account.performance.thSumPnl")}</th>
                    <th>{t("account.performance.thProfitFactor")}</th>
                  </tr>
                </thead>
                <tbody>
                  {(["last_7d", "last_30d", "all_in_window"] as const).map(
                    (key) => {
                      const p = periods[key] ?? {};
                      const labelKey =
                        key === "last_7d"
                          ? "account.performance.period7d"
                          : key === "last_30d"
                            ? "account.performance.period30d"
                            : "account.performance.periodAll";
                      return (
                        <tr key={key}>
                          <td>{t(labelKey)}</td>
                          <td>{num(p.trade_count)}</td>
                          <td>
                            {p.win_rate != null
                              ? `${num(Number(p.win_rate) * 100)} %`
                              : "—"}
                          </td>
                          <td>{num(p.sum_pnl_net_usdt)}</td>
                          <td>{num(p.profit_factor)}</td>
                        </tr>
                      );
                    },
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="panel">
            <h2>{t("account.performance.openPositionsHeading")}</h2>
            {openPos.length === 0 ? (
              <p className="muted customer-empty-state">
                {t("account.performance.emptyOpen")}
              </p>
            ) : (
              <div className="table-wrap">
                <table className="data-table data-table--dense">
                  <thead>
                    <tr>
                      <th>{t("account.performance.thSymbol")}</th>
                      <th>{t("account.performance.thSide")}</th>
                      <th>{t("account.performance.thQty")}</th>
                      <th>{t("account.performance.thEntry")}</th>
                      <th>uPnL</th>
                    </tr>
                  </thead>
                  <tbody>
                    {openPos.map((row) => (
                      <tr key={String(row.position_id)}>
                        <td>{String(row.symbol ?? "—")}</td>
                        <td>{String(row.side ?? "—")}</td>
                        <td className="mono-small">
                          {String(row.qty_base ?? "—")}
                        </td>
                        <td className="mono-small">
                          {String(row.entry_price_avg ?? "—")}
                        </td>
                        <td className="mono-small">
                          {num(row.unrealized_pnl_usdt)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="panel">
            <h2>{t("account.performance.closedHeading")}</h2>
            {closed.length === 0 ? (
              <p className="muted customer-empty-state">
                {t("account.performance.emptyClosed")}
              </p>
            ) : (
              <div className="table-wrap">
                <table className="data-table data-table--dense">
                  <thead>
                    <tr>
                      <th>{t("account.performance.thSymbol")}</th>
                      <th>{t("account.performance.thSide")}</th>
                      <th>{t("account.performance.thClosed")}</th>
                      <th>PnL</th>
                      <th>{t("account.performance.thFees")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {closed.slice(0, 40).map((row) => (
                      <tr key={String(row.position_id)}>
                        <td>{String(row.symbol ?? "—")}</td>
                        <td>{String(row.side ?? "—")}</td>
                        <td className="mono-small">
                          {String(row.closed_ts_ms ?? "—")}
                        </td>
                        <td className="mono-small">{num(row.pnl_net_usdt)}</td>
                        <td className="mono-small">
                          {num(row.fees_total_usdt)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="panel">
            <h2>{t("account.performance.liveHeading")}</h2>
            {liveFees.module_disabled ? (
              <p className="muted">{t("account.performance.liveModuleOff")}</p>
            ) : (
              <>
                <p className="muted small" style={{ marginTop: 0 }}>
                  {t("account.performance.liveHint")}
                </p>
                <ul className="news-list">
                  <li>
                    {t("account.performance.hwmPaper")}:{" "}
                    <strong>{num(hwm?.paper)}</strong> —{" "}
                    {t("account.performance.hwmLive")}:{" "}
                    <strong>{num(hwm?.live)}</strong>
                  </li>
                  <li>
                    {t("account.performance.statementsRecent")}:{" "}
                    <strong>
                      {Array.isArray(liveFees.recent_statements)
                        ? liveFees.recent_statements.length
                        : 0}
                    </strong>
                  </li>
                </ul>
              </>
            )}
          </div>
        </>
      )}
    </>
  );
}
