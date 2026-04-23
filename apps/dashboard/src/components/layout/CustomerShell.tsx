import type { ReactNode } from "react";

import { HelpHint } from "@/components/help/HelpHint";
import { CustomerSidebarNav } from "@/components/layout/CustomerSidebarNav";
import { LocaleSwitcher } from "@/components/i18n/LocaleSwitcher";

type Props = Readonly<{
  children: ReactNode;
}>;

/**
 * Kunden-Portal: keine Operator-Steuerung (UiMode, Admin, Heartbeat) — nur Navigation + Sprache.
 */
export function CustomerShell({ children }: Props) {
  return (
    <div className="dash-shell" data-app-region="customer-portal">
      <CustomerSidebarNav />
      <div className="dash-main-wrap">
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
  );
}
