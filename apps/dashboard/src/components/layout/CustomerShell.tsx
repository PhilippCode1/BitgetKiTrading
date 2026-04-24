import type { ReactNode } from "react";

import { HelpHint } from "@/components/help/HelpHint";
import { CustomerGatewayIncidentBanner } from "@/components/layout/CustomerGatewayIncidentBanner";
import {
  CustomerPortalProvider,
} from "@/components/layout/CustomerPortalContext";
import { CustomerSidebarNav } from "@/components/layout/CustomerSidebarNav";
import { LocaleSwitcher } from "@/components/i18n/LocaleSwitcher";
import type { DashboardPersona } from "@/lib/operator-jwt";

type Props = Readonly<{
  children: ReactNode;
  /** Server: Cookie-JWT-Auswertung (siehe portal-persona). */
  persona: DashboardPersona;
}>;

/**
 * Kunden-Portal: keine Operator-Steuerung (UiMode, Admin, Heartbeat) — nur Navigation + Sprache.
 */
export function CustomerShell({ children, persona }: Props) {
  return (
    <CustomerPortalProvider persona={persona}>
      <div
        className="dash-shell"
        data-app-region="customer-portal"
        data-persona={persona}
      >
        <CustomerSidebarNav />
        <div className="dash-main-wrap">
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
          <main className="dash-main">{children}</main>
        </div>
      </div>
    </CustomerPortalProvider>
  );
}
