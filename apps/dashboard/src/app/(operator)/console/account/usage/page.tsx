import Link from "next/link";

import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { Header } from "@/components/layout/Header";
import { fetchCommerceUsageSummary } from "@/lib/api";
import { consolePath } from "@/lib/console-paths";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function AccountUsagePage() {
  const t = await getServerTranslator();
  let summary: Record<string, unknown> | null = null;
  let err: string | null = null;
  try {
    summary = await fetchCommerceUsageSummary();
  } catch (e) {
    err = e instanceof Error ? e.message : t("account.usage.loadErr");
  }
  const month = summary?.month_utc as Record<string, unknown> | undefined;
  const plan = summary?.plan as Record<string, unknown> | undefined;

  return (
    <>
      <Header
        title={t("account.usage.title")}
        subtitle={t("account.usage.subtitle")}
        helpBriefKey="help.usage.brief"
        helpDetailKey="help.usage.detail"
      />
      <p className="muted small">
        <Link href={consolePath("usage")}>{t("account.usage.linkOps")}</Link>
      </p>
      {err ? (
        <PanelDataIssue err={err} diagnostic={false} t={t} />
      ) : (
        <div className="panel">
          <h2>{plan?.display_name ? String(plan.display_name) : "—"}</h2>
          <ul className="news-list operator-metric-list">
            <li>
              {t("account.home.monthUsageLabel")}:{" "}
              <strong className="customer-metric-value">
                {month?.ledger_total_list_usd != null
                  ? String(month.ledger_total_list_usd)
                  : "—"}{" "}
                {t("account.home.currencyRef")}
              </strong>
            </li>
            <li>
              {t("account.home.llmUsageLabel")}:{" "}
              <strong className="customer-metric-value">
                {month?.llm_tokens_used != null
                  ? String(month.llm_tokens_used)
                  : "—"}
              </strong>
            </li>
          </ul>
        </div>
      )}
    </>
  );
}
