import Link from "next/link";

import { Header } from "@/components/layout/Header";
import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import {
  fetchAdminConsoleOverview,
  fetchCommerceAdminSubscriptions,
} from "@/lib/api";
import { CONSOLE_BASE } from "@/lib/console-paths";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import { canAccessAdminViaServer } from "@/lib/operator-session";
import type { AdminConsoleOverviewResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

type LifecycleRecent = NonNullable<
  AdminConsoleOverviewResponse["lifecycle"]
>["recent"];

export default async function AdminCustomersPage() {
  const t = await getServerTranslator();
  const ok = await canAccessAdminViaServer();
  if (!ok) {
    return (
      <>
        <Header
          title={t("pages.adminHub.customersTitle")}
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

  let overviewErr: string | null = null;
  let subsErr: string | null = null;
  let recent: LifecycleRecent = [];
  let statusCounts: { lifecycle_status: string; count: number }[] = [];
  try {
    const o = await fetchAdminConsoleOverview();
    statusCounts = o.lifecycle?.status_counts ?? [];
    recent = o.lifecycle?.recent ?? [];
  } catch (e) {
    overviewErr = e instanceof Error ? e.message : t("errors.fallbackMessage");
  }

  let subRows: Record<string, unknown>[] = [];
  try {
    const pack = await fetchCommerceAdminSubscriptions({ limit: 200 });
    const list = pack.subscriptions as Record<string, unknown>[] | undefined;
    subRows = Array.isArray(list) ? list : [];
  } catch (e) {
    subsErr = e instanceof Error ? e.message : t("errors.fallbackMessage");
  }

  return (
    <>
      <Header
        title={t("pages.adminHub.customersTitle")}
        subtitle={t("pages.adminHub.customersSubtitle")}
      />
      <p className="muted small admin-hub__back">
        <Link href={`${CONSOLE_BASE}/admin`}>
          {t("pages.adminHub.backCockpit")}
        </Link>
      </p>
      <PanelDataIssue err={overviewErr} diagnostic={true} t={t} />
      {!overviewErr && statusCounts.length > 0 ? (
        <div className="panel">
          <h2>{t("pages.adminHub.lifecycleCounts")}</h2>
          <ul className="news-list">
            {statusCounts.map((row) => (
              <li key={row.lifecycle_status}>
                <strong>{row.lifecycle_status}</strong>: {row.count}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {!overviewErr && recent.length > 0 ? (
        <div className="panel">
          <h2>{t("pages.adminHub.recentLifecycle")}</h2>
          <div className="table-wrap">
            <table className="data-table data-table--dense">
              <thead>
                <tr>
                  <th>{t("pages.adminHub.th.tenant")}</th>
                  <th>{t("pages.adminHub.th.status")}</th>
                  <th>{t("pages.adminHub.th.trialEnds")}</th>
                  <th>{t("pages.adminHub.th.action")}</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((row) => (
                  <tr key={row.tenant_id}>
                    <td>{row.tenant_id_masked}</td>
                    <td>{row.lifecycle_status}</td>
                    <td className="mono-small">{row.trial_ends_at ?? "—"}</td>
                    <td>
                      <Link
                        href={`${CONSOLE_BASE}/admin/customers/${encodeURIComponent(row.tenant_id)}`}
                      >
                        {t("pages.adminHub.open")}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
      <PanelDataIssue err={subsErr} diagnostic={true} t={t} />
      {!subsErr && subRows.length > 0 ? (
        <div className="panel">
          <h2>{t("pages.adminHub.subscriptionsTable")}</h2>
          <div className="table-wrap">
            <table className="data-table data-table--dense">
              <thead>
                <tr>
                  <th>{t("pages.adminHub.th.tenantRaw")}</th>
                  <th>{t("pages.adminHub.th.plan")}</th>
                  <th>{t("pages.adminHub.th.subStatus")}</th>
                  <th>{t("pages.adminHub.th.dunning")}</th>
                  <th>{t("pages.adminHub.th.action")}</th>
                </tr>
              </thead>
              <tbody>
                {subRows.map((row) => {
                  const tid = String(row.tenant_id ?? "");
                  return (
                    <tr key={tid}>
                      <td className="mono-small">{tid}</td>
                      <td>{String(row.plan_code ?? "—")}</td>
                      <td>{String(row.status ?? "—")}</td>
                      <td>{String(row.dunning_stage ?? "—")}</td>
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
      ) : null}
    </>
  );
}
