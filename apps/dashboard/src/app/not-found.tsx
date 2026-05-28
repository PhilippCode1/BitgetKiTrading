import Link from "next/link";

import { CONSOLE_BASE, PORTAL_BASE } from "@/lib/console-paths";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export default async function NotFound() {
  const t = await getServerTranslator();
  return (
    <>
      <a href="#dash-main-content" className="skip-to-main">
        {t("ui.skipToMain")}
      </a>
      <main className="welcome-gate" id="dash-main-content">
      <div className="welcome-card panel" role="status">
        <h1>{t("ui.notFound.title")}</h1>
        <p className="welcome-lead">{t("ui.notFound.body")}</p>
        <div className="app-error-fallback__actions">
          <Link href="/" className="public-btn primary">
            {t("ui.appError.home")}
          </Link>
          <Link href={PORTAL_BASE} className="public-btn ghost">
            {t("ui.appError.openCustomerPortal")}
          </Link>
          <Link href={CONSOLE_BASE} className="public-btn ghost">
            {t("ui.appError.openConsole")}
          </Link>
        </div>
      </div>
    </main>
    </>
  );
}
