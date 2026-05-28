import type { ReactNode } from "react";

import { HelpHint } from "@/components/help/HelpHint";
import { SkipToMainLink } from "@/components/layout/SkipToMainLink";
import { CustomerGatewayIncidentBanner } from "@/components/layout/CustomerGatewayIncidentBanner";
import { CustomerPortalProvider } from "@/components/layout/CustomerPortalContext";
import { CustomerSidebarNav } from "@/components/layout/CustomerSidebarNav";
import { LocaleSwitcher } from "@/components/i18n/LocaleSwitcher";
import type { DashboardPersona } from "@/lib/operator-jwt";
import { getCustomerPortalSummary } from "@/lib/customer-portal-summary";
import { readE2eLiveRibbonFixture } from "@/lib/e2e-fixtures";
import { getServerTranslator } from "@/lib/i18n/server-translate";

type Props = Readonly<{
  children: ReactNode;
  /** Server: Cookie-JWT-Auswertung (siehe portal-persona). */
  persona: DashboardPersona;
}>;

/**
 * Kunden-Portal: keine Operator-Steuerung (UiMode, Admin, Heartbeat) — nur Navigation + Sprache.
 */
export async function CustomerShell({ children, persona }: Props) {
  const summary = await getCustomerPortalSummary();
  const t = await getServerTranslator();
  const e2eLiveRibbon = await readE2eLiveRibbonFixture();
  const isLive =
    e2eLiveRibbon ||
    summary.commerceLifecycle?.body?.gatesPreview?.admin_live_trading_granted ===
      true;

  return (
    <CustomerPortalProvider persona={persona}>
      <div
        className="dash-shell"
        data-app-region="customer-portal"
        data-persona={persona}
      >
        <SkipToMainLink />
        <CustomerSidebarNav />
        <div className="dash-main-wrap">
          {isLive ? (
            <div
              className="live-ribbon"
              role="status"
              data-e2e="live-ribbon"
              aria-live="polite"
            >
              {t("customerPortal.tradingPage.ribbonLive")}
            </div>
          ) : null}
          <CustomerGatewayIncidentBanner />
          <div className="dash-locale-bar">
            <div className="dash-bar-group" />
            <div className="dash-bar-group">
              <LocaleSwitcher />
              <HelpHint
                briefKey="help.language.brief"
                detailKey="help.language.detail"
              />
            </div>
          </div>
          <main id="dash-main-content" className="dash-main" tabIndex={-1}>
            {children}
          </main>
        </div>
      </div>
    </CustomerPortalProvider>
  );
}
