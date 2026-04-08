import Link from "next/link";

import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { Header } from "@/components/layout/Header";
import { fetchCommerceCustomerBalance } from "@/lib/api";
import { consolePath } from "@/lib/console-paths";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function AccountBalancePage() {
  const t = await getServerTranslator();
  let data: Record<string, unknown> | null = null;
  let err: string | null = null;
  try {
    data = await fetchCommerceCustomerBalance();
  } catch (e) {
    err = e instanceof Error ? e.message : t("account.balance.loadErr");
  }
  const wallet = data?.wallet as Record<string, unknown> | undefined;
  const usage = data?.usage_month_utc as Record<string, unknown> | undefined;
  const billing = data?.billing as Record<string, unknown> | undefined;
  const bstatus = billing?.status as Record<string, unknown> | undefined;
  const accruals =
    (billing?.daily_accruals_recent as Record<string, unknown>[] | undefined) ??
    [];
  const balerts =
    (billing?.balance_alerts_recent as Record<string, unknown>[] | undefined) ??
    [];

  return (
    <>
      <Header
        title={t("account.balance.title")}
        subtitle={t("account.balance.subtitle")}
        helpBriefKey="help.usage.brief"
        helpDetailKey="help.usage.detail"
      />
      {err ? (
        <PanelDataIssue err={err} diagnostic={false} t={t} />
      ) : (
        <div className="panel">
          <ul className="news-list operator-metric-list">
            <li>
              {t("account.home.prepaid")}:{" "}
              <strong className="customer-metric-value">
                {wallet?.prepaid_balance_list_usd != null
                  ? String(wallet.prepaid_balance_list_usd)
                  : "—"}{" "}
                {t("account.home.currencyRef")}
              </strong>
            </li>
            <li>
              {t("account.home.monthUsageLabel")}:{" "}
              <strong className="customer-metric-value">
                {usage?.ledger_total_list_usd != null
                  ? String(usage.ledger_total_list_usd)
                  : "—"}{" "}
                {t("account.home.currencyRef")}
              </strong>
            </li>
            <li>
              {t("account.home.llmUsageLabel")}:{" "}
              <strong className="customer-metric-value">
                {usage?.llm_tokens_used != null
                  ? String(usage.llm_tokens_used)
                  : "—"}
              </strong>
            </li>
          </ul>
          {bstatus ? (
            <>
              <h3 className="account-section-title">
                {t("account.balance.billingTitle")}
              </h3>
              <ul className="news-list operator-metric-list">
                <li>
                  {t("account.balance.dailyFee")}:{" "}
                  <strong className="customer-metric-value">
                    {bstatus.daily_api_fee_list_usd != null
                      ? String(bstatus.daily_api_fee_list_usd)
                      : "—"}{" "}
                    {t("account.home.currencyRef")}
                  </strong>
                </li>
                <li>
                  {t("account.balance.minNewTrade")}:{" "}
                  <strong className="customer-metric-value">
                    {bstatus.min_balance_new_trade_list_usd != null
                      ? String(bstatus.min_balance_new_trade_list_usd)
                      : "—"}{" "}
                    {t("account.home.currencyRef")}
                  </strong>
                </li>
                <li>
                  {t("account.balance.balanceLevel")}:{" "}
                  <strong>
                    {bstatus.balance_level != null
                      ? String(bstatus.balance_level)
                      : "—"}
                  </strong>
                </li>
                <li>
                  {t("account.balance.allowsNewTrades")}:{" "}
                  <strong>
                    {bstatus.allows_new_trades === true
                      ? t("account.deposit.on")
                      : t("account.deposit.off")}
                  </strong>
                </li>
              </ul>
              <p className="muted small">{t("account.balance.billingNote")}</p>
            </>
          ) : null}
          {accruals.length > 0 ? (
            <>
              <h3 className="account-section-title">
                {t("account.balance.accrualsTitle")}
              </h3>
              <div className="table-wrap">
                <table className="data-table data-table--dense">
                  <thead>
                    <tr>
                      <th>{t("account.balance.thDate")}</th>
                      <th>{t("account.balance.thCharged")}</th>
                      <th>{t("account.balance.thAfter")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {accruals.map((row) => (
                      <tr key={String(row.accrual_id ?? row)}>
                        <td className="mono-small">
                          {String(row.accrual_date ?? "—")}
                        </td>
                        <td className="mono-small">
                          {String(row.amount_charged_list_usd ?? "—")}
                        </td>
                        <td className="mono-small">
                          {String(row.balance_after_list_usd ?? "—")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : null}
          {balerts.length > 0 ? (
            <>
              <h3 className="account-section-title">
                {t("account.balance.alertsTitle")}
              </h3>
              <div className="table-wrap">
                <table className="data-table data-table--dense">
                  <thead>
                    <tr>
                      <th>{t("account.balance.thLevel")}</th>
                      <th>{t("account.balance.thBalance")}</th>
                      <th>{t("account.balance.thTime")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {balerts.map((row) => (
                      <tr key={String(row.alert_id ?? row)}>
                        <td>{String(row.alert_level ?? "—")}</td>
                        <td className="mono-small">
                          {String(row.balance_list_usd ?? "—")}
                        </td>
                        <td className="mono-small">
                          {String(row.created_ts ?? "—")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : null}
          <p className="muted small" style={{ marginTop: 16 }}>
            {t("account.balance.nextLinksLead")}{" "}
            <Link href={consolePath("account/deposit")}>
              {t("account.nav.deposit")}
            </Link>
            {" · "}
            <Link href={consolePath("account/usage")}>
              {t("account.nav.usage")}
            </Link>
            {" · "}
            <Link href={consolePath("account")}>
              {t("account.nav.overview")}
            </Link>
          </p>
        </div>
      )}
    </>
  );
}
