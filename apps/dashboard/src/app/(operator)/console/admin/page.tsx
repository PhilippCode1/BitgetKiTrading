import Link from "next/link";

import { Header } from "@/components/layout/Header";
import {
  fetchAdminConsoleOverview,
  fetchLiveBrokerRuntime,
  fetchMonitorAlertsOpen,
  fetchSystemHealthCached,
} from "@/lib/api";
import { CONSOLE_BASE } from "@/lib/console-paths";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import { canAccessAdminViaServer } from "@/lib/operator-session";
import { systemHealthAdminHubGreen } from "@/lib/health-service-reachability";
import type {
  AdminConsoleOverviewResponse,
  SystemHealthResponse,
} from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function AdminCockpitPage() {
  const t = await getServerTranslator();
  const ok = await canAccessAdminViaServer();
  if (!ok) {
    return (
      <>
        <Header
          title={t("pages.adminHub.title")}
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

  const settled = await Promise.allSettled([
    fetchAdminConsoleOverview(),
    fetchSystemHealthCached(),
    fetchMonitorAlertsOpen(),
    fetchLiveBrokerRuntime(),
  ]);

  let overview: AdminConsoleOverviewResponse | null = null;
  let overviewErr: string | null = null;
  if (settled[0].status === "fulfilled") {
    overview = settled[0].value;
  } else {
    overviewErr =
      settled[0].reason instanceof Error
        ? settled[0].reason.message
        : t("errors.fallbackMessage");
  }

  let health: SystemHealthResponse | null = null;
  let healthErr: string | null = null;
  if (settled[1].status === "fulfilled") {
    health = settled[1].value;
  } else {
    healthErr =
      settled[1].reason instanceof Error
        ? settled[1].reason.message
        : t("errors.fallbackMessage");
  }

  let openAlerts = 0;
  let alertsErr: string | null = null;
  if (settled[2].status === "fulfilled") {
    const a = settled[2].value;
    const items = (a as { items?: unknown[] }).items;
    openAlerts = Array.isArray(items) ? items.length : 0;
  } else {
    alertsErr =
      settled[2].reason instanceof Error
        ? settled[2].reason.message
        : t("errors.fallbackMessage");
  }

  let liveMode: string | null = null;
  let liveErr: string | null = null;
  if (settled[3].status === "fulfilled") {
    const rt = settled[3].value as { runtime?: { mode?: string } };
    liveMode = rt.runtime?.mode != null ? String(rt.runtime.mode) : null;
  } else {
    liveErr =
      settled[3].reason instanceof Error
        ? settled[3].reason.message
        : t("errors.fallbackMessage");
  }

  const trialActive =
    overview?.lifecycle?.status_counts?.find(
      (r) => r.lifecycle_status === "trial_active",
    )?.count ?? 0;
  const liveApproved =
    overview?.lifecycle?.status_counts?.find(
      (r) => r.lifecycle_status === "live_approved",
    )?.count ?? 0;
  const subs = overview?.subscriptions;
  const reviewOpen = overview?.contracts_review_open;

  return (
    <>
      <Header
        title={t("pages.adminHub.title")}
        subtitle={t("pages.adminHub.subtitle")}
      />
      <p className="muted small admin-hub__intro">
        {t("pages.adminHub.intro")}
      </p>

      <div className="admin-cockpit-metrics">
        <section
          className={`admin-cockpit-card admin-cockpit-card--${systemHealthAdminHubGreen(health) ? "ok" : "warn"}`}
        >
          <h2 className="admin-cockpit-card__title">
            {t("pages.adminHub.card.systemHealth")}
          </h2>
          {healthErr ? (
            <p className="msg-err small">{healthErr}</p>
          ) : (
            <>
              <p className="admin-cockpit-card__value">
                {systemHealthAdminHubGreen(health)
                  ? t("pages.adminHub.status.ok")
                  : t("pages.adminHub.status.check")}
              </p>
              <p className="muted small">
                <Link href={`${CONSOLE_BASE}/health`}>
                  {t("pages.adminHub.link.healthDetail")}
                </Link>
              </p>
            </>
          )}
        </section>

        <section
          className={`admin-cockpit-card admin-cockpit-card--${openAlerts > 0 ? "warn" : "ok"}`}
        >
          <h2 className="admin-cockpit-card__title">
            {t("pages.adminHub.card.alerts")}
          </h2>
          {alertsErr ? (
            <p className="msg-err small">{alertsErr}</p>
          ) : (
            <>
              <p className="admin-cockpit-card__value">{openAlerts}</p>
              <p className="muted small">
                <Link href={`${CONSOLE_BASE}/health`}>
                  {t("pages.adminHub.link.monitor")}
                </Link>
              </p>
            </>
          )}
        </section>

        <section className="admin-cockpit-card admin-cockpit-card--neutral">
          <h2 className="admin-cockpit-card__title">
            {t("pages.adminHub.card.liveBroker")}
          </h2>
          {liveErr ? (
            <p className="msg-err small">{liveErr}</p>
          ) : (
            <>
              <p className="admin-cockpit-card__value">{liveMode ?? "—"}</p>
              <p className="muted small">
                <Link href={`${CONSOLE_BASE}/live-broker`}>
                  {t("pages.adminHub.link.liveJournal")}
                </Link>
              </p>
            </>
          )}
        </section>

        <section className="admin-cockpit-card admin-cockpit-card--neutral">
          <h2 className="admin-cockpit-card__title">
            {t("pages.adminHub.card.trial")}
          </h2>
          {overviewErr ? (
            <p className="msg-err small">{overviewErr}</p>
          ) : overview?.commercial_enabled ? (
            <>
              <p className="admin-cockpit-card__value">{trialActive}</p>
              <p className="muted small">
                {t("pages.adminHub.card.trialHint")}
              </p>
            </>
          ) : (
            <p className="muted small">{t("pages.adminHub.commercialOff")}</p>
          )}
        </section>

        <section className="admin-cockpit-card admin-cockpit-card--neutral">
          <h2 className="admin-cockpit-card__title">
            {t("pages.adminHub.card.liveApproved")}
          </h2>
          {overviewErr ? (
            <p className="msg-err small">{overviewErr}</p>
          ) : overview?.commercial_enabled ? (
            <>
              <p className="admin-cockpit-card__value">{liveApproved}</p>
              <p className="muted small">
                <Link href={`${CONSOLE_BASE}/admin/customers`}>
                  {t("pages.adminHub.link.customers")}
                </Link>
              </p>
            </>
          ) : (
            <p className="muted small">{t("pages.adminHub.commercialOff")}</p>
          )}
        </section>

        <section
          className={`admin-cockpit-card admin-cockpit-card--${
            (subs?.dunning_attention ?? 0) > 0 ? "warn" : "ok"
          }`}
        >
          <h2 className="admin-cockpit-card__title">
            {t("pages.adminHub.card.billing")}
          </h2>
          {overviewErr ? (
            <p className="msg-err small">{overviewErr}</p>
          ) : overview?.commercial_enabled && subs ? (
            <>
              <p className="admin-cockpit-card__value">
                {t("pages.adminHub.card.billingValue", {
                  subs: subs.subscription_rows,
                  dunning: subs.dunning_attention,
                })}
              </p>
              <p className="muted small">
                <Link href={`${CONSOLE_BASE}/admin/billing`}>
                  {t("pages.adminHub.link.billing")}
                </Link>
              </p>
            </>
          ) : (
            <p className="muted small">{t("pages.adminHub.commercialOff")}</p>
          )}
        </section>

        <section
          className={`admin-cockpit-card admin-cockpit-card--${
            (reviewOpen ?? 0) > 0 ? "warn" : "ok"
          }`}
        >
          <h2 className="admin-cockpit-card__title">
            {t("pages.adminHub.card.contracts")}
          </h2>
          {overviewErr ? (
            <p className="msg-err small">{overviewErr}</p>
          ) : overview?.commercial_enabled ? (
            <>
              <p className="admin-cockpit-card__value">{reviewOpen ?? "—"}</p>
              <p className="muted small">
                <Link href={`${CONSOLE_BASE}/admin/contracts`}>
                  {t("pages.adminHub.link.contracts")}
                </Link>
              </p>
            </>
          ) : (
            <p className="muted small">{t("pages.adminHub.commercialOff")}</p>
          )}
        </section>

        <section className="admin-cockpit-card admin-cockpit-card--neutral">
          <h2 className="admin-cockpit-card__title">
            {t("pages.adminHub.card.profitFee")}
          </h2>
          {overviewErr ? (
            <p className="msg-err small">{overviewErr}</p>
          ) : overview?.profit_fee_module_enabled &&
            overview.profit_fee_by_status ? (
            <>
              <ul className="admin-cockpit-mini-list">
                {overview.profit_fee_by_status.map((row) => (
                  <li key={row.status}>
                    {row.status}: <strong>{row.count}</strong>
                  </li>
                ))}
              </ul>
              <p className="muted small">
                <Link href={`${CONSOLE_BASE}/admin/profit-fees`}>
                  {t("pages.adminHub.link.profitFees")}
                </Link>
              </p>
            </>
          ) : (
            <p className="muted small">{t("pages.adminHub.profitFeeOff")}</p>
          )}
        </section>

        <section className="admin-cockpit-card admin-cockpit-card--neutral">
          <h2 className="admin-cockpit-card__title">
            {t("pages.adminHub.card.telegram")}
          </h2>
          {overviewErr ? (
            <p className="msg-err small">{overviewErr}</p>
          ) : overview?.integrations_telegram &&
            overview.integrations_telegram.length > 0 ? (
            <ul className="admin-cockpit-mini-list">
              {overview.integrations_telegram.slice(0, 5).map((row) => (
                <li key={row.telegram_state}>
                  {row.telegram_state}: <strong>{row.count}</strong>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted small">—</p>
          )}
        </section>

        <section className="admin-cockpit-card admin-cockpit-card--neutral">
          <h2 className="admin-cockpit-card__title">
            {t("pages.adminHub.card.broker")}
          </h2>
          {overviewErr ? (
            <p className="msg-err small">{overviewErr}</p>
          ) : overview?.integrations_broker &&
            overview.integrations_broker.length > 0 ? (
            <ul className="admin-cockpit-mini-list">
              {overview.integrations_broker.slice(0, 5).map((row) => (
                <li key={row.broker_state}>
                  {row.broker_state}: <strong>{row.count}</strong>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted small">—</p>
          )}
          <p className="muted small">
            <Link href={`${CONSOLE_BASE}/integrations`}>
              {t("pages.adminHub.link.integrations")}
            </Link>
          </p>
        </section>

        <section className="admin-cockpit-card admin-cockpit-card--accent">
          <h2 className="admin-cockpit-card__title">
            {t("pages.adminHub.card.support")}
          </h2>
          <p className="muted small">{t("pages.adminHub.card.supportBody")}</p>
          <p className="admin-cockpit-card__actions">
            <Link href={`${CONSOLE_BASE}/approvals`}>
              {t("pages.adminHub.link.approvals")}
            </Link>
            {" · "}
            <Link href={`${CONSOLE_BASE}/account`}>
              {t("pages.adminHub.link.customerAssist")}
            </Link>
          </p>
        </section>
      </div>

      {overview?.lifecycle?.recent && overview.lifecycle.recent.length > 0 ? (
        <div className="panel admin-cockpit-recent">
          <h2>{t("pages.adminHub.recentLifecycle")}</h2>
          <div className="table-wrap">
            <table className="data-table data-table--dense">
              <thead>
                <tr>
                  <th>{t("pages.adminHub.th.tenant")}</th>
                  <th>{t("pages.adminHub.th.status")}</th>
                  <th>{t("pages.adminHub.th.trialEnds")}</th>
                  <th>{t("pages.adminHub.th.email")}</th>
                  <th>{t("pages.adminHub.th.action")}</th>
                </tr>
              </thead>
              <tbody>
                {overview.lifecycle.recent.map((row) => (
                  <tr key={row.tenant_id}>
                    <td>{row.tenant_id_masked}</td>
                    <td>{row.lifecycle_status}</td>
                    <td className="mono-small">{row.trial_ends_at ?? "—"}</td>
                    <td>
                      {row.email_verified
                        ? t("pages.adminHub.yes")
                        : t("pages.adminHub.no")}
                    </td>
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

      <div className="panel admin-cockpit-quicklinks">
        <h2>{t("pages.adminHub.quickLinksTitle")}</h2>
        <ul className="news-list">
          <li>
            <Link href={`${CONSOLE_BASE}/admin/rules`}>
              {t("pages.adminHub.ql.rules")}
            </Link>
          </li>
          <li>
            <Link href={`${CONSOLE_BASE}/admin/ai-governance`}>
              {t("pages.adminHub.ql.governance")}
            </Link>
          </li>
          <li>
            <Link href={`${CONSOLE_BASE}/admin/commerce-payments`}>
              {t("pages.adminHub.ql.payments")}
            </Link>
          </li>
          <li>
            <Link href={`${CONSOLE_BASE}/strategies`}>
              {t("pages.adminHub.ql.strategies")}
            </Link>
          </li>
        </ul>
      </div>
    </>
  );
}
