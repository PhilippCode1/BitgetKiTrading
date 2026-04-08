"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useI18n } from "@/components/i18n/I18nProvider";
import { CONSOLE_BASE } from "@/lib/console-paths";

type Item = Readonly<{
  href: string;
  messageKey: string;
  match?: "exact" | "prefix";
}>;

const ITEMS: readonly Item[] = [
  {
    href: `${CONSOLE_BASE}/admin`,
    messageKey: "pages.adminHub.nav.cockpit",
    match: "exact",
  },
  {
    href: `${CONSOLE_BASE}/admin/performance`,
    messageKey: "pages.adminHub.nav.performance",
    match: "prefix",
  },
  {
    href: `${CONSOLE_BASE}/admin/customers`,
    messageKey: "pages.adminHub.nav.customers",
    match: "prefix",
  },
  {
    href: `${CONSOLE_BASE}/admin/billing`,
    messageKey: "pages.adminHub.nav.billing",
    match: "prefix",
  },
  {
    href: `${CONSOLE_BASE}/admin/contracts`,
    messageKey: "pages.adminHub.nav.contracts",
    match: "prefix",
  },
  {
    href: `${CONSOLE_BASE}/admin/profit-fees`,
    messageKey: "pages.adminHub.nav.profitFees",
    match: "prefix",
  },
  {
    href: `${CONSOLE_BASE}/admin/commerce-payments`,
    messageKey: "pages.adminHub.nav.payments",
    match: "prefix",
  },
  {
    href: `${CONSOLE_BASE}/admin/telegram`,
    messageKey: "pages.adminHub.nav.telegramDelivery",
    match: "prefix",
  },
  {
    href: `${CONSOLE_BASE}/admin/rules`,
    messageKey: "pages.adminHub.nav.rules",
    match: "prefix",
  },
  {
    href: `${CONSOLE_BASE}/admin/ai-governance`,
    messageKey: "pages.adminHub.nav.aiGovernance",
    match: "prefix",
  },
];

const OPS_LINKS: readonly Item[] = [
  {
    href: `${CONSOLE_BASE}/approvals`,
    messageKey: "pages.adminHub.nav.approvals",
  },
  {
    href: `${CONSOLE_BASE}/live-broker`,
    messageKey: "pages.adminHub.nav.liveBroker",
  },
  { href: `${CONSOLE_BASE}/health`, messageKey: "pages.adminHub.nav.health" },
  {
    href: `${CONSOLE_BASE}/integrations`,
    messageKey: "pages.adminHub.nav.integrations",
  },
];

function active(
  pathname: string,
  href: string,
  match?: "exact" | "prefix",
): boolean {
  if (match === "exact") {
    return pathname === href || pathname === `${href}/`;
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AdminHubSubnav() {
  const pathname = usePathname();
  const { t } = useI18n();
  return (
    <nav
      className="admin-hub-subnav panel"
      aria-label={t("pages.adminHub.subnavAria")}
    >
      <p className="admin-hub-subnav__title">
        {t("pages.adminHub.subnavTitle")}
      </p>
      <ul className="admin-hub-subnav__list">
        {ITEMS.map((item) => (
          <li key={item.href}>
            <Link
              href={item.href}
              className={
                active(pathname, item.href, item.match) ? "active" : undefined
              }
            >
              {t(item.messageKey)}
            </Link>
          </li>
        ))}
      </ul>
      <p className="admin-hub-subnav__title admin-hub-subnav__title--secondary">
        {t("pages.adminHub.subnavOps")}
      </p>
      <ul className="admin-hub-subnav__list admin-hub-subnav__list--ops">
        {OPS_LINKS.map((item) => (
          <li key={item.href}>
            <Link
              href={item.href}
              className={active(pathname, item.href) ? "active" : undefined}
            >
              {t(item.messageKey)}
            </Link>
          </li>
        ))}
      </ul>
      <p className="muted small admin-hub-subnav__hint">
        {t("pages.adminHub.subnavHint")}
      </p>
    </nav>
  );
}
