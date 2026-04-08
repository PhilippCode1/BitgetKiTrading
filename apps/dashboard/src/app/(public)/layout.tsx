import Link from "next/link";
import type { ReactNode } from "react";

import { CONSOLE_BASE } from "@/lib/console-paths";
import {
  guidedWelcomeUrl,
  ONBOARDING_DEFAULT_RETURN,
} from "@/lib/onboarding-flow";
import { getMessagesForLocale } from "@/lib/i18n/load-messages";
import { buildTranslator } from "@/lib/i18n/resolve-message";
import { getRequestLocale } from "@/lib/i18n/server";

type Props = Readonly<{ children: ReactNode }>;

export default async function PublicMarketingLayout({ children }: Props) {
  const locale = await getRequestLocale();
  const { messages, fallback } = getMessagesForLocale(locale);
  const t = buildTranslator(locale, messages, fallback);
  const guidedWelcomeHref = guidedWelcomeUrl(ONBOARDING_DEFAULT_RETURN);

  return (
    <div className="public-shell">
      <header className="public-header">
        <Link href="/" className="public-brand">
          {t("public.shellBrand")}
        </Link>
        <nav className="public-nav" aria-label={t("public.navAria")}>
          <Link href="/#top" className="public-nav-link-secondary">
            {t("public.navStart")}
          </Link>
          <a href="/#ki" className="public-nav-link-secondary">
            {t("public.navKi")}
          </a>
          <a href="#leistungen">{t("public.navServices")}</a>
          <a href="#kosten">{t("public.navCost")}</a>
          <a href="#transparenz">{t("public.navTransparency")}</a>
          <a href="#betrieb">{t("public.navOps")}</a>
          <Link href={guidedWelcomeHref} className="public-nav-cta">
            {t("public.navGuidedStart")}
          </Link>
          <Link
            href={`${CONSOLE_BASE}/ops`}
            className="public-nav-link-secondary"
          >
            {t("public.navConsole")}
          </Link>
          <Link
            href={`${CONSOLE_BASE}/learning`}
            className="public-nav-link-secondary"
          >
            {t("public.footerLearning")}
          </Link>
          <Link
            href={`${CONSOLE_BASE}/signals`}
            className="public-nav-link-secondary"
          >
            {t("public.footerSignals")}
          </Link>
        </nav>
      </header>
      {children}
      <footer className="public-footer">
        <nav
          className="public-footer-nav"
          aria-label={t("public.footerNavAria")}
        >
          <Link href="/#top">{t("public.footerProduct")}</Link>
          <a href="/#ki">{t("public.footerKi")}</a>
          <Link href={CONSOLE_BASE}>{t("public.footerConsole")}</Link>
          <Link href={`${CONSOLE_BASE}/learning`}>
            {t("public.footerLearning")}
          </Link>
          <Link href={`${CONSOLE_BASE}/signals`}>
            {t("public.footerSignals")}
          </Link>
          <Link href={`${CONSOLE_BASE}/health`}>
            {t("public.footerHealth")}
          </Link>
          <Link href={guidedWelcomeHref}>{t("public.footerWelcome")}</Link>
        </nav>
        <p className="muted small public-footer-disclaimer">
          {t("public.footerDisclaimer")}
        </p>
      </footer>
    </div>
  );
}
