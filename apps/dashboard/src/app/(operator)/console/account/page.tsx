import Link from "next/link";

import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { Header } from "@/components/layout/Header";
import { AssistLayerPanel } from "@/components/panels/AssistLayerPanel";
import {
  fetchCommerceCustomerBalance,
  fetchCommerceCustomerMe,
} from "@/lib/api";
import { CONSOLE_BASE, consolePath } from "@/lib/console-paths";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

const QUICK_CARDS: readonly {
  href: string;
  titleKey: string;
  bodyKey: string;
}[] = [
  {
    href: consolePath("terminal"),
    titleKey: "account.home.quick.chartTitle",
    bodyKey: "account.home.quick.chartBody",
  },
  {
    href: consolePath("paper"),
    titleKey: "account.home.quick.paperTitle",
    bodyKey: "account.home.quick.paperBody",
  },
  {
    href: consolePath("health"),
    titleKey: "account.home.quick.aiTitle",
    bodyKey: "account.home.quick.aiBody",
  },
  {
    href: consolePath("account/balance"),
    titleKey: "account.home.quick.balanceTitle",
    bodyKey: "account.home.quick.balanceBody",
  },
  {
    href: consolePath("signals"),
    titleKey: "account.home.quick.signalsTitle",
    bodyKey: "account.home.quick.signalsBody",
  },
  {
    href: consolePath("account/telegram"),
    titleKey: "account.home.quick.telegramTitle",
    bodyKey: "account.home.quick.telegramBody",
  },
];

export default async function AccountHomePage() {
  const t = await getServerTranslator();
  let me: Record<string, unknown> | null = null;
  let bal: Record<string, unknown> | null = null;
  let err: string | null = null;
  try {
    [me, bal] = await Promise.all([
      fetchCommerceCustomerMe(),
      fetchCommerceCustomerBalance(),
    ]);
  } catch (e) {
    err = e instanceof Error ? e.message : t("account.loadError");
  }

  const access = (me?.access as Record<string, boolean> | undefined) ?? {};
  const plan = me?.plan as Record<string, unknown> | undefined;
  const tenant = me?.tenant as Record<string, string> | undefined;
  const wallet = bal?.wallet as Record<string, unknown> | undefined;
  const usageMonth = bal?.usage_month_utc as
    | Record<string, unknown>
    | undefined;

  return (
    <>
      <Header
        title={t("account.home.title")}
        subtitle={t("account.home.subtitle")}
      />
      <p className="muted small customer-area__console-lead">
        {t("account.home.consoleLead")}{" "}
        <Link href={CONSOLE_BASE} className="customer-area__inline-link">
          {t("account.home.consoleCta")}
        </Link>
      </p>
      <PanelDataIssue err={err} diagnostic={false} t={t} />
      <div
        className="customer-quick-grid"
        role="navigation"
        aria-label={t("account.home.quick.aria")}
      >
        {QUICK_CARDS.map((card) => (
          <Link
            key={card.href}
            href={card.href}
            className="customer-quick-card"
          >
            <span className="customer-quick-card__title">
              {t(card.titleKey)}
            </span>
            <span className="customer-quick-card__body muted small">
              {t(card.bodyKey)}
            </span>
          </Link>
        ))}
      </div>
      {!err && me ? (
        <div className="customer-snapshot-grid">
          <div className="panel customer-snapshot-panel">
            <h2 className="customer-snapshot-panel__heading">
              {t("account.home.snapshotTitle")}
            </h2>
            <dl className="customer-snapshot-dl">
              <div className="customer-snapshot-dl__row">
                <dt>{t("account.home.plan")}</dt>
                <dd>
                  <strong>
                    {plan?.display_name ? String(plan.display_name) : "—"}
                  </strong>
                </dd>
              </div>
              <div className="customer-snapshot-dl__row">
                <dt>{t("account.home.refLabel")}</dt>
                <dd>
                  <span className="customer-ref-value">
                    {tenant?.id_masked ?? "—"}
                  </span>
                </dd>
              </div>
              <div className="customer-snapshot-dl__row">
                <dt>{t("account.home.prepaid")}</dt>
                <dd>
                  <strong className="customer-metric-value">
                    {wallet?.prepaid_balance_list_usd != null
                      ? String(wallet.prepaid_balance_list_usd)
                      : "—"}{" "}
                    {t("account.home.currencyRef")}
                  </strong>
                </dd>
              </div>
              <div className="customer-snapshot-dl__row">
                <dt>{t("account.home.monthUsageLabel")}</dt>
                <dd>
                  <strong className="customer-metric-value">
                    {usageMonth?.ledger_total_list_usd != null
                      ? String(usageMonth.ledger_total_list_usd)
                      : "—"}{" "}
                    {t("account.home.currencyRef")}
                  </strong>
                </dd>
              </div>
              <div className="customer-snapshot-dl__row">
                <dt>{t("account.home.llmUsageLabel")}</dt>
                <dd>
                  <strong className="customer-metric-value">
                    {usageMonth?.llm_tokens_used != null
                      ? String(usageMonth.llm_tokens_used)
                      : "—"}
                  </strong>
                </dd>
              </div>
            </dl>
          </div>
          {access.admin_write ? (
            <div className="panel customer-admin-teaser">
              <h2 className="customer-snapshot-panel__heading">
                {t("account.home.adminSectionTitle")}
              </h2>
              <p className="muted small">{t("account.home.adminTeaser")}</p>
              <p className="customer-admin-teaser__cta">
                <Link href={consolePath("admin")}>
                  {t("account.home.adminLink")}
                </Link>
              </p>
            </div>
          ) : null}
        </div>
      ) : null}
      <div className="panel customer-next-steps">
        <h2>{t("account.home.nextStepsTitle")}</h2>
        <p className="muted small">{t("account.home.nextStepsLead")}</p>
        <ol className="customer-next-steps__list">
          <li>
            <Link href={consolePath("account/telegram")}>
              {t("account.home.stepTelegram")}
            </Link>
          </li>
          <li>
            <Link href={consolePath("account/deposit")}>
              {t("account.home.stepDeposit")}
            </Link>
          </li>
          <li>
            <Link href={consolePath("signals")}>
              {t("account.home.stepSignals")}
            </Link>
          </li>
          <li>
            <Link href={consolePath("paper")}>
              {t("account.home.stepPaper")}
            </Link>
          </li>
          <li>
            <Link href={consolePath("account/billing")}>
              {t("account.home.stepBilling")}
            </Link>
          </li>
          <li>
            <Link href={consolePath("health")}>
              {t("account.home.stepWellbeing")}
            </Link>
          </li>
        </ol>
      </div>
      <div id="customer-assist" className="customer-assist-region">
        <AssistLayerPanel
          titleKey="account.assistLayerTitle"
          leadKey="account.assistLayerLead"
          segments={[
            {
              segment: "customer-onboarding",
              labelKey: "account.assistTabOnboarding",
              contextHintKey: "account.assistContextHintOnboarding",
            },
            {
              segment: "support-billing",
              labelKey: "account.assistTabBilling",
              contextHintKey: "account.assistContextHintBilling",
            },
          ]}
        />
      </div>
    </>
  );
}
