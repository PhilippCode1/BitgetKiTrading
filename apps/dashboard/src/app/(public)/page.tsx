import Link from "next/link";

import { HelpHint } from "@/components/help/HelpHint";
import { CONSOLE_BASE, consolePath } from "@/lib/console-paths";
import {
  guidedWelcomeUrl,
  ONBOARDING_DEFAULT_RETURN,
  onboardingUrlWithReturn,
} from "@/lib/onboarding-flow";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function ProductLandingPage() {
  const t = await getServerTranslator();
  const guidedWelcomeHref = guidedWelcomeUrl(ONBOARDING_DEFAULT_RETURN);

  return (
    <main id="top" className="public-main">
      <section className="public-hero">
        <h1>{t("public.heroTitle")}</h1>
        <p className="public-lead">{t("public.heroLead")}</p>
        <p className="muted small public-hero-audience">
          {t("public.heroAudience")}
        </p>
        <div className="public-hero-actions">
          <div className="public-hero-btns">
            <Link href={guidedWelcomeHref} className="public-btn primary">
              {t("public.startGuidedFlow")}
            </Link>
            <Link href={CONSOLE_BASE} className="public-btn ghost">
              {t("public.toConsole")}
            </Link>
            <Link
              href={onboardingUrlWithReturn(ONBOARDING_DEFAULT_RETURN)}
              className="public-btn ghost"
            >
              {t("public.startOnboarding")}
            </Link>
          </div>
          <span className="muted small">{t("public.heroHint")}</span>
        </div>
      </section>

      <section id="ki" className="public-section public-section--ki">
        <h2>{t("public.kiSectionTitle")}</h2>
        <p className="muted public-ki-lead">{t("public.kiSectionLead")}</p>
        <ol className="public-ki-steps">
          <li>
            <h3 className="public-ki-step-title">{t("public.kiStep1Title")}</h3>
            <p className="muted small">{t("public.kiStep1Body")}</p>
          </li>
          <li>
            <h3 className="public-ki-step-title">{t("public.kiStep2Title")}</h3>
            <p className="muted small">{t("public.kiStep2Body")}</p>
          </li>
          <li>
            <h3 className="public-ki-step-title">{t("public.kiStep3Title")}</h3>
            <p className="muted small">{t("public.kiStep3Body")}</p>
          </li>
        </ol>
        <div className="public-hero-btns public-ki-ctas">
          <Link href={guidedWelcomeHref} className="public-btn primary">
            {t("public.kiPrimaryCta")}
          </Link>
          <Link href={consolePath("learning")} className="public-btn ghost">
            {t("public.kiSecondaryLearning")}
          </Link>
        </div>
      </section>

      <section id="leistungen" className="public-section">
        <h2>{t("public.servicesTitle")}</h2>
        <ul className="public-grid">
          <li>
            <h3>{t("public.svc1Title")}</h3>
            <p>{t("public.svc1Body")}</p>
          </li>
          <li>
            <h3>{t("public.svc2Title")}</h3>
            <p>{t("public.svc2Body")}</p>
          </li>
          <li>
            <h3>{t("public.svc3Title")}</h3>
            <p>{t("public.svc3Body")}</p>
          </li>
          <li>
            <h3>{t("public.svc4Title")}</h3>
            <p>{t("public.svc4Body")}</p>
          </li>
        </ul>
      </section>

      <section className="public-section">
        <h2>{t("public.releaseTitle")}</h2>
        <ul className="public-grid">
          <li>
            <h3>{t("public.rel1Title")}</h3>
            <p>{t("public.rel1Body")}</p>
          </li>
          <li>
            <h3>{t("public.rel2Title")}</h3>
            <p>{t("public.rel2Body")}</p>
          </li>
          <li>
            <h3>{t("public.rel3Title")}</h3>
            <p>{t("public.rel3Body")}</p>
          </li>
        </ul>
      </section>

      <section id="transparenz" className="public-section">
        <h2>{t("public.driftTitle")}</h2>
        <p className="muted">{t("public.driftLead")}</p>
      </section>

      <section id="kosten" className="public-section">
        <h2>{t("public.costTitle")}</h2>
        <p className="muted">{t("public.costLead")}</p>
        <p className="muted small">{t("commerce.customerAreaNote")}</p>
      </section>

      <section id="betrieb" className="public-section">
        <div className="public-section-title-row">
          <h2>{t("public.opsTitle")}</h2>
          <HelpHint
            briefKey="help.telegramPublic.brief"
            detailKey="help.telegramPublic.detail"
          />
        </div>
        <p className="muted">{t("public.opsLead")}</p>
        <p className="muted small">{t("telegram.areaHint")}</p>
      </section>

      <section className="public-section public-section--admin">
        <h2>{t("public.adminTitle")}</h2>
        <p>{t("public.adminBody")}</p>
        <Link href={CONSOLE_BASE} className="public-btn ghost">
          {t("public.openConsole")}
        </Link>
      </section>
    </main>
  );
}
