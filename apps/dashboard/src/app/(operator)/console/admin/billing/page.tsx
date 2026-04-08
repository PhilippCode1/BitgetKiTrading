import Link from "next/link";

import { Header } from "@/components/layout/Header";
import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { fetchCommerceAdminSubscriptions } from "@/lib/api";
import { CONSOLE_BASE } from "@/lib/console-paths";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import { canAccessAdminViaServer } from "@/lib/operator-session";

export const dynamic = "force-dynamic";

export default async function AdminBillingPage() {
  const t = await getServerTranslator();
  const ok = await canAccessAdminViaServer();
  if (!ok) {
    return (
      <>
        <Header
          title={t("pages.adminHub.billingTitle")}
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
  let rows: Record<string, unknown>[] = [];
  try {
    const pack = await fetchCommerceAdminSubscriptions({ limit: 300 });
    const list = pack.subscriptions as Record<string, unknown>[] | undefined;
    rows = Array.isArray(list) ? list : [];
  } catch (e) {
    err = e instanceof Error ? e.message : t("errors.fallbackMessage");
  }

  return (
    <>
      <Header
        title={t("pages.adminHub.billingTitle")}
        subtitle={t("pages.adminHub.billingSubtitle")}
      />
      <p className="muted small admin-hub__back">
        <Link href={`${CONSOLE_BASE}/admin`}>
          {t("pages.adminHub.backCockpit")}
        </Link>
      </p>
      <p className="muted small">{t("pages.adminHub.billingLead")}</p>
      <PanelDataIssue err={err} diagnostic={true} t={t} />
      {!err && rows.length > 0 ? (
        <div className="panel">
          <div className="table-wrap">
            <table className="data-table data-table--dense">
              <thead>
                <tr>
                  <th>{t("pages.adminHub.th.tenantRaw")}</th>
                  <th>{t("pages.adminHub.th.plan")}</th>
                  <th>{t("pages.adminHub.th.subStatus")}</th>
                  <th>{t("pages.adminHub.th.dunning")}</th>
                  <th>{t("pages.adminHub.th.updated")}</th>
                  <th>{t("pages.adminHub.th.action")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const tid = String(row.tenant_id ?? "");
                  const d = String(row.dunning_stage ?? "").toLowerCase();
                  const warn =
                    d.length > 0 &&
                    !["none", "ok", "healthy", "clear", "current"].includes(d);
                  return (
                    <tr
                      key={tid}
                      className={warn ? "admin-row-warn" : undefined}
                    >
                      <td className="mono-small">{tid}</td>
                      <td>{String(row.plan_code ?? "—")}</td>
                      <td>{String(row.status ?? "—")}</td>
                      <td>{String(row.dunning_stage ?? "—")}</td>
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
        <p className="muted">{t("pages.adminHub.emptySubscriptions")}</p>
      ) : null}
    </>
  );
}
