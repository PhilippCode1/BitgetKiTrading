import Link from "next/link";

import { AdminTenantDangerPanel } from "@/components/admin/AdminTenantDangerPanel";
import { Header } from "@/components/layout/Header";
import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { fetchCommerceAdminBillingSnapshot } from "@/lib/api";
import { CONSOLE_BASE } from "@/lib/console-paths";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import { canAccessAdminViaServer } from "@/lib/operator-session";

export const dynamic = "force-dynamic";

type Props = Readonly<{ params: Promise<{ tenantId: string }> }>;

export default async function AdminCustomerDetailPage({ params }: Props) {
  const { tenantId: raw } = await params;
  const tenantId = decodeURIComponent(raw);
  const t = await getServerTranslator();
  const ok = await canAccessAdminViaServer();
  if (!ok) {
    return (
      <>
        <Header
          title={t("pages.adminHub.customerDetail")}
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
  let snap: Record<string, unknown> | null = null;
  try {
    snap = await fetchCommerceAdminBillingSnapshot(tenantId);
  } catch (e) {
    err = e instanceof Error ? e.message : t("errors.fallbackMessage");
  }

  const sub = snap?.subscription as Record<string, unknown> | undefined;

  return (
    <>
      <Header
        title={t("pages.adminHub.customerDetail")}
        subtitle={t("pages.adminHub.customerDetailSubtitle")}
      />
      <p className="muted small admin-hub__back">
        <Link href={`${CONSOLE_BASE}/admin/customers`}>
          {t("pages.adminHub.backCustomers")}
        </Link>
        {" · "}
        <Link href={`${CONSOLE_BASE}/admin`}>
          {t("pages.adminHub.backCockpit")}
        </Link>
      </p>
      <div className="panel">
        <p className="mono-small">
          <strong>{t("pages.adminHub.th.tenantRaw")}:</strong> {tenantId}
        </p>
      </div>
      <PanelDataIssue err={err} diagnostic={true} t={t} />
      {!err && snap ? (
        <div className="panel">
          <h2>{t("pages.adminHub.billingSnapshot")}</h2>
          {sub ? (
            <ul className="news-list">
              <li>
                {t("pages.adminHub.th.plan")}:{" "}
                <strong>{String(sub.plan_code ?? "—")}</strong>
              </li>
              <li>
                {t("pages.adminHub.th.subStatus")}: {String(sub.status ?? "—")}
              </li>
              <li>
                {t("pages.adminHub.th.dunning")}:{" "}
                {String(sub.dunning_stage ?? "—")}
              </li>
            </ul>
          ) : (
            <p className="muted">{t("pages.adminHub.noSubscriptionRow")}</p>
          )}
        </div>
      ) : null}
      <AdminTenantDangerPanel tenantId={tenantId} />
    </>
  );
}
