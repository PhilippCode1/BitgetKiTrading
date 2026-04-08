import Link from "next/link";

import { CONSOLE_BASE } from "@/lib/console-paths";
import {
  guidedWelcomeUrl,
  ONBOARDING_DEFAULT_RETURN,
  onboardingUrlWithReturn,
} from "@/lib/onboarding-flow";
import { getServerTranslator } from "@/lib/i18n/server-translate";

/**
 * Schlanke Navigation fuer /welcome und /onboarding — gleiche Ziele wie die Marketing-Shell,
 * ohne doppelte Inhalts-Sektionen.
 */
export async function FlowNavBar() {
  const t = await getServerTranslator();
  const guidedWelcomeHref = guidedWelcomeUrl(ONBOARDING_DEFAULT_RETURN);
  const onboardingOnlyHref = onboardingUrlWithReturn(ONBOARDING_DEFAULT_RETURN);

  return (
    <header className="public-header" role="banner">
      <Link href="/" className="public-brand">
        {t("public.shellBrand")}
      </Link>
      <nav className="public-nav" aria-label={t("public.flowNavAria")}>
        <Link href="/#top" className="public-nav-link-secondary">
          {t("public.navStart")}
        </Link>
        <Link href="/#ki" className="public-nav-link-secondary">
          {t("public.navKi")}
        </Link>
        <Link href="/#leistungen" className="public-nav-link-secondary">
          {t("public.navServices")}
        </Link>
        <Link href="/#kosten" className="public-nav-link-secondary">
          {t("public.navCost")}
        </Link>
        <Link href="/#transparenz" className="public-nav-link-secondary">
          {t("public.navTransparency")}
        </Link>
        <Link href="/#betrieb" className="public-nav-link-secondary">
          {t("public.navOps")}
        </Link>
        <Link href={guidedWelcomeHref} className="public-nav-cta">
          {t("public.navGuidedStart")}
        </Link>
        <Link href={CONSOLE_BASE} className="public-nav-link-secondary">
          {t("public.navConsole")}
        </Link>
        <Link
          href={`${CONSOLE_BASE}/learning`}
          className="public-nav-link-secondary"
        >
          {t("public.footerLearning")}
        </Link>
        <Link href={onboardingOnlyHref} className="public-nav-link-secondary">
          {t("public.startOnboarding")}
        </Link>
      </nav>
    </header>
  );
}
