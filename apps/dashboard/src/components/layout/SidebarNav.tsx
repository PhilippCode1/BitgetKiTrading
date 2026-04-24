"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useI18n } from "@/components/i18n/I18nProvider";
import { ONBOARDING_NAV_HREF } from "@/lib/onboarding-flow";
import { CONSOLE_BASE } from "@/lib/console-paths";
import type { UiMode } from "@/lib/dashboard-prefs";

type NavLink = Readonly<{ href: string; messageKey: string }>;

type NavSection = Readonly<{
  sectionKey: string | null;
  links: readonly NavLink[];
}>;

/**
 * Profi-Konsole: weniger Sektionen, Health beim Cockpit (Lage + System nahe beieinander).
 */
const SECTIONS: readonly NavSection[] = [
  {
    sectionKey: null,
    links: [{ href: CONSOLE_BASE, messageKey: "console.nav.overview" }],
  },
  {
    sectionKey: "console.navSections.cockpit",
    links: [
      { href: `${CONSOLE_BASE}/ops`, messageKey: "console.nav.ops" },
      { href: `${CONSOLE_BASE}/terminal`, messageKey: "console.nav.terminal" },
      {
        href: `${CONSOLE_BASE}/approvals`,
        messageKey: "console.nav.approvals",
      },
      { href: `${CONSOLE_BASE}/health`, messageKey: "console.nav.health" },
      {
        href: `${CONSOLE_BASE}/diagnostics`,
        messageKey: "console.nav.diagnostics",
      },
      {
        href: `${CONSOLE_BASE}/self-healing`,
        messageKey: "console.nav.self_healing",
      },
    ],
  },
  {
    sectionKey: "console.navSections.market",
    links: [
      {
        href: `${CONSOLE_BASE}/market-universe`,
        messageKey: "console.nav.market_universe",
      },
      {
        href: `${CONSOLE_BASE}/capabilities`,
        messageKey: "console.nav.capabilities",
      },
      { href: `${CONSOLE_BASE}/signals`, messageKey: "console.nav.signals" },
      { href: `${CONSOLE_BASE}/no-trade`, messageKey: "console.nav.no_trade" },
    ],
  },
  {
    sectionKey: "console.navSections.execution",
    links: [
      {
        href: `${CONSOLE_BASE}/live-broker`,
        messageKey: "console.nav.live_broker",
      },
      {
        href: `${CONSOLE_BASE}/shadow-live`,
        messageKey: "console.nav.shadow_live",
      },
      { href: `${CONSOLE_BASE}/paper`, messageKey: "console.nav.paper" },
    ],
  },
  {
    sectionKey: "console.navSections.model",
    links: [
      { href: `${CONSOLE_BASE}/learning`, messageKey: "console.nav.learning" },
      {
        href: `${CONSOLE_BASE}/strategies`,
        messageKey: "console.nav.strategies",
      },
    ],
  },
  {
    sectionKey: "console.navSections.operations",
    links: [
      { href: `${CONSOLE_BASE}/news`, messageKey: "console.nav.news" },
      { href: `${CONSOLE_BASE}/usage`, messageKey: "console.nav.usage" },
      {
        href: `${CONSOLE_BASE}/integrations`,
        messageKey: "console.nav.integrations",
      },
    ],
  },
  {
    sectionKey: "console.navSections.account",
    links: [
      { href: `${CONSOLE_BASE}/account`, messageKey: "console.nav.accountHub" },
    ],
  },
];

const ADMIN_LINK: NavLink = {
  href: `${CONSOLE_BASE}/admin`,
  messageKey: "console.nav.admin",
};

/**
 * Einfache Ansicht: Health, Paper, Konto und Hilfe zuerst; Chart/Signale danach;
 * Orientierung zuletzt — gleiche Begriffe wie in den Kacheln auf der Startseite.
 */
const SIMPLE_SECTIONS: readonly NavSection[] = [
  {
    sectionKey: null,
    links: [{ href: CONSOLE_BASE, messageKey: "simple.nav.start" }],
  },
  {
    sectionKey: "simple.navSection.essentials",
    links: [
      { href: `${CONSOLE_BASE}/health`, messageKey: "simple.nav.aiStatus" },
      {
        href: `${CONSOLE_BASE}/diagnostics`,
        messageKey: "simple.nav.diagnostics",
      },
      {
        href: `${CONSOLE_BASE}/self-healing`,
        messageKey: "simple.nav.selfHealing",
      },
      { href: `${CONSOLE_BASE}/paper`, messageKey: "simple.nav.paper" },
      { href: `${CONSOLE_BASE}/account`, messageKey: "simple.nav.account" },
    ],
  },
  {
    sectionKey: "simple.navSection.market",
    links: [
      { href: `${CONSOLE_BASE}/terminal`, messageKey: "simple.nav.chart" },
      { href: `${CONSOLE_BASE}/signals`, messageKey: "simple.nav.signals" },
    ],
  },
  {
    sectionKey: "simple.navSection.guide",
    links: [
      { href: `${CONSOLE_BASE}/help`, messageKey: "simple.nav.help" },
      { href: ONBOARDING_NAV_HREF, messageKey: "simple.nav.onboarding" },
      {
        href: `${CONSOLE_BASE}/account/language`,
        messageKey: "simple.nav.settings",
      },
    ],
  },
];

type Props = Readonly<{
  /** Server-only: true nur bei getOperatorSession().role === "admin" (DASHBOARD_GATEWAY_AUTHORIZATION), niemals von Client-ENV. */
  showAdminNav: boolean;
  uiMode?: UiMode;
}>;

export function SidebarNav({ showAdminNav, uiMode = "pro" }: Props) {
  const pathname = usePathname();
  const { t } = useI18n();
  const base = uiMode === "simple" ? SIMPLE_SECTIONS : SECTIONS;
  const sections = showAdminNav
    ? [
        ...base,
        {
          sectionKey: "console.navSections.internal",
          links: [ADMIN_LINK] as const,
        },
      ]
    : base;

  return (
    <aside className="dash-sidebar" data-e2e="operator-sidebar">
      <Link href="/" className="dash-brand dash-brand-link">
        {uiMode === "simple" ? t("console.brandSimple") : t("console.brand")}
      </Link>
      <p className="dash-sidebar-note muted small">
        {uiMode === "simple"
          ? t("console.sidebarNoteSimple")
          : t("console.sidebarNote")}
      </p>
      <Link href="/" className="dash-back-to-product">
        {t("console.backToProduct")}
      </Link>
      {sections.map((section) => (
        <div
          key={section.sectionKey ?? section.links[0]?.href}
          className="dash-nav-section"
        >
          {section.sectionKey ? (
            <div className="dash-nav-heading">{t(section.sectionKey)}</div>
          ) : null}
          <nav
            className="dash-nav"
            aria-label={
              section.sectionKey ? t(section.sectionKey) : t("console.navAria")
            }
          >
            {section.links.map(({ href, messageKey }) => {
              const active =
                pathname === href || pathname.startsWith(`${href}/`);
              return (
                <Link
                  key={href}
                  href={href}
                  className={active ? "dash-nav-link active" : "dash-nav-link"}
                >
                  {t(messageKey)}
                </Link>
              );
            })}
          </nav>
        </div>
      ))}
    </aside>
  );
}
