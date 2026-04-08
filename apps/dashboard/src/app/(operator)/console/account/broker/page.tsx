import Link from "next/link";

import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { Header } from "@/components/layout/Header";
import { fetchCommerceCustomerIntegrations } from "@/lib/api";
import { consolePath } from "@/lib/console-paths";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function AccountBrokerPage() {
  const t = await getServerTranslator();
  let data: Record<string, unknown> | null = null;
  let err: string | null = null;
  try {
    data = await fetchCommerceCustomerIntegrations();
  } catch (e) {
    err = e instanceof Error ? e.message : t("account.broker.loadErr");
  }
  const integ = data?.integration as Record<string, unknown> | undefined;

  return (
    <>
      <Header
        title={t("account.broker.title")}
        subtitle={t("account.broker.subtitle")}
        helpBriefKey="help.broker.brief"
        helpDetailKey="help.broker.detail"
      />
      {err ? (
        <PanelDataIssue err={err} diagnostic={false} t={t} />
      ) : (
        <div className="panel">
          <ul className="news-list">
            <li>
              {t("account.broker.state")}:{" "}
              <strong>
                {integ?.broker_state != null ? String(integ.broker_state) : "—"}
              </strong>
            </li>
            <li className="muted">
              {t("account.broker.hint")}:{" "}
              {integ?.broker_hint_public
                ? String(integ.broker_hint_public)
                : "—"}
            </li>
          </ul>
        </div>
      )}
      <div className="panel">
        <h2>{t("account.broker.nextTitle")}</h2>
        <p className="muted small">{t("account.broker.nextLead")}</p>
        <ul className="news-list">
          <li>
            <Link href={consolePath("paper")}>
              {t("account.broker.nextPaper")}
            </Link>
          </li>
          <li>
            <Link href={consolePath("live-broker")}>
              {t("account.broker.nextLiveJournal")}
            </Link>
          </li>
          <li>
            <Link href={consolePath("account/telegram")}>
              {t("account.broker.nextTelegram")}
            </Link>
          </li>
        </ul>
      </div>
    </>
  );
}
