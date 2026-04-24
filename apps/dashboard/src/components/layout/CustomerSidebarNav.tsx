"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useI18n } from "@/components/i18n/I18nProvider";
import {
  PORTAL_BASE,
  portalAccountPath,
  portalPath,
} from "@/lib/console-paths";

const LINKS: readonly { href: string; messageKey: string }[] = [
    { href: PORTAL_BASE, messageKey: "customerPortal.nav.overview" },
    { href: portalPath("performance"), messageKey: "customerPortal.nav.performance" },
    {
      href: portalAccountPath("billing"),
      messageKey: "customerPortal.nav.contractAndBilling",
    },
    { href: portalPath("help"), messageKey: "customerPortal.nav.helpSupport" },
  ];

export function CustomerSidebarNav() {
  const pathname = usePathname();
  const { t } = useI18n();
  return (
    <aside className="dash-sidebar" data-portal="customer">
      <Link href="/" className="dash-brand dash-brand-link">
        {t("public.shellBrand")}
      </Link>
      <p className="dash-sidebar-note muted small">
        {t("customerPortal.sidebarTrustLine")}
      </p>
      <Link href="/" className="dash-back-to-product">
        {t("customerPortal.backToProduct")}
      </Link>
      <div className="dash-nav-section">
        <div className="dash-nav-heading">{t("customerPortal.nav.aria")}</div>
        <nav className="dash-nav" aria-label={t("customerPortal.nav.aria")}>
          {LINKS.map(({ href, messageKey }) => {
            const active =
              href === PORTAL_BASE
                ? pathname === href || pathname === `${href}/`
                : pathname === href || pathname.startsWith(`${href}/`);
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
    </aside>
  );
}
