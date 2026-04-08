"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useI18n } from "@/components/i18n/I18nProvider";
import { consolePath } from "@/lib/console-paths";

type SegmentLink = Readonly<{
  kind: "segment";
  segment: string;
  messageKey: string;
  hub?: boolean;
}>;

type HrefLink = Readonly<{
  kind: "href";
  path: string;
  messageKey: string;
  hash?: string;
}>;

type NavLink = SegmentLink | HrefLink;

type SectionDef = Readonly<{
  titleKey: string;
  links: readonly NavLink[];
}>;

const SECTIONS: readonly SectionDef[] = [
  {
    titleKey: "account.subnavSection.start",
    links: [
      {
        kind: "segment",
        segment: "account",
        messageKey: "account.nav.overview",
        hub: true,
      },
    ],
  },
  {
    titleKey: "account.subnavSection.market",
    links: [
      { kind: "href", path: "terminal", messageKey: "account.nav.chart" },
      { kind: "href", path: "health", messageKey: "account.nav.aiAssistant" },
      { kind: "href", path: "signals", messageKey: "account.nav.signals" },
    ],
  },
  {
    titleKey: "account.subnavSection.trading",
    links: [
      { kind: "href", path: "paper", messageKey: "account.nav.demoAccount" },
      { kind: "href", path: "live-broker", messageKey: "account.nav.orders" },
      {
        kind: "segment",
        segment: "account/broker",
        messageKey: "account.nav.broker",
      },
      { kind: "href", path: "learning", messageKey: "account.nav.performance" },
    ],
  },
  {
    titleKey: "account.subnavSection.money",
    links: [
      {
        kind: "segment",
        segment: "account/balance",
        messageKey: "account.nav.balance",
      },
      {
        kind: "segment",
        segment: "account/deposit",
        messageKey: "account.nav.deposit",
      },
      {
        kind: "segment",
        segment: "account/payments",
        messageKey: "account.nav.payments",
      },
      {
        kind: "segment",
        segment: "account/billing",
        messageKey: "account.nav.billing",
      },
      {
        kind: "segment",
        segment: "account/contract",
        messageKey: "account.nav.contract",
      },
    ],
  },
  {
    titleKey: "account.subnavSection.records",
    links: [
      {
        kind: "segment",
        segment: "account/history",
        messageKey: "account.nav.history",
      },
      {
        kind: "segment",
        segment: "account/performance",
        messageKey: "account.nav.performanceAccount",
      },
      {
        kind: "segment",
        segment: "account/usage",
        messageKey: "account.nav.usage",
      },
    ],
  },
  {
    titleKey: "account.subnavSection.connect",
    links: [
      {
        kind: "segment",
        segment: "account/telegram",
        messageKey: "account.nav.telegram",
      },
      {
        kind: "href",
        path: "account",
        messageKey: "account.nav.assistOnPage",
        hash: "customer-assist",
      },
    ],
  },
  {
    titleKey: "account.subnavSection.settings",
    links: [
      {
        kind: "segment",
        segment: "account/profile",
        messageKey: "account.nav.profile",
      },
      {
        kind: "segment",
        segment: "account/language",
        messageKey: "account.nav.language",
      },
    ],
  },
];

function isSegmentActive(
  pathname: string,
  href: string,
  hub?: boolean,
): boolean {
  if (hub) {
    return pathname === href || pathname === `${href}/`;
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

function isHrefActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function resolveHref(link: NavLink): string {
  if (link.kind === "segment") {
    return consolePath(link.segment);
  }
  const base = consolePath(link.path);
  return link.hash ? `${base}#${link.hash}` : base;
}

export function AccountSubnav() {
  const pathname = usePathname();
  const { t } = useI18n();
  return (
    <nav
      className="account-subnav customer-subnav panel"
      aria-label={t("account.subnavAria")}
    >
      {SECTIONS.map((section) => (
        <div key={section.titleKey} className="customer-subnav__section">
          <p className="customer-subnav__section-title">
            {t(section.titleKey)}
          </p>
          <ul className="account-subnav-list customer-subnav__list">
            {section.links.map((link) => {
              const href = resolveHref(link);
              const baseHref = href.split("#")[0] ?? href;
              let active: boolean;
              if (link.kind === "segment") {
                active = isSegmentActive(
                  pathname,
                  consolePath(link.segment),
                  link.hub,
                );
              } else if (link.hash) {
                active = pathname === baseHref || pathname === `${baseHref}/`;
              } else {
                active = isHrefActive(pathname, baseHref);
              }
              const messageKey = link.messageKey;
              return (
                <li key={`${section.titleKey}-${messageKey}`}>
                  <Link href={href} className={active ? "active" : ""}>
                    {t(messageKey)}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
      <p className="muted small account-subnav-hint customer-subnav__hint">
        {t("account.subnavHint")}
      </p>
    </nav>
  );
}
