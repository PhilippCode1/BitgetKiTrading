import Link from "next/link";

import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { EmptyStateHelp } from "@/components/help/EmptyStateHelp";
import { Header } from "@/components/layout/Header";
import { fetchCommerceUsageLedger, fetchCommerceUsageSummary } from "@/lib/api";
import { consolePath } from "@/lib/console-paths";
import {
  diagnosticFromSearchParams,
  type ConsoleSearchParams,
} from "@/lib/console-params";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function UsagePage({
  searchParams = {},
}: {
  searchParams?: ConsoleSearchParams | Promise<ConsoleSearchParams>;
}) {
  const sp = await Promise.resolve(searchParams);
  const diagnostic = diagnosticFromSearchParams(sp);
  const t = await getServerTranslator();
  let summary: Awaited<ReturnType<typeof fetchCommerceUsageSummary>> | null =
    null;
  let ledger: Awaited<ReturnType<typeof fetchCommerceUsageLedger>> | null =
    null;
  let err: string | null = null;
  try {
    const [s, l] = await Promise.all([
      fetchCommerceUsageSummary(),
      fetchCommerceUsageLedger({ limit: 30 }),
    ]);
    summary = s;
    ledger = l;
  } catch (e) {
    err = e instanceof Error ? e.message : t("usage.errApi");
  }

  const month =
    summary?.month_utc && typeof summary.month_utc === "object"
      ? (summary.month_utc as Record<string, unknown>)
      : null;

  return (
    <>
      <Header title={t("usage.title")} subtitle={t("usage.subtitle")} />
      <p className="muted small">{t("usage.dataHint")}</p>
      <p className="muted small">
        <Link href={consolePath("ops")}>{t("usage.backCockpit")}</Link>
      </p>
      {err ? (
        err.includes("404") || /\b404\b/.test(err) ? (
          <div
            className="console-fetch-notice console-fetch-notice--soft"
            role="status"
          >
            <p className="console-fetch-notice__title">
              {t("usage.notConfiguredTitle")}
            </p>
            <p className="console-fetch-notice__body muted small">
              {t("usage.err404")}
            </p>
            <p className="console-fetch-notice__refresh muted small">
              {t("ui.refreshHint")}
            </p>
          </div>
        ) : (
          <PanelDataIssue err={err} diagnostic={diagnostic} t={t} />
        )
      ) : null}
      {!err && !summary ? (
        <EmptyStateHelp
          titleKey="help.usage.emptyTitle"
          bodyKey="help.usage.emptyBody"
          stepKeys={[
            "help.usage.step1",
            "help.usage.step2",
            "help.usage.step3",
          ]}
        />
      ) : null}
      {summary ? (
        <div className="panel">
          <h2>{t("usage.summary")}</h2>
          <ul className="news-list operator-metric-list">
            <li>
              {t("usage.tenant")}:{" "}
              <strong className="mono-small">
                {String(summary.tenant_id ?? "—")}
              </strong>
            </li>
            {month ? (
              <>
                <li>
                  {t("usage.ledgerMonth")}:{" "}
                  <strong>{String(month.ledger_total_list_usd ?? "—")}</strong>
                </li>
                <li>
                  {t("usage.tokensMonth")}:{" "}
                  <strong>{String(month.llm_tokens_used ?? "—")}</strong>
                </li>
                <li>
                  {t("usage.tokenCap")}:{" "}
                  <strong>
                    {month.llm_monthly_token_cap == null
                      ? "—"
                      : String(month.llm_monthly_token_cap)}
                  </strong>
                </li>
                <li>
                  {t("usage.budgetCap")}:{" "}
                  <strong>
                    {month.budget_cap_usd_month == null
                      ? "—"
                      : String(month.budget_cap_usd_month)}
                  </strong>
                </li>
                <li>
                  {t("usage.capExceeded")}:{" "}
                  <strong>{String(month.cap_exceeded ?? "—")}</strong> —{" "}
                  {t("usage.budgetExceededLabel")}:{" "}
                  <strong>{String(month.budget_exceeded ?? "—")}</strong>
                </li>
              </>
            ) : null}
          </ul>
        </div>
      ) : null}
      {summary && !err && !ledger?.items?.length ? (
        <p className="muted small" role="status">
          {t("help.usage.ledgerHint")}
        </p>
      ) : null}
      {ledger?.items?.length ? (
        <div className="panel">
          <h2>{t("usage.ledgerRows")}</h2>
          <div className="table-wrap">
            <table className="data-table data-table--dense">
              <thead>
                <tr>
                  <th>{t("usage.thTime")}</th>
                  <th>{t("usage.thEvent")}</th>
                  <th>{t("usage.thQty")}</th>
                  <th>{t("usage.thUnit")}</th>
                  <th>{t("usage.thUsd")}</th>
                </tr>
              </thead>
              <tbody>
                {ledger.items.map((row) => {
                  const r = row as Record<string, unknown>;
                  return (
                    <tr key={String(r.ledger_id ?? r.id ?? JSON.stringify(r))}>
                      <td className="mono-small">
                        {String(r.created_at ?? r.ts ?? "—")}
                      </td>
                      <td>{String(r.event_type ?? "—")}</td>
                      <td>{String(r.quantity ?? "—")}</td>
                      <td>{String(r.unit ?? "—")}</td>
                      <td>{String(r.line_total_list_usd ?? "—")}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </>
  );
}
