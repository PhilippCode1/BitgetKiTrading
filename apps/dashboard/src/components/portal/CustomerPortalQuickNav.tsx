import Link from "next/link";

import {
  PORTAL_BASE,
  portalAccountPath,
  portalPath,
} from "@/lib/console-paths";
import { getServerTranslator } from "@/lib/i18n/server-translate";

const LINKS = [
  { href: portalPath("trial"), key: "customerPortal.nav.trial" },
  { href: portalPath("risk"), key: "customerPortal.nav.risk" },
  { href: portalPath("exchange"), key: "customerPortal.nav.exchange" },
  { href: portalPath("performance"), key: "customerPortal.nav.performance" },
  {
    href: portalAccountPath("billing"),
    key: "customerPortal.nav.contractAndBilling",
  },
  { href: portalPath("trading"), key: "customerPortal.nav.trading" },
  { href: portalPath("help"), key: "customerPortal.nav.helpSupport" },
] as const;

export async function CustomerPortalQuickNav() {
  const t = await getServerTranslator();
  return (
    <nav
      className="panel customer-portal-quick-nav"
      aria-label={t("customerPortal.quickNavTitle")}
    >
      <h2 style={{ marginTop: 0, fontSize: "1.05rem" }}>
        {t("customerPortal.quickNavTitle")}
      </h2>
      <p className="muted small">{t("customerPortal.quickNavLead")}</p>
      <ul className="customer-portal-quick-nav__list">
        <li>
          <Link href={PORTAL_BASE} className="dash-inline-link">
            {t("customerPortal.nav.overview")}
          </Link>
        </li>
        {LINKS.map(({ href, key }) => (
          <li key={href}>
            <Link href={href} className="dash-inline-link">
              {t(key)}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
