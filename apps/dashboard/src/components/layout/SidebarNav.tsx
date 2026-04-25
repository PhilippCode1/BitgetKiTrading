"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useI18n } from "@/components/i18n/I18nProvider";
import {
  MAIN_CONSOLE_PRIMARY_SECTIONS,
  type MainConsoleNavSection,
} from "@/lib/main-console/navigation";
import { ONBOARDING_NAV_HREF } from "@/lib/onboarding-flow";
import { CONSOLE_BASE } from "@/lib/console-paths";
import type { UiMode } from "@/lib/dashboard-prefs";

type NavLink = Readonly<{ href: string; messageKey: string }>;

type NavSection = Readonly<{
  sectionKey: string | null;
  links: readonly NavLink[];
}>;

const SECTIONS: readonly NavSection[] = MAIN_CONSOLE_PRIMARY_SECTIONS;

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
  const sections = (
    showAdminNav
      ? base
      : base.map((section) => ({
          ...section,
          links: section.links.filter((link) => link.href !== `${CONSOLE_BASE}/admin`),
        }))
  ).filter((section) => section.links.length > 0) as readonly MainConsoleNavSection[];

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
