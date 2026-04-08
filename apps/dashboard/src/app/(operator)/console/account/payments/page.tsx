import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { Header } from "@/components/layout/Header";
import { fetchCommerceCustomerPayments } from "@/lib/api";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function AccountPaymentsPage() {
  const t = await getServerTranslator();
  let data: Record<string, unknown> | null = null;
  let err: string | null = null;
  try {
    data = await fetchCommerceCustomerPayments({ limit: 80 });
  } catch (e) {
    err = e instanceof Error ? e.message : t("account.payments.loadErr");
  }
  const items = (data?.items as Record<string, unknown>[] | undefined) ?? [];

  return (
    <>
      <Header
        title={t("account.payments.title")}
        subtitle={t("account.payments.subtitle")}
      />
      {err ? (
        <PanelDataIssue err={err} diagnostic={false} t={t} />
      ) : items.length === 0 ? (
        <p className="muted">{t("account.payments.empty")}</p>
      ) : (
        <div className="table-wrap">
          <table className="data-table data-table--dense">
            <thead>
              <tr>
                <th>{t("account.payments.thAmount")}</th>
                <th>{t("account.payments.thStatus")}</th>
                <th>{t("account.payments.thProvider")}</th>
                <th>{t("account.payments.thRef")}</th>
                <th>{t("account.payments.thTime")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={String(row.payment_id ?? row)}>
                  <td>{String(row.amount_list_usd ?? "—")}</td>
                  <td>{String(row.status ?? "—")}</td>
                  <td>{String(row.provider ?? "—")}</td>
                  <td className="mono-small">
                    {String(row.provider_reference_masked ?? "—")}
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
    </>
  );
}
