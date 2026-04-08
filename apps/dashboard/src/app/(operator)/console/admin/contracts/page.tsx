import Link from "next/link";

import { Header } from "@/components/layout/Header";
import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { fetchCommerceAdminContractReviewQueue } from "@/lib/api";
import { CONSOLE_BASE } from "@/lib/console-paths";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import { canAccessAdminViaServer } from "@/lib/operator-session";

export const dynamic = "force-dynamic";

export default async function AdminContractsPage() {
  const t = await getServerTranslator();
  const ok = await canAccessAdminViaServer();
  if (!ok) {
    return (
      <>
        <Header
          title={t("pages.adminHub.contractsTitle")}
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
  let items: Record<string, unknown>[] = [];
  try {
    const pack = await fetchCommerceAdminContractReviewQueue();
    const list = pack.items as Record<string, unknown>[] | undefined;
    items = Array.isArray(list) ? list : [];
  } catch (e) {
    err = e instanceof Error ? e.message : t("errors.fallbackMessage");
  }

  return (
    <>
      <Header
        title={t("pages.adminHub.contractsTitle")}
        subtitle={t("pages.adminHub.contractsSubtitle")}
      />
      <p className="muted small admin-hub__back">
        <Link href={`${CONSOLE_BASE}/admin`}>
          {t("pages.adminHub.backCockpit")}
        </Link>
      </p>
      <p className="muted small">{t("pages.adminHub.contractsLead")}</p>
      <PanelDataIssue err={err} diagnostic={true} t={t} />
      {!err && items.length > 0 ? (
        <div className="panel">
          <div className="table-wrap">
            <table className="data-table data-table--dense">
              <thead>
                <tr>
                  <th>{t("pages.adminHub.th.queueStatus")}</th>
                  <th>{t("pages.adminHub.th.tenantRaw")}</th>
                  <th>{t("pages.adminHub.th.template")}</th>
                  <th>{t("pages.adminHub.th.contractStatus")}</th>
                  <th>{t("pages.adminHub.th.created")}</th>
                  <th>{t("pages.adminHub.th.action")}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => {
                  const tid = String(row.tenant_id ?? "");
                  return (
                    <tr key={String(row.queue_id ?? row.contract_id)}>
                      <td>{String(row.queue_status ?? "—")}</td>
                      <td className="mono-small">{tid}</td>
                      <td>
                        {String(row.template_key ?? "—")} v
                        {String(row.template_version ?? "—")}
                      </td>
                      <td>{String(row.contract_status ?? "—")}</td>
                      <td className="mono-small">
                        {String(row.created_ts ?? "—")}
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
        <p className="muted">{t("pages.adminHub.emptyContracts")}</p>
      ) : null}
    </>
  );
}
