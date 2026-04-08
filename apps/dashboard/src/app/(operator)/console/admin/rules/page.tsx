import Link from "next/link";

import { Header } from "@/components/layout/Header";
import { AdminRulesPanel } from "@/components/panels/AdminRulesPanel";
import { fetchAdminRules } from "@/lib/api";
import { CONSOLE_BASE } from "@/lib/console-paths";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import { canAccessAdminViaServer } from "@/lib/operator-session";

export const dynamic = "force-dynamic";

export default async function AdminRulesPage() {
  const t = await getServerTranslator();
  const ok = await canAccessAdminViaServer();
  if (!ok) {
    return (
      <>
        <Header
          title={t("pages.adminHub.rulesTitle")}
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

  let data: import("@/lib/types").AdminRulesResponse = {
    rule_sets: [],
    env: {},
  };
  let error: string | null = null;
  try {
    data = await fetchAdminRules();
  } catch (e) {
    error = e instanceof Error ? e.message : t("errors.fallbackMessage");
  }

  return (
    <>
      <Header
        title={t("pages.adminHub.rulesTitle")}
        subtitle={t("pages.adminPage.subtitleRules")}
      />
      <p className="muted small admin-hub__back">
        <Link href={`${CONSOLE_BASE}/admin`}>
          {t("pages.adminHub.backCockpit")}
        </Link>
        {" · "}
        <Link href={`${CONSOLE_BASE}/admin/ai-governance`}>
          {t("pages.adminPage.linkAiGovernance")}
        </Link>
      </p>
      {error ? (
        <div className="panel" role="alert">
          <p className="msg-err" style={{ margin: 0 }}>
            {t("errors.loadDataPrefix")} {error}
          </p>
          <p className="muted small" style={{ margin: "10px 0 0" }}>
            {t("pages.adminPage.rulesUnavailableHint")}
          </p>
        </div>
      ) : (
        <AdminRulesPanel initial={data} />
      )}
    </>
  );
}
