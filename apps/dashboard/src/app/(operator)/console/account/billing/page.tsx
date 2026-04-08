import { Header } from "@/components/layout/Header";
import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import {
  fetchCommerceBillingInvoices,
  fetchCommerceBillingLedger,
  fetchCommerceBillingPlans,
  fetchCommerceBillingSubscription,
} from "@/lib/api";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function AccountBillingPage() {
  const t = await getServerTranslator();
  let err: string | null = null;
  let plans: Record<string, unknown>[] = [];
  let subscription: Record<string, unknown> | null = null;
  let invoices: Record<string, unknown>[] = [];
  let ledger: Record<string, unknown>[] = [];
  try {
    const [p, s, inv, led] = await Promise.all([
      fetchCommerceBillingPlans(),
      fetchCommerceBillingSubscription(),
      fetchCommerceBillingInvoices(),
      fetchCommerceBillingLedger(),
    ]);
    plans = (p.plans as Record<string, unknown>[] | undefined) ?? [];
    subscription =
      (s.subscription as Record<string, unknown> | null | undefined) ?? null;
    invoices = (inv.invoices as Record<string, unknown>[] | undefined) ?? [];
    ledger = (led.entries as Record<string, unknown>[] | undefined) ?? [];
  } catch (e) {
    err = e instanceof Error ? e.message : t("account.billing.loadErr");
  }

  return (
    <>
      <Header
        title={t("account.billing.title")}
        subtitle={t("account.billing.subtitle")}
        helpBriefKey="help.usage.brief"
        helpDetailKey="help.usage.detail"
      />
      {err ? (
        <div className="panel">
          <PanelDataIssue err={err} diagnostic={false} t={t} />
          <p className="muted small">{t("account.billing.migrationHint")}</p>
        </div>
      ) : (
        <>
          <div className="panel">
            <h3 className="account-section-title">
              {t("account.billing.plansTitle")}
            </h3>
            {plans.length === 0 ? (
              <p className="muted small">
                {t("account.billing.migrationHint")}
              </p>
            ) : (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{t("account.billing.thPlan")}</th>
                      <th>{t("account.billing.thInterval")}</th>
                      <th>{t("account.billing.thNet")}</th>
                      <th>{t("account.billing.thVat")}</th>
                      <th>{t("account.billing.thGross")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {plans.map((row) => (
                      <tr key={String(row.plan_code)}>
                        <td>{String(row.display_name_de ?? row.plan_code)}</td>
                        <td className="mono-small">
                          {String(row.billing_interval)}
                        </td>
                        <td className="mono-small">{String(row.net_cents)}</td>
                        <td className="mono-small">{String(row.vat_cents)}</td>
                        <td className="mono-small">
                          {String(row.gross_cents)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="panel">
            <h3 className="account-section-title">
              {t("account.billing.subscriptionTitle")}
            </h3>
            {!subscription ? (
              <p className="muted">{t("account.billing.noSubscription")}</p>
            ) : (
              <ul className="news-list operator-metric-list">
                <li>
                  {t("account.billing.status")}:{" "}
                  <strong>{String(subscription.status)}</strong>
                </li>
                <li>
                  {t("account.billing.dunning")}:{" "}
                  <strong>{String(subscription.dunning_stage ?? "—")}</strong>
                </li>
                <li>
                  Plan:{" "}
                  <strong>
                    {String(
                      subscription.display_name_de ?? subscription.plan_code,
                    )}{" "}
                    ({String(subscription.plan_code)})
                  </strong>
                </li>
                <li className="mono-small">
                  {t("account.billing.period")}:{" "}
                  {String(subscription.current_period_start ?? "—")} →{" "}
                  {String(subscription.current_period_end ?? "—")}
                </li>
              </ul>
            )}
          </div>

          <div className="panel">
            <h3 className="account-section-title">
              {t("account.billing.invoicesTitle")}
            </h3>
            {invoices.length === 0 ? (
              <p className="muted">{t("account.billing.emptyInvoices")}</p>
            ) : (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{t("account.billing.thInvoiceNo")}</th>
                      <th>{t("account.billing.thInvKind")}</th>
                      <th>{t("account.billing.thInvStatus")}</th>
                      <th>{t("account.billing.thInvGross")}</th>
                      <th>{t("account.billing.thTime")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoices.map((row) => (
                      <tr key={String(row.invoice_id)}>
                        <td className="mono-small">
                          {String(row.invoice_number)}
                        </td>
                        <td>{String(row.invoice_kind)}</td>
                        <td>{String(row.status)}</td>
                        <td className="mono-small">
                          {String(row.total_gross_cents)}
                        </td>
                        <td className="mono-small">
                          {String(row.issued_ts ?? row.created_ts ?? "—")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="panel">
            <h3 className="account-section-title">
              {t("account.billing.ledgerTitle")}
            </h3>
            {ledger.length === 0 ? (
              <p className="muted">{t("account.billing.emptyLedger")}</p>
            ) : (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{t("account.billing.thEvent")}</th>
                      <th>{t("account.billing.thLedgerGross")}</th>
                      <th>{t("account.billing.thTime")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ledger.map((row) => (
                      <tr key={String(row.ledger_entry_id)}>
                        <td>{String(row.event_type)}</td>
                        <td className="mono-small">
                          {row.amount_gross_cents != null
                            ? String(row.amount_gross_cents)
                            : "—"}
                        </td>
                        <td className="mono-small">
                          {String(row.created_ts ?? "—")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </>
  );
}
