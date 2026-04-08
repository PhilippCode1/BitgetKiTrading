import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { Header } from "@/components/layout/Header";
import { fetchCommerceCustomerHistory } from "@/lib/api";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function AccountHistoryPage() {
  const t = await getServerTranslator();
  let data: Record<string, unknown> | null = null;
  let err: string | null = null;
  try {
    data = await fetchCommerceCustomerHistory({
      ledger_limit: 50,
      audit_limit: 50,
    });
  } catch (e) {
    err = e instanceof Error ? e.message : t("account.history.loadErr");
  }
  const ledger =
    (data?.usage_ledger as Record<string, unknown>[] | undefined) ?? [];
  const audits =
    (data?.portal_audit as Record<string, unknown>[] | undefined) ?? [];

  return (
    <>
      <Header
        title={t("account.history.title")}
        subtitle={t("account.history.subtitle")}
      />
      {err ? (
        <PanelDataIssue err={err} diagnostic={false} t={t} />
      ) : (
        <>
          <div className="panel">
            <h2>{t("account.history.ledgerTitle")}</h2>
            {ledger.length === 0 ? (
              <p className="muted customer-empty-state">
                {t("account.history.emptyLedger")}
              </p>
            ) : (
              <div className="table-wrap">
                <table className="data-table data-table--dense">
                  <thead>
                    <tr>
                      <th>{t("account.history.thEvent")}</th>
                      <th>{t("account.history.thQty")}</th>
                      <th>{t("account.history.thAmount")}</th>
                      <th>{t("account.history.thTime")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ledger.map((row) => (
                      <tr key={String(row.ledger_id ?? row)}>
                        <td>{String(row.event_type ?? "—")}</td>
                        <td className="mono-small">
                          {String(row.quantity ?? "—")} {String(row.unit ?? "")}
                        </td>
                        <td>{String(row.line_total_list_usd ?? "—")}</td>
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
          <div className="panel">
            <h2>{t("account.history.auditTitle")}</h2>
            {audits.length === 0 ? (
              <p className="muted customer-empty-state">
                {t("account.history.emptyAudit")}
              </p>
            ) : (
              <div className="table-wrap">
                <table className="data-table data-table--dense">
                  <thead>
                    <tr>
                      <th>{t("account.history.thAction")}</th>
                      <th>{t("account.history.thActor")}</th>
                      <th>{t("account.history.thTime")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {audits.map((row) => (
                      <tr key={String(row.audit_id ?? row)}>
                        <td>{String(row.action ?? "—")}</td>
                        <td className="mono-small">
                          {String(row.actor ?? "—")}
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
