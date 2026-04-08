import Link from "next/link";

import { Header } from "@/components/layout/Header";
import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { fetchAdminTelegramCustomerDelivery } from "@/lib/api";
import { CONSOLE_BASE } from "@/lib/console-paths";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import { canAccessAdminViaServer } from "@/lib/operator-session";
import type { AdminTelegramCustomerDeliveryResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function AdminTelegramDeliveryPage() {
  const t = await getServerTranslator();
  const ok = await canAccessAdminViaServer();
  if (!ok) {
    return (
      <>
        <Header
          title={t("pages.adminHub.telegramTitle")}
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
  let data: AdminTelegramCustomerDeliveryResponse | null = null;
  try {
    data = await fetchAdminTelegramCustomerDelivery();
  } catch (e) {
    err = e instanceof Error ? e.message : t("errors.fallbackMessage");
  }

  const recent = data?.customer_notify_recent ?? [];
  const failed = data?.customer_notify_failed_recent ?? [];
  const audit = data?.command_audit_recent ?? [];

  return (
    <>
      <Header
        title={t("pages.adminHub.telegramTitle")}
        subtitle={t("pages.adminHub.telegramSubtitle")}
      />
      <p className="muted small admin-hub__back">
        <Link href={`${CONSOLE_BASE}/admin`}>
          {t("pages.adminHub.backCockpit")}
        </Link>
      </p>
      <PanelDataIssue err={err} diagnostic={true} t={t} />
      {!err && data ? (
        <div className="panel">
          <p className="muted small" style={{ marginTop: 0 }}>
            {t("pages.adminHub.telegramBindings", {
              count: String(data.bindings_count ?? "—"),
            })}
          </p>
        </div>
      ) : null}
      {!err && failed.length > 0 ? (
        <div className="panel">
          <h2>{t("pages.adminHub.telegramFailedHeading")}</h2>
          <div className="table-wrap">
            <table className="data-table data-table--dense">
              <thead>
                <tr>
                  <th>{t("pages.adminHub.telegramThTime")}</th>
                  <th>{t("pages.adminHub.telegramThTenant")}</th>
                  <th>{t("pages.adminHub.telegramThCategory")}</th>
                  <th>{t("pages.adminHub.telegramThError")}</th>
                </tr>
              </thead>
              <tbody>
                {failed.map((row) => (
                  <tr key={row.alert_id}>
                    <td>{row.created_ts ?? "—"}</td>
                    <td>{row.tenant_id_masked}</td>
                    <td>{row.customer_category || "—"}</td>
                    <td className="muted">{row.last_error ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
      {!err && recent.length > 0 ? (
        <div className="panel">
          <h2>{t("pages.adminHub.telegramRecentHeading")}</h2>
          <div className="table-wrap">
            <table className="data-table data-table--dense">
              <thead>
                <tr>
                  <th>{t("pages.adminHub.telegramThTime")}</th>
                  <th>{t("pages.adminHub.telegramThState")}</th>
                  <th>{t("pages.adminHub.telegramThTenant")}</th>
                  <th>{t("pages.adminHub.telegramThCategory")}</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((row) => (
                  <tr key={row.alert_id}>
                    <td>{row.created_ts ?? "—"}</td>
                    <td>{row.state}</td>
                    <td>{row.tenant_id_masked}</td>
                    <td>{row.customer_category || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
      {!err && audit.length > 0 ? (
        <div className="panel">
          <h2>{t("pages.adminHub.telegramAuditHeading")}</h2>
          <div className="table-wrap">
            <table className="data-table data-table--dense">
              <thead>
                <tr>
                  <th>{t("pages.adminHub.telegramThTime")}</th>
                  <th>{t("pages.adminHub.telegramThCommand")}</th>
                  <th>{t("pages.adminHub.telegramThChat")}</th>
                </tr>
              </thead>
              <tbody>
                {audit.map((row) => (
                  <tr key={row.id}>
                    <td>{row.ts ?? "—"}</td>
                    <td>
                      <code>{row.command}</code>
                    </td>
                    <td className="muted">{row.chat_id_masked ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
      {!err &&
      data &&
      recent.length === 0 &&
      failed.length === 0 &&
      audit.length === 0 ? (
        <div className="panel">
          <p className="muted" style={{ margin: 0 }}>
            {t("pages.adminHub.telegramEmpty")}
          </p>
        </div>
      ) : null}
    </>
  );
}
