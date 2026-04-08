import Link from "next/link";

import { Header } from "@/components/layout/Header";
import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { fetchCommerceAdminPaymentsDiagnostics } from "@/lib/api";
import { CONSOLE_BASE } from "@/lib/console-paths";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import { canAccessAdminViaServer } from "@/lib/operator-session";

export const dynamic = "force-dynamic";

export default async function AdminCommercePaymentsPage() {
  const t = await getServerTranslator();
  const ok = await canAccessAdminViaServer();
  if (!ok) {
    return (
      <>
        <Header
          title={t("pages.adminHub.payDiagTitle")}
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
  let data: Record<string, unknown> | null = null;
  try {
    data = await fetchCommerceAdminPaymentsDiagnostics();
  } catch (e) {
    err = e instanceof Error ? e.message : t("errors.fallbackMessage");
  }

  const caps = data?.capabilities as Record<string, unknown> | undefined;
  const failures = (data?.webhook_failure_log_recent as unknown[]) ?? [];
  const rails = (data?.rail_webhook_inbox_summary as unknown[]) ?? [];

  return (
    <>
      <Header
        title={t("pages.adminHub.payDiagTitle")}
        subtitle={t("pages.adminHub.payDiagSubtitle")}
      />
      <p className="muted small admin-hub__back">
        <Link href={`${CONSOLE_BASE}/admin`}>
          {t("pages.adminHub.backCockpit")}
        </Link>
      </p>
      <PanelDataIssue err={err} diagnostic={true} t={t} />
      {!err && data ? (
        <>
          <div className="panel">
            <h2>{t("pages.adminHub.payCapabilities")}</h2>
            {caps ? (
              <ul className="news-list">
                <li>
                  {t("pages.adminHub.payEnv")}:{" "}
                  <strong>{String(caps.environment ?? "—")}</strong>
                </li>
                <li>
                  {t("pages.adminHub.payCheckout")}:{" "}
                  {String(caps.checkout_enabled ?? "—")}
                </li>
                <li>
                  {t("pages.adminHub.payCommercial")}:{" "}
                  {String(caps.commercial_enabled ?? "—")}
                </li>
              </ul>
            ) : null}
            <pre className="admin-json-preview">
              {JSON.stringify(caps ?? {}, null, 2)}
            </pre>
          </div>
          <div className="panel">
            <h2>{t("pages.adminHub.payWebhookFailures")}</h2>
            {failures.length === 0 ? (
              <p className="muted">{t("pages.adminHub.emptyFailures")}</p>
            ) : (
              <pre className="admin-json-preview">
                {JSON.stringify(failures, null, 2)}
              </pre>
            )}
          </div>
          <div className="panel">
            <h2>{t("pages.adminHub.payRails")}</h2>
            {rails.length === 0 ? (
              <p className="muted">{t("pages.adminHub.emptyRails")}</p>
            ) : (
              <pre className="admin-json-preview">
                {JSON.stringify(rails, null, 2)}
              </pre>
            )}
          </div>
        </>
      ) : null}
    </>
  );
}
