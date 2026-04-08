import Link from "next/link";

import { Header } from "@/components/layout/Header";
import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { fetchCommerceAdminProfitFeeStatements } from "@/lib/api";
import { CONSOLE_BASE } from "@/lib/console-paths";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import { canAccessAdminViaServer } from "@/lib/operator-session";

export const dynamic = "force-dynamic";

export default async function AdminProfitFeesPage() {
  const t = await getServerTranslator();
  const ok = await canAccessAdminViaServer();
  if (!ok) {
    return (
      <>
        <Header
          title={t("pages.adminHub.profitTitle")}
          subtitle={t("pages.adminPage.subtitleRead")}
        />
        <div className="panel" role="alert">
          <p className="msg-err degradation-inline" style={{ margin: 0 }}>
            {t("pages.adminPage.deniedBody")}
          </p>
        </div>
      </>
    );
  }

  let err: string | null = null;
  let stmts: Record<string, unknown>[] = [];
  try {
    const pack = await fetchCommerceAdminProfitFeeStatements({ limit: 80 });
    const list = pack.statements as Record<string, unknown>[] | undefined;
    stmts = Array.isArray(list) ? list : [];
  } catch (e) {
    err = e instanceof Error ? e.message : t("errors.fallbackMessage");
  }

  return (
    <>
      <Header
        title={t("pages.adminHub.profitTitle")}
        subtitle={t("pages.adminHub.profitSubtitle")}
      />
      <p className="muted small admin-hub__back">
        <Link href={`${CONSOLE_BASE}/admin`}>
          {t("pages.adminHub.backCockpit")}
        </Link>
      </p>
      <p className="muted small">{t("pages.adminHub.profitLead")}</p>
      <PanelDataIssue err={err} diagnostic={true} t={t} />
      {!err && stmts.length > 0 ? (
        <div className="panel">
          <div className="table-wrap">
            <table className="data-table data-table--dense">
              <thead>
                <tr>
                  <th>{t("pages.adminHub.th.statementStatus")}</th>
                  <th>{t("pages.adminHub.th.tenantRaw")}</th>
                  <th>{t("pages.adminHub.th.period")}</th>
                  <th>{t("pages.adminHub.th.updated")}</th>
                  <th>{t("pages.adminHub.th.action")}</th>
                </tr>
              </thead>
              <tbody>
                {stmts.map((row) => {
                  const tid = String(row.tenant_id ?? "");
                  return (
                    <tr key={String(row.statement_id ?? row)}>
                      <td>{String(row.status ?? "—")}</td>
                      <td className="mono-small">{tid}</td>
                      <td className="mono-small">
                        {String(row.period_start ?? "—")} →{" "}
                        {String(row.period_end ?? "—")}
                      </td>
                      <td className="mono-small">
                        {String(row.updated_ts ?? "—")}
                      </td>
                      <td>
                        <Link
                          href={`${CONSOLE_BASE}/admin/customers/${encodeURIComponent(tid)}`}
                        >
                          {t("pages.adminHub.open")}
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : !err ? (
        <p className="muted">{t("pages.adminHub.emptyProfit")}</p>
      ) : null}
    </>
  );
}
