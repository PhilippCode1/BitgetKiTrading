"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useI18n } from "@/components/i18n/I18nProvider";
import { CONSOLE_BASE } from "@/lib/console-paths";

const SEGMENT_LABEL: Readonly<Record<string, string>> = {
  ops: "console.nav.ops",
  terminal: "console.nav.terminal",
  approvals: "console.nav.approvals",
  "market-universe": "console.nav.market_universe",
  capabilities: "console.nav.capabilities",
  signals: "console.nav.signals",
  "no-trade": "console.nav.no_trade",
  "live-broker": "console.nav.live_broker",
  "shadow-live": "console.nav.shadow_live",
  paper: "console.nav.paper",
  learning: "console.nav.learning",
  strategies: "console.nav.strategies",
  news: "console.nav.news",
  usage: "console.nav.usage",
  health: "console.nav.health",
  diagnostics: "console.nav.diagnostics",
  integrations: "console.nav.integrations",
  help: "pages.consoleHelp.breadcrumb",
  admin: "console.nav.admin",
  account: "account.nav.overview",
};

const ACCOUNT_TAIL: Readonly<Record<string, string>> = {
  profile: "account.nav.profile",
  language: "account.nav.language",
  telegram: "account.nav.telegram",
  broker: "account.nav.broker",
  balance: "account.nav.balance",
  usage: "account.nav.usage",
  deposit: "account.nav.deposit",
  payments: "account.nav.payments",
  history: "account.nav.history",
};

function breadcrumbMessageKey(
  parts: readonly string[],
  depthIndex: number,
): string {
  const sub = parts.slice(0, depthIndex + 1).join("/");
  if (sub === "live-broker/forensic") return "console.breadcrumbForensic";

  if (parts[0] === "account" && depthIndex === 1) {
    const tail = parts[1];
    if (tail && ACCOUNT_TAIL[tail]) return ACCOUNT_TAIL[tail];
  }

  const seg = parts[depthIndex];
  const isLast = depthIndex === parts.length - 1;
  if (isLast && depthIndex > 0) {
    const par = parts[depthIndex - 1];
    if (par === "signals" || par === "strategies" || par === "news") {
      return "console.breadcrumbDetail";
    }
    if (par === "forensic" && parts[0] === "live-broker") {
      return "console.breadcrumbDetail";
    }
  }

  return SEGMENT_LABEL[seg] ?? "console.breadcrumbDetail";
}

export function ConsoleBreadcrumbs() {
  const pathname = usePathname();
  const { t } = useI18n();
  const segments = pathname.replace(/\/$/, "").split("/").filter(Boolean);
  if (segments[0] !== "console") return null;
  const parts = segments.slice(1);
  if (parts.length === 0) return null;

  const crumbs: { href: string; labelKey: string }[] = [
    { href: CONSOLE_BASE, labelKey: "console.breadcrumbRoot" },
  ];
  let acc = CONSOLE_BASE;
  for (let i = 0; i < parts.length; i++) {
    acc += `/${parts[i]}`;
    crumbs.push({ href: acc, labelKey: breadcrumbMessageKey(parts, i) });
  }

  return (
    <nav className="dash-breadcrumbs" aria-label={t("console.breadcrumbsAria")}>
      <ol className="dash-breadcrumbs-list">
        {crumbs.map((c, idx) => {
          const isLast = idx === crumbs.length - 1;
          return (
            <li key={c.href} className="dash-breadcrumbs-item">
              {isLast ? (
                <span aria-current="page">{t(c.labelKey)}</span>
              ) : (
                <Link href={c.href}>{t(c.labelKey)}</Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
