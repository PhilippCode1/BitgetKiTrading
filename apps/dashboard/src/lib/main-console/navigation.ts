import { CONSOLE_BASE } from "@/lib/console-paths";

export type MainConsoleNavLink = Readonly<{
  href: string;
  messageKey: string;
}>;

export type MainConsoleNavSection = Readonly<{
  sectionKey: string | null;
  links: readonly MainConsoleNavLink[];
}>;

/**
 * Verbindliche Kernnavigation fuer die private deutsche Main Console.
 * Legacy-/Portal-/Billing-Pfade gehoeren nicht in diese Primaernavigation.
 */
export const MAIN_CONSOLE_PRIMARY_SECTIONS: readonly MainConsoleNavSection[] = [
  {
    sectionKey: "console.navSections.mainConsole",
    links: [
      { href: CONSOLE_BASE, messageKey: "console.nav.overview" },
      {
        href: `${CONSOLE_BASE}/market-universe`,
        messageKey: "console.nav.asset_universe",
      },
      { href: `${CONSOLE_BASE}/terminal`, messageKey: "console.nav.charts_market" },
      {
        href: `${CONSOLE_BASE}/signals`,
        messageKey: "console.nav.signals_ai",
      },
      { href: `${CONSOLE_BASE}/risk`, messageKey: "console.nav.risk_portfolio" },
      {
        href: `${CONSOLE_BASE}/live-broker`,
        messageKey: "console.nav.live_broker_safety",
      },
      {
        href: `${CONSOLE_BASE}/bitget-demo`,
        messageKey: "console.nav.bitget_demo",
      },
      { href: `${CONSOLE_BASE}/safety-center`, messageKey: "console.nav.safety_center" },
      {
        href: `${CONSOLE_BASE}/system-health-map`,
        messageKey: "console.nav.system_alerts",
      },
      {
        href: `${CONSOLE_BASE}/reports`,
        messageKey: "console.nav.reports_evidence",
      },
      {
        href: `${CONSOLE_BASE}/account/language`,
        messageKey: "console.nav.settings_runtime",
      },
    ],
  },
];

